#include <vector>
#include <map>
#include <algorithm>
#include <chrono>

const long long _nanos_in_minute = 60000000000LL;
const long long NANOS_IN_MINUTE = _nanos_in_minute;

enum EventType {
    BAR = 0,
    SESSION_START = 1,
    SESSION_END = 2,
    MINUTE_END = 3,
    BEFORE_TRADING_START_BAR = 4
};

class MinuteSimulationClock {
private:
    bool minute_emission;
    std::vector<std::chrono::nanoseconds> market_opens_nanos, market_closes_nanos, bts_nanos, sessions_nanos;
    std::map<std::chrono::nanoseconds, std::vector<std::chrono::nanoseconds>> minutes_by_session;

public:
    MinuteSimulationClock(std::vector<std::chrono::nanoseconds> sessions,
                          std::vector<std::chrono::nanoseconds> market_opens,
                          std::vector<std::chrono::nanoseconds> market_closes,
                          std::vector<std::chrono::nanoseconds> before_trading_start_minutes,
                          bool minute_emission=false)
            : sessions_nanos(sessions), market_opens_nanos(market_opens), market_closes_nanos(market_closes),
              bts_nanos(before_trading_start_minutes), minute_emission(minute_emission) {
        calc_minutes_by_session();
    }

    void calc_minutes_by_session() {
        for (size_t i = 0; i < sessions_nanos.size(); ++i) {
            std::vector<std::chrono::nanoseconds> minutes_nanos;
            for (auto t = market_opens_nanos[i]; t <= market_closes_nanos[i]; t += std::chrono::minutes(1)) {
                minutes_nanos.push_back(t);
            }
            minutes_by_session[sessions_nanos[i]] = minutes_nanos;
        }
    }

    std::vector<std::pair<std::chrono::nanoseconds, EventType>> get_events() {
        std::vector<std::pair<std::chrono::nanoseconds, EventType>> events;

        for (size_t i = 0; i < sessions_nanos.size(); ++i) {
            events.push_back({sessions_nanos[i], SESSION_START});

            auto bts_minute = bts_nanos[i];
            auto& regular_minutes = minutes_by_session[sessions_nanos[i]];

            if (bts_minute > regular_minutes.back()) {
                for (auto& minute : regular_minutes) {
                    events.push_back({minute, BAR});
                    if (minute_emission) {
                        events.push_back({minute, MINUTE_END});
                    }
                }
            } else {
                auto bts_idx = std::lower_bound(regular_minutes.begin(), regular_minutes.end(), bts_minute) - regular_minutes.begin();

                for (size_t j = 0; j < bts_idx; ++j) {
                    events.push_back({regular_minutes[j], BAR});
                    if (minute_emission) {
                        events.push_back({regular_minutes[j], MINUTE_END});
                    }
                }

                events.push_back({bts_minute, BEFORE_TRADING_START_BAR});

                for (size_t j = bts_idx; j < regular_minutes.size(); ++j) {
                    events.push_back({regular_minutes[j], BAR});
                    if (minute_emission) {
                        events.push_back({regular_minutes[j], MINUTE_END});
                    }
                }
            }

            events.push_back({regular_minutes.back(), SESSION_END});
        }

        return events;
    }
};