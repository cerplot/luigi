#include <string>

class ExchangeInfo {
public:
    ExchangeInfo(std::string name, std::string canonical_name, std::string country_code)
            : name(name), canonical_name(canonical_name.empty() ? name : canonical_name), country_code(country_code) {
        std::transform(country_code.begin(), country_code.end(), country_code.begin(), ::toupper);
    }

    std::string to_string() const {
        return "ExchangeInfo(" + name + ", " + canonical_name + ", " + country_code + ")";
    }

    // Assuming get_calendar() is a function that returns a TradingCalendar object
    TradingCalendar calendar() const {
        return get_calendar(canonical_name);
    }

    bool operator==(const ExchangeInfo& other) const {
        return name == other.name && canonical_name == other.canonical_name && country_code == other.country_code;
    }

    bool operator!=(const ExchangeInfo& other) const {
        return !(*this == other);
    }

private:
    std::string name;
    std::string canonical_name;
    std::string country_code;
};