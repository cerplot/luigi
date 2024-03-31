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

class Asset {
    // Assume Asset class is defined elsewhere
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
            : dt(dt), asset(asset), amount(amount), stop(stop), limit(limit), filled(filled), commission(commission), id(id), _status(ORDER_STATUS::OPEN), stop_reached(false), limit_reached(false), direction(amount > 0 ? 1 : -1), type(DATASOURCE_TYPE::ORDER), broker_order_id("") {}

    // Assume a method make_id() that generates a unique id
    std::string make_id() {
        // Generate a unique id
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

    // Other methods and properties are omitted for brevity
};