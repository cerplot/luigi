#include <string>
#include <cmath>
#include <stdexcept>
#include <map>

enum class ORDER_STATUS {
    OPEN,
    FILLED,
    CANCELLED,
    REJECTED,
    HELD
};

enum class DATASOURCE_TYPE {
    ORDER
};

class Order {
private:
    std::string id;
    std::string dt;
    std::string reason;
    std::string created;
    Asset asset;
    int amount;
    int filled;
    double commission;
    ORDER_STATUS _status;
    double stop;
    double limit;
    bool stop_reached;
    bool limit_reached;
    int direction;
    DATASOURCE_TYPE type;
    std::string broker_order_id;

public:
    Order(std::string dt, Asset asset, int amount, double stop = 0, double limit = 0, int filled = 0, double commission = 0, std::string id = "")
            : dt(dt), asset(asset), amount(amount), stop(stop), limit(limit), filled(filled), commission(commission), id(id), _status(ORDER_STATUS::OPEN), stop_reached(false), limit_reached(false), direction(amount > 0 ? 1 : -1), type(DATASOURCE_TYPE::ORDER), broker_order_id("") {
        if (id.empty()) {
            this->id = make_id();
        }
    }
    // Assume a method make_id() that generates a unique id
    std::string make_id() {
        uuid_t uuid;
        uuid_generate_random(uuid);
        char uuid_str[37];
        uuid_unparse_lower(uuid, uuid_str);
        return std::string(uuid_str);
    }

    Asset getAsset() const { return asset; }
    int getAmount() const { return amount; }
    std::string getDt() const { return dt; }
    double getStop() const { return stop; }
    double getLimit() const { return limit; }
    int getFilled() const { return filled; }
    double getCommission() const { return commission; }
    ORDER_STATUS getStatus() const { return _status; }
    DATASOURCE_TYPE getType() const { return type; }
    std::string getBrokerOrderId() const { return broker_order_id; }

    std::map<std::string, std::variant<int, double, std::string, Asset, ORDER_STATUS>> to_dict() {
        std::map<std::string, std::variant<int, double, std::string, Asset, ORDER_STATUS>> dct;
        dct["id"] = id;
        dct["dt"] = dt;
        dct["reason"] = reason;
        dct["created"] = created;
        dct["amount"] = amount;
        dct["filled"] = filled;
        dct["commission"] = commission;
        dct["stop"] = stop;
        dct["limit"] = limit;
        dct["stop_reached"] = stop_reached;
        dct["limit_reached"] = limit_reached;
        dct["direction"] = direction;
        dct["type"] = static_cast<int>(type);

        if (!broker_order_id.empty()) {
            dct["broker_order_id"] = broker_order_id;
        }

        dct["sid"] = asset; // Assuming Asset can be implicitly converted to string
        dct["status"] = static_cast<int>(_status);

        return dct;
    }

    Asset getSid() const {
        // For backwards compatibility because we pass this object to
        // custom slippage models.
        return this->asset;
    }
    Order to_api_obj() {
        auto pydict = this->to_dict();
        Order obj(pydict); // Assuming ep::Order constructor takes a std::map
        return obj;
    }

    void check_triggers(double price, std::string dt) {
        bool stop_reached, limit_reached, sl_stop_reached;
        std::tie(stop_reached, limit_reached, sl_stop_reached) = check_order_triggers(price);
        if (stop_reached != this->stop_reached || limit_reached != this->limit_reached) {
            this->dt = dt;
        }
        this->stop_reached = stop_reached;
        this->limit_reached = limit_reached;
        if (sl_stop_reached) {
            // Change the STOP LIMIT order into a LIMIT order
            this->stop = 0;
        }
    }
    std::tuple<bool, bool, bool> check_order_triggers(double current_price) {
        if (this->triggered) {
            return std::make_tuple(this->stop_reached, this->limit_reached, false);
        }

        bool stop_reached = false;
        bool limit_reached = false;
        bool sl_stop_reached = false;

        int order_type = 0;

        if (this->amount > 0) {
            order_type |= BUY;
        } else {
            order_type |= SELL;
        }

        if (this->stop != 0) {
            order_type |= STOP;
        }

        if (this->limit != 0) {
            order_type |= LIMIT;
        }

        if (order_type == (BUY | STOP | LIMIT)) {
            if (current_price >= this->stop) {
                sl_stop_reached = true;
                if (current_price <= this->limit) {
                    limit_reached = true;
                }
            }
        } else if (order_type == (SELL | STOP | LIMIT)) {
            if (current_price <= this->stop) {
                sl_stop_reached = true;
                if (current_price >= this->limit) {
                    limit_reached = true;
                }
            }
        } else if (order_type == (BUY | STOP)) {
            if (current_price >= this->stop) {
                stop_reached = true;
            }
        } else if (order_type == (SELL | STOP)) {
            if (current_price <= this->stop) {
                stop_reached = true;
            }
        } else if (order_type == (BUY | LIMIT)) {
            if (current_price <= this->limit) {
                limit_reached = true;
            }
        } else if (order_type == (SELL | LIMIT)) {
            if (current_price >= this->limit) {
                limit_reached = true;
            }
        }

        return std::make_tuple(stop_reached, limit_reached, sl_stop_reached);
    }

    void handle_split(double ratio) {
        // update the amount, limit_price, and stop_price
        // by the split's ratio

        // info here: http://finra.complinet.com/en/display/display_plain.html?
        // rbid=2403&element_id=8950&record_id=12208&print=1

        // new_share_amount = old_share_amount / ratio
        // new_price = old_price * ratio

        this->amount = static_cast<int>(this->amount / ratio);

        if (this->limit != 0) {
            this->limit = std::round(this->limit * ratio * 100) / 100;
        }

        if (this->stop != 0) {
            this->stop = std::round(this->stop * ratio * 100) / 100;
        }
    }
    ORDER_STATUS getStatus() const {
        if (open_amount == 0) {
            return ORDER_STATUS::FILLED;
        } else if (_status == ORDER_STATUS::HELD && filled != 0) {
            return ORDER_STATUS::OPEN;
        } else {
            return _status;
        }
    }
    void setStatus(ORDER_STATUS status) {
        _status = status;
    }
    void cancel() {
        this->setStatus(ORDER_STATUS::CANCELLED);
    }

    void hold(std::string reason = "") {
        this->setStatus(ORDER_STATUS::HELD);
        this->reason = reason;
    }
    bool isOpen() const {
        return this->_status == ORDER_STATUS::OPEN || this->_status == ORDER_STATUS::HELD;
    }

    bool isTriggered() const {
        if (this->stop != 0 && !this->stop_reached) {
            return false;
        }

        if (this->limit != 0 && !this->limit_reached) {
            return false;
        }

        return true;
    }

    int getOpenAmount() const {
        return amount - filled;
    }

    struct Visitor {
        template <typename T>
        std::string operator()(T t) const {
            std::ostringstream oss;
            oss << t;
            return oss.str();
        }
    };

    std::string repr() const {
        std::ostringstream oss;
        auto dict = to_dict();
        oss << "Order(";
        for (const auto& pair : dict) {
            oss << pair.first << ": " << std::visit(Visitor{}, pair.second) << ", ";
        }
        std::string reprStr = oss.str();
        reprStr = reprStr.substr(0, reprStr.length()-2);  // remove the last comma and space
        reprStr += ")";
        return reprStr;
    }

};