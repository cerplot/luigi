#include <string>
#include <map>
#include <vector>
#include "exchange_info.h

class Asset {
public:
    unsigned int id;
    std::shared_ptr<ExchangeInfo> exchange_info;
    std::string symbol;
    std::string name;

    std::chrono::system_clock::time_point start_date;
    std::chrono::system_clock::time_point end_date;

    std::optional<std::chrono::system_clock::time_point> first_traded;
    std::optional<std::chrono::system_clock::time_point> auto_close_date;
    double tick_size;
    float price_multiplier;
    Asset(unsigned int id, std::shared_ptr<ExchangeInfo> exchange_info, std::string_view symbol = "", std::string asset_name = "", void* start_date = nullptr, void* end_date = nullptr, void* first_traded = nullptr, void* auto_close_date = nullptr, double tick_size = 0.01, float multiplier = 1.0) {
        this->id = id;
        this->exchange_info = exchange_info;
        this->symbol = symbol;
        this->name = asset_name;
        this->start_date = start_date;
        this->end_date = end_date;
        this->first_traded = first_traded;
        this->auto_close_date = auto_close_date;
        this->tick_size = tick_size;
        this->price_multiplier = multiplier;
    }
    std::string exchange() {
        return exchange_info->canonical_name;
    }

    std::string exchangeFull() {
        return exchange_info->name;
    }

    std::string countryCode() {
        return exchange_info->countryCode;
    }
    int64_t getId() const {
        return id;
    }
    int64_t getIndex() const {
        return id;
    }
    int64_t getHash() const {
        return id;
    }
    bool operator==(const Asset& other) const {
        return id == other.id;
    }

    bool operator!=(const Asset& other) const {
        return id != other.id;
    }
    bool operator<(const Asset& other) const {
        return id < other.id;
    }
    bool operator<=(const Asset& other) const {
        return id <= other.id;
    }
    bool operator>(const Asset& other) const {
        return id > other.id;
    }
    bool operator>=(const Asset& other) const {
        return id >= other.id;
    }

    std::string toString() const {
        std::ostringstream oss;
        if (!symbol.empty()) {
            oss << typeid(*this).name() << "(" << id << " [" << symbol << "])";
        } else {
            oss << typeid(*this).name() << "(" << id << ")";
        }
        return oss.str();
    }

    std::map<std::string, std::string> toDict() {
        std::map<std::string, std::string> dict;
        dict["id"] = std::to_string(id);
        dict["symbol"] = symbol;
        dict["name"] = name;
        // You would need to convert the time_points to string
        // This is a placeholder, actual conversion might be different
        dict["start_date"] = std::to_string(start_date.time_since_epoch().count());
        dict["end_date"] = std::to_string(end_date.time_since_epoch().count());
        dict["first_traded"] = std::to_string(first_traded.time_since_epoch().count());
        dict["auto_close_date"] = std::to_string(auto_close_date.time_since_epoch().count());
        dict["exchange"] = exchange_info->exchange;
        dict["exchange_full"] = exchange_info->exchange_full;
        dict["tick_size"] = std::to_string(tick_size);
        dict["price_multiplier"] = std::to_string(price_multiplier);
        dict["exchange_info"] = exchange_info.repr();
        return dict;
    }

    bool is_alive_for_session(std::chrono::system_clock::time_point session_label) {
        return start_date <= session_label && session_label <= end_date;
    }

    bool is_exchange_open(std::chrono::system_clock::time_point dt_minute) {
        Calendar calendar = get_calendar(exchange->exchangeFull());
        return calendar.is_open_on_minute(dt_minute);
    }
};


class Equity : public Asset {
    // Define the attributes and methods of Equity
};

class Future : public Asset {
public:
    std::string root_symbol;
    // Replace these with appropriate date/time types in C++
    void* notice_date;
    void* expiration_date;

    Future(unsigned int id,
           ExchangeInfo* exchange_info,
           std::string symbol = "",
           std::string root_symbol = "",
           std::string asset_name = "",
           void* start_date = nullptr,
           void* end_date = nullptr,
           void* notice_date = nullptr,
           void* expiration_date = nullptr,
           void* auto_close_date = nullptr,
           void* first_traded = nullptr,
           double tick_size = 0.001,
           float multiplier = 1.0) : Asset(sid, exchange_info, symbol, asset_name, start_date, end_date, first_traded, auto_close_date, tick_size, multiplier) {
        this->root_symbol = root_symbol;
        this->notice_date = notice_date;
        this->expiration_date = expiration_date;

        if (auto_close_date == nullptr) {
            if (notice_date == nullptr) {
                this->auto_close_date = expiration_date;
            } else if (expiration_date == nullptr) {
                this->auto_close_date = notice_date;
            } else {
                // Replace this with appropriate min function for your date/time type
                this->auto_close_date = min(notice_date, expiration_date);
            }
        }
    }

    // For the __reduce__ method, C++ doesn't support pickling or similar functionality out of the box.
    // You would need to implement serialization and deserialization manually or use a library.

    std::map<std::string, void*> toDict() {
        std::map<std::string, void*> super_dict = Asset::to_dict();
        super_dict["root_symbol"] = &this->root_symbol;
        super_dict["notice_date"] = this->notice_date;
        super_dict["expiration_date"] = this->expiration_date;
        return super_dict;
    }
};


std::vector<Asset> make_asset_array(int size, Asset asset) {
    std::vector<Asset> out(size, asset);
    return out;
}
