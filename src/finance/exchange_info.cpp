#include <string>
#include <algorithm>
#include <tuple>

class ExchangeInfo {
public:
    std::string name;
    std::string canonical_name;
    std::string country_code;

    ExchangeInfo(const std::string& name, const std::string& canonical_name, const std::string& country_code)
            : name(name), canonical_name(canonical_name.empty() ? name : canonical_name), country_code(country_code) {
        std::transform(this->country_code.begin(), this->country_code.end(), this->country_code.begin(), ::toupper);
    }

    std::string repr() const {
        return "ExchangeInfo(" + name + ", " + canonical_name + ", " + country_code + ")";
    }

    Calendar get_calendar() const {
        return get_calendar_by_name(canonical_name);
    }

    bool operator==(const ExchangeInfo& other) const {
        return std::tie(name, canonical_name, country_code) == std::tie(other.name, other.canonical_name, other.country_code);
    }

    bool operator!=(const ExchangeInfo& other) const {
        return !(*this == other);
    }
};