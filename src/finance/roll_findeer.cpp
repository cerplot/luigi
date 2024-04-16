#include <vector>
#include <map>
#include <string>
#include <chrono>
#include <algorithm>

// Number of days over which to compute rolls when finding the current contract
// for a volume-rolling contract chain.
const int ROLL_DAYS_FOR_CURRENT_CONTRACT = 90;

class RollFinder {
public:
    virtual ~RollFinder() = default;

    virtual int _active_contract(int oc, int front, int back, std::chrono::system_clock::time_point dt) = 0;

    int _get_active_contract_at_offset(std::string root_symbol, std::chrono::system_clock::time_point dt, int offset) {
        OrderedContracts oc = asset_finder.get_ordered_contracts(root_symbol);
        std::chrono::system_clock::time_point session = trading_calendar.minute_to_session(dt);
        int front = oc.contract_before_auto_close(session);
        int back = oc.contract_at_offset(front, 1, dt);
        if (back == -1) { // Assuming -1 indicates None
            return front;
        }
        int primary = _active_contract(oc, front, back, session);
        return oc.contract_at_offset(primary, offset, session);
    }

    int get_contract_center(std::string root_symbol, std::chrono::system_clock::time_point dt, int offset) {
        return _get_active_contract_at_offset(root_symbol, dt, offset);
    }

    std::vector<std::pair<int, std::chrono::system_clock::time_point>> RollFinder::get_rolls(std::string root_symbol, std::chrono::system_clock::time_point start, std::chrono::system_clock::time_point end, int offset) {
        OrderedContracts oc = asset_finder.get_ordered_contracts(root_symbol);
        int front = _get_active_contract_at_offset(root_symbol, end, 0);
        int back = oc.contract_at_offset(front, 1, end);
        int first;
        if (back != -1) { // Assuming -1 indicates None
            std::chrono::system_clock::time_point end_session = trading_calendar.minute_to_session(end);
            first = _active_contract(oc, front, back, end_session);
        } else {
            first = front;
        }
        Contract first_contract = oc.sid_to_contract[first];
        std::vector<std::pair<int, std::chrono::system_clock::time_point>> rolls = {{first_contract.contract.sid >> offset, std::chrono::system_clock::time_point()}}; // Assuming std::chrono::system_clock::time_point() indicates None
        Calendar tc = trading_calendar;
        std::vector<std::chrono::system_clock::time_point> sessions = tc.sessions_in_range(tc.minute_to_session(start), tc.minute_to_session(end));
        std::chrono::system_clock::time_point freq = sessions[1] - sessions[0]; // Assuming sessions are sorted in ascending order
        Contract curr;
        if (first == front) {
            curr = first_contract << 1;
        } else {
            curr = first_contract << 2;
        }
        std::chrono::system_clock::time_point session = sessions.back();

        while (session > start && curr.contract.sid != -1) { // Assuming -1 indicates None
            front = curr.contract.sid;
            back = rolls[0].first;
            Contract prev_c = curr.prev;
            while (session > start) {
                std::chrono::system_clock::time_point prev = session - freq;
                if (prev_c.contract.sid != -1) { // Assuming -1 indicates None
                    if (prev < prev_c.contract.auto_close_date) {
                        break;
                    }
                }
                if (back != _active_contract(oc, front, back, prev)) {
                    rolls.insert(rolls.begin(), {curr.contract.sid >> offset, session});
                    break;
                }
                session = prev;
            }
            curr = curr.prev;
            if (curr.contract.sid != -1) { // Assuming -1 indicates None
                session = std::min(session, curr.contract.auto_close_date + freq);
            }
        }

        return rolls;
    }

};

class CalendarRollFinder : public RollFinder {
public:
    CalendarRollFinder(Calendar trading_calendar, AssetFinder asset_finder)
            : trading_calendar(trading_calendar), asset_finder(asset_finder) {}

    int _active_contract(int oc, int front, int back, std::chrono::system_clock::time_point dt) override {
        Contract contract = asset_finder.sid_to_contract[front].contract;
        std::chrono::system_clock::time_point auto_close_date = contract.auto_close_date;
        bool auto_closed = dt >= auto_close_date;
        return auto_closed ? back : front;
    }

private:
    Calendar trading_calendar;
    AssetFinder asset_finder;
};


class VolumeRollFinder : public RollFinder {
public:
    static const int GRACE_DAYS = 7;

    VolumeRollFinder(Calendar trading_calendar, AssetFinder asset_finder, SessionReader session_reader)
            : trading_calendar(trading_calendar), asset_finder(asset_finder), session_reader(session_reader) {}

    int _active_contract(int oc, int front, int back, std::chrono::system_clock::time_point dt) {
        Contract front_contract = asset_finder.sid_to_contract[front].contract;
        Contract back_contract = asset_finder.sid_to_contract[back].contract;

        std::chrono::duration<int, std::ratio<24*60*60>> trading_day = trading_calendar.day(); // Assuming trading_calendar.day() returns a duration representing one day
        std::chrono::system_clock::time_point prev = dt - trading_day;

        if (dt > std::min(front_contract.auto_close_date, front_contract.end_date)) {
            return back;
        } else if (front_contract.start_date > prev) {
            return back;
        } else if (dt > std::min(back_contract.auto_close_date, back_contract.end_date)) {
            return front;
        } else if (back_contract.start_date > prev) {
            return front;
        }

        int front_vol = session_reader.get_value(front, prev, "volume"); // Assuming session_reader.get_value() returns the volume
        int back_vol = session_reader.get_value(back, prev, "volume"); // Assuming session_reader.get_value() returns the volume
        if (back_vol > front_vol) {
            return back;
        }

        std::chrono::system_clock::time_point gap_start = std::max(back_contract.start_date, front_contract.auto_close_date - GRACE_DAYS * trading_day);
        std::chrono::system_clock::time_point gap_end = prev - trading_day;
        if (dt < gap_start) {
            return front;
        }

        std::vector<std::chrono::system_clock::time_point> sessions = trading_calendar.sessions_in_range(trading_calendar.minute_to_session(gap_start), trading_calendar.minute_to_session(gap_end)); // Assuming trading_calendar.minute_to_session() returns a session
        for (std::chrono::system_clock::time_point session : sessions) {
            front_vol = session_reader.get_value(front, session, "volume"); // Assuming session_reader.get_value() returns the volume
            back_vol = session_reader.get_value(back, session, "volume"); // Assuming session_reader.get_value() returns the volume
            if (back_vol > front_vol) {
                return back;
            }
        }

        return front;
    }

    Asset VolumeRollFinder::get_contract_center(std::string root_symbol, std::chrono::system_clock::time_point dt, int offset) {
        std::chrono::duration<int, std::ratio<24*60*60>> day = trading_calendar.day(); // Assuming trading_calendar.day() returns a duration representing one day
        std::chrono::system_clock::time_point end_date = std::min(dt + ROLL_DAYS_FOR_CURRENT_CONTRACT * day, session_reader.last_available_dt()); // Assuming session_reader.last_available_dt() returns the last available date-time
        std::vector<std::pair<int, std::chrono::system_clock::time_point>> rolls = get_rolls(root_symbol, dt, end_date, offset);
        int sid = rolls[0].first;
        return asset_finder.retrieve_asset(sid); // Assuming asset_finder.retrieve_asset() returns an Asset
    }

private:
    Calendar trading_calendar;
    AssetFinder asset_finder;
    SessionReader session_reader;
};