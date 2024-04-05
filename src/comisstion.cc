#include <iostream>
#include <vector>

// Assuming Equity and Future are defined somewhere
class Equity {};
class Future {};


class Asset {};  // Assuming Asset is defined somewhere

class AllowedAssetMarker {
public:
    virtual std::vector<std::type_index> getAllowedAssetTypes() = 0;  // Pure virtual function
};

class EquityCommissionModel : public AllowedAssetMarker {
public:
    std::vector<std::type_index> getAllowedAssetTypes() override {
        return {typeid(Equity)};
    }
};

class FutureCommissionModel : public AllowedAssetMarker {
public:
    std::vector<std::type_index> getAllowedAssetTypes() override {
        return {typeid(Future)};
    }
};


// Assuming Order and Transaction are defined somewhere
class Order {
public:
    double commission = 0;
    int filled = 0;
};

class Transaction {
public:
    int amount = 0;
    double price = 0;
};

class CommissionModel {
public:
    virtual double calculate(Order order, Transaction transaction) = 0; // Pure virtual function
};

class NoCommission : public CommissionModel {
public:
    double calculate(Order order, Transaction transaction) override {
        return 0.0;
    }
};

class PerShare : public CommissionModel {
private:
    double cost_per_share;
    double min_trade_cost;
public:
    PerShare(double cost, double min_cost) : cost_per_share(cost), min_trade_cost(min_cost) {}
    double calculate(Order order, Transaction transaction) override {
        // Simplified calculation logic
        return abs(transaction.amount * cost_per_share);
    }
};



class PerContract {
protected:
    float cost;
    float exchange_fee;
    float min_trade_cost;

public:
    PerContract(float cost = 0, float exchange_fee = 0, float min_trade_cost = 0)
            : cost(cost), exchange_fee(exchange_fee), min_trade_cost(min_trade_cost) {}
};

class PerFutureTrade : public PerContract {
private:
    float cost_per_trade;

public:
    static constexpr float DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE = 0.0;

    PerFutureTrade(float cost = DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE)
            : PerContract(0, cost, 0), cost_per_trade(cost) {}

    std::string repr() {
        std::string cost_per_trade_str = std::to_string(cost_per_trade);
        return "PerFutureTrade(cost_per_trade=" + cost_per_trade_str + ")";
    }
};

class PerDollar : public EquityCommissionModel {
private:
    float cost_per_dollar;

public:
    static constexpr float DEFAULT_PER_DOLLAR_COST = 0.0015;  // 0.15 cents per dollar

    PerDollar(float cost = DEFAULT_PER_DOLLAR_COST) : cost_per_dollar(cost) {}

    std::string repr() {
        return "PerDollar(cost_per_dollar=" + std::to_string(cost_per_dollar) + ")";
    }

    float calculate(float price, float amount) {
        float cost_per_share = price * cost_per_dollar;
        return std::abs(amount) * cost_per_share;
    }
};