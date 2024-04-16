#include <string>
#include <set>
#include <map>
#include <functional>

bool delivery_predicate(std::set<char> codes, Contract contract) {
    char delivery_code = contract.symbol().back();
    return codes.find(delivery_code) != codes.end();
}

std::set<char> march_cycle_codes = {'H', 'M', 'U', 'Z'};
std::set<char> pl_codes = {'F', 'J', 'N', 'V'};
std::set<char> gc_codes = {'G', 'J', 'M', 'Q', 'V', 'Z'};
std::set<char> sv_codes = {'H', 'K', 'N', 'U', 'Z'};

std::map<std::string, std::function<bool(Contract)>> CHAIN_PREDICATES = {
        {"EL", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"ME", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"PL", std::bind(delivery_predicate, pl_codes, std::placeholders::_1)},
        {"PA", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"JY", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"CD", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"AD", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"BP", std::bind(delivery_predicate, march_cycle_codes, std::placeholders::_1)},
        {"GC", std::bind(delivery_predicate, gc_codes, std::placeholders::_1)},
        {"XG", std::bind(delivery_predicate, gc_codes, std::placeholders::_1)},
        {"SV", std::bind(delivery_predicate, sv_codes, std::placeholders::_1)},
        {"YS", std::bind(delivery_predicate, sv_codes, std::placeholders::_1)}
};

std::set<std::string> ADJUSTMENT_STYLES = {"add", "mul"};


#include <string>
#include <functional>

class ContinuousFuture {
public:
    ContinuousFuture(int64_t sid, std::string root_symbol, int offset, std::string roll_style, std::string start_date, std::string end_date, ExchangeInfo exchange_info, std::string adjustment = "")
            : sid(sid), root_symbol(root_symbol), offset(offset), roll_style(roll_style), start_date(start_date), end_date(end_date), exchange_info(exchange_info), adjustment(adjustment) {}

    std::string exchange() const {
        return exchange_info.canonical_name();
    }

    std::string exchange_full() const {
        return exchange_info.name();
    }

    int64_t to_int() const {
        return sid;
    }

    bool operator==(const ContinuousFuture& other) const {
        return sid == other.sid;
    }

    bool operator!=(const ContinuousFuture& other) const {
        return !(*this == other);
    }

    bool operator<(const ContinuousFuture& other) const {
        return sid < other.sid;
    }

    bool operator<=(const ContinuousFuture& other) const {
        return sid <= other.sid;
    }

    bool operator>(const ContinuousFuture& other) const {
        return sid > other.sid;
    }

    bool operator>=(const ContinuousFuture& other) const {
        return sid >= other.sid;
    }

    std::string to_string() const {
        return "ContinuousFuture(" + std::to_string(sid) + " [" + root_symbol + ", " + std::to_string(offset) + ", " + roll_style + ", " + adjustment + "])";
    }

    bool ContinuousFuture::is_alive_for_session(std::chrono::system_clock::time_point session_label) const {
        std::istringstream start_stream(start_date);
        std::istringstream end_stream(end_date);
        date::sys_seconds start_tp;
        date::sys_seconds end_tp;
        start_stream >> date::parse("%Y-%m-%d", start_tp);
        end_stream >> date::parse("%Y-%m-%d", end_tp);
        std::chrono::system_clock::time_point start_date_tp = std::chrono::system_clock::from_time_t(start_tp.time_since_epoch().count());
        std::chrono::system_clock::time_point end_date_tp = std::chrono::system_clock::from_time_t(end_tp.time_since_epoch().count());

        return start_date_tp <= session_label && session_label <= end_date_tp;
    }


    bool ContinuousFuture::is_exchange_open(std::chrono::system_clock::time_point dt_minute) const {
        Calendar calendar = get_calendar(exchange()); // Assuming get_calendar() is a function that returns a Calendar object
        return calendar.is_open_on_minute(dt_minute); // Assuming calendar.is_open_on_minute() returns a boolean
    }


private:
    int64_t sid;
    std::string root_symbol;
    int offset;
    std::string roll_style;
    std::string start_date;
    std::string end_date;
    ExchangeInfo exchange_info;
    std::string adjustment;
};