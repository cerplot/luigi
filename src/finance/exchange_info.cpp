#include <string>
#include <algorithm>

class ExchangeInfo {
public:
    std::string name;
    std::string canonical_name;
    std::string country_code;

    ExchangeInfo(std::string name, std::string canonical_name, std::string country_code) {
        this->name = name;

        if (canonical_name.empty()) {
            canonical_name = name;
        }

        this->canonical_name = canonical_name;
        std::transform(this->country_code.begin(), this->country_code.end(), this->country_code.begin(), ::toupper);
    }

    std::string repr() {
        return "ExchangeInfo(" + this->name + ", " + this->canonical_name + ", " + this->country_code + ")";
    }

    TradingCalendar get_calendar() {
        return get_calendar_by_name(this->canonical_name);
    }

    bool operator==(const ExchangeInfo& other) const {
        return this->name == other.name && this->canonical_name == other.canonical_name && this->country_code == other.country_code;
    }

    bool operator!=(const ExchangeInfo& other) const {
        return !(*this == other);
    }
};