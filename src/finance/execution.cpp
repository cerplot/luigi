#include <string>
#include <stdexcept>
#include <cmath>
class Asset;
class BadOrderParameters : public std::runtime_error {
public:
    explicit BadOrderParameters(const std::string& msg) : std::runtime_error(msg) {}
};
double consistent_round(double value) {
    return (value > 0.0) ? floor(value + 0.5) : ceil(value - 0.5);
}
void check_stoplimit_prices(double price, const std::string& label) {
    if (!std::isfinite(price)) {
        throw BadOrderParameters(
                "Attempted to place an order with a " + label + " price of " + std::to_string(price) + "."
        );
    }
    if (price < 0) {
        throw BadOrderParameters(
                "Can't place a " + label + " order with a negative price."
        );
    }
}
double asymmetric_round_price(double price, bool prefer_round_down, double tick_size, double diff = 0.95) {
    int precision = std::ceil(std::log10(1.0 / tick_size));
    int multiplier = tick_size * std::pow(10, precision);
    diff -= 0.5;  // shift the difference down
    diff *= std::pow(10, -precision);  // adjust diff to precision of tick size
    diff *= multiplier;  // adjust diff to value of tick_size

    // Subtracting an epsilon from diff to enforce the open-ness of the upper
    // bound on buys and the lower bound on sells.  Using the actual system
    // epsilon doesn't quite get there, so use a slightly less epsilon-ey value.
    double epsilon = std::numeric_limits<double>::epsilon() * 10;
    diff = diff - epsilon;

    // relies on rounding half away from zero, unlike numpy's bankers' rounding
    double rounded = tick_size * consistent_round(
            (price - (prefer_round_down ? diff : -diff)) / tick_size
    );
    if (std::abs(rounded) < std::numeric_limits<double>::epsilon()) {
        return 0.0;
    }
    return rounded;
}

class ExecutionStyle {
protected:
    std::string _exchange;

public:
    virtual double get_limit_price(bool is_buy) = 0;
    virtual double get_stop_price(bool is_buy) = 0;

    std::string get_exchange() const {
        return _exchange;
    }
};

class MarketOrder : public ExecutionStyle {
public:
    MarketOrder(const std::string& exchange = "") {
        _exchange = exchange;
    }
    double get_limit_price(bool _is_buy) override {
        return 0; // No limit price for market order
    }
    double get_stop_price(bool _is_buy) override {
        return 0; // No stop price for market order
    }
};

class LimitOrder : public ExecutionStyle {
private:
    double limit_price;
    Asset* asset;

public:
    LimitOrder(double limit_price, Asset* asset = nullptr, const std::string& exchange = "")
            : limit_price(limit_price), asset(asset) {
        _exchange = exchange;
        check_stoplimit_prices(limit_price, "limit");
    }

    double get_limit_price(bool is_buy) override {
        return asymmetric_round_price(
                limit_price,
                is_buy,
                (asset == nullptr ? 0.01 : asset->get_tick_size())
        );
    }

    double get_stop_price(bool _is_buy) override {
        return 0; // No stop price for limit order
    }
};

class StopOrder : public ExecutionStyle {
private:
    double stop_price;
    Asset* asset;

public:
    StopOrder(double stop_price, Asset* asset = nullptr, const std::string& exchange = "")
            : stop_price(stop_price), asset(asset) {
        _exchange = exchange;
        // check_stoplimit_prices function needs to be implemented
        check_stoplimit_prices(stop_price, "stop");
    }

    double get_limit_price(bool _is_buy) override {
        return 0; // No limit price for stop order
    }

    double get_stop_price(bool is_buy) override {
        // asymmetric_round_price function needs to be implemented
        return asymmetric_round_price(
                stop_price,
                !is_buy,
                (asset == nullptr ? 0.01 : asset->get_tick_size())
        );
    }
};

class StopLimitOrder : public ExecutionStyle {
private:
    double limit_price;
    double stop_price;
    // Assuming Asset is another class in your code
    Asset* asset;
public:
    StopLimitOrder(double limit_price, double stop_price, Asset* asset = nullptr, const std::string& exchange = "")
            : limit_price(limit_price), stop_price(stop_price), asset(asset) {
        _exchange = exchange;
        // check_stoplimit_prices function needs to be implemented
        check_stoplimit_prices(limit_price, "limit");
        check_stoplimit_prices(stop_price, "stop");
    }
    double get_limit_price(bool is_buy) override {
        // asymmetric_round_price function needs to be implemented
        return asymmetric_round_price(
                limit_price,
                is_buy,
                (asset == nullptr ? 0.01 : asset->get_tick_size())
        );
    }
    double get_stop_price(bool is_buy) override {
        // asymmetric_round_price function needs to be implemented
        return asymmetric_round_price(
                stop_price,
                !is_buy,
                (asset == nullptr ? 0.01 : asset->get_tick_size())
        );
    }
};
