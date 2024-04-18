#include <string>
#include <cmath>
#include <stdexcept>

enum class DATASOURCE_TYPE {
    TRANSACTION
};


class Transaction {
private:
    Asset asset;
    int amount;
    std::string dt;
    double price;
    int order_id;
    DATASOURCE_TYPE type;

public:
    Transaction(Asset asset, int amount, std::string dt, double price, int order_id)
            : asset(asset), amount(amount), dt(dt), price(price), order_id(order_id), type(DATASOURCE_TYPE::TRANSACTION) {}

    Asset getAsset() const { return asset; }
    int getAmount() const { return amount; }
    std::string getDt() const { return dt; }
    double getPrice() const { return price; }
    int getOrderId() const { return order_id; }
    DATASOURCE_TYPE getType() const { return type; }

    std::string repr() const {
        return "Transaction(asset=" + std::to_string(asset) + ", dt=" + dt +
               ", amount=" + std::to_string(amount) + ", price=" + std::to_string(price) + ")";
    }
};

Transaction create_transaction(Order order, std::string dt, double price, int amount) {
    int amount_magnitude = std::abs(amount);

    if (amount_magnitude < 1) {
        throw std::runtime_error("Transaction magnitude must be at least 1.");
    }

    return Transaction(order.asset, amount, dt, price, order.id);
}