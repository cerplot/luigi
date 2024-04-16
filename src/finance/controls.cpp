#include <iostream>
#include <string>
#include <map>
#include <stdexcept>

class TradingControlViolation : public std::runtime_error {
public:
    TradingControlViolation(const std::string& message) : std::runtime_error(message) {}
};

class TradingControl {
public:
    TradingControl(std::string on_error, std::map<std::string, std::string> fail_args)
            : on_error(on_error), fail_args(fail_args) {}

    virtual void validate(std::string asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) = 0;

    void handle_violation(std::string asset, double amount, std::string datetime, std::string metadata = "") {
        std::string constraint = _constraint_msg(metadata);

        if (on_error == "fail") {
            throw TradingControlViolation("Order for " + std::to_string(amount) + " shares of " + asset + " at " + datetime + " violates trading constraint " + constraint);
        } else if (on_error == "log") {
            std::cerr << "Order for " << amount << " shares of " << asset << " at " << datetime << " violates trading constraint " << constraint << std::endl;
        }
    }

    std::string _constraint_msg(std::string metadata) {
        std::string constraint = repr();
        if (!metadata.empty()) {
            constraint = constraint + " (Metadata: " + metadata + ")";
        }
        return constraint;
    }

    std::string repr() {
        std::string attrs = "";
        for (const auto& kv : fail_args) {
            attrs += kv.first + "=" + kv.second + ", ";
        }
        attrs = attrs.substr(0, attrs.size() - 2);  // remove trailing comma and space
        return "TradingControl(" + attrs + ")";
    }

protected:
    std::string on_error;
    std::map<std::string, std::string> fail_args;
};

#include <ctime>

class MaxOrderCount : public TradingControl {
public:
    MaxOrderCount(std::string on_error, int max_count)
            : TradingControl(on_error, {{"max_count", std::to_string(max_count)}}), max_count(max_count), orders_placed(0), current_date("") {}

    void validate(std::string asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) override {
        // Convert algo_datetime to date
        std::string algo_date = algo_datetime.substr(0, algo_datetime.find(" "));

        // Reset order count if it's a new day
        if (!current_date.empty() && current_date != algo_date) {
            orders_placed = 0;
        }
        current_date = algo_date;

        // Fail if we've already placed max_count orders today
        if (orders_placed >= max_count) {
            handle_violation(asset, amount, algo_datetime);
        }
        orders_placed++;
    }

private:
    int max_count;
    int orders_placed;
    std::string current_date;
};

class Restrictions {
public:
    virtual bool is_restricted(std::string asset, std::string algo_datetime) = 0;
};

class RestrictedListOrder : public TradingControl {
public:
    RestrictedListOrder(std::string on_error, Restrictions* restrictions)
            : TradingControl(on_error, {}), restrictions(restrictions) {}

    void validate(std::string asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) override {
        // Fail if the asset is in the restricted list
        if (restrictions->is_restricted(asset, algo_datetime)) {
            handle_violation(asset, amount, algo_datetime);
        }
    }

private:
    Restrictions* restrictions;
};


class MaxOrderSize : public TradingControl {
public:
    MaxOrderSize(std::string on_error, std::string asset = "", int max_shares = -1, double max_notional = -1.0)
            : TradingControl(on_error, {{"asset", asset}, {"max_shares", std::to_string(max_shares)}, {"max_notional", std::to_string(max_notional)}}),
              asset(asset), max_shares(max_shares), max_notional(max_notional) {
        if (max_shares == -1 && max_notional == -1.0) {
            throw std::invalid_argument("Must supply at least one of max_shares and max_notional");
        }
        if (max_shares < 0) {
            throw std::invalid_argument("max_shares cannot be negative.");
        }
        if (max_notional < 0) {
            throw std::invalid_argument("max_notional must be positive.");
        }
    }

    void validate(std::string asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) override {
        if (!this->asset.empty() && this->asset != asset) {
            return;
        }

        if (max_shares != -1 && abs(amount) > max_shares) {
            handle_violation(asset, amount, algo_datetime);
        }

        double current_asset_price = std::stod(algo_current_data); // assuming algo_current_data is the price
        double order_value = amount * current_asset_price;

        if (max_notional != -1.0 && abs(order_value) > max_notional) {
            handle_violation(asset, amount, algo_datetime);
        }
    }

private:
    std::string asset;
    int max_shares;
    double max_notional;
};

class MaxPositionSize : public TradingControl {
public:
    MaxPositionSize(std::string on_error, std::string asset = "", int max_shares = -1, double max_notional = -1.0)
            : TradingControl(on_error, {{"asset", asset}, {"max_shares", std::to_string(max_shares)}, {"max_notional", std::to_string(max_notional)}}),
              asset(asset), max_shares(max_shares), max_notional(max_notional) {
        if (max_shares == -1 && max_notional == -1.0) {
            throw std::invalid_argument("Must supply at least one of max_shares and max_notional");
        }
        if (max_shares < 0) {
            throw std::invalid_argument("max_shares cannot be negative.");
        }
        if (max_notional < 0) {
            throw std::invalid_argument("max_notional must be positive.");
        }
    }

    void validate(std::string asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) override {
        if (!this->asset.empty() && this->asset != asset) {
            return;
        }

        double current_share_count = std::stod(portfolio); // assuming portfolio is the current share count
        double shares_post_order = current_share_count + amount;

        if (max_shares != -1 && abs(shares_post_order) > max_shares) {
            handle_violation(asset, amount, algo_datetime);
        }

        double current_price = std::stod(algo_current_data); // assuming algo_current_data is the price
        double value_post_order = shares_post_order * current_price;

        if (max_notional != -1.0 && abs(value_post_order) > max_notional) {
            handle_violation(asset, amount, algo_datetime);
        }
    }

private:
    std::string asset;
    int max_shares;
    double max_notional;
};

class Asset {
public:
    virtual std::string get_start_date() = 0;
    virtual std::string get_end_date() = 0;
};

class AssetDateBounds : public TradingControl {
public:
    AssetDateBounds(std::string on_error)
            : TradingControl(on_error, {}) {}

    void validate(Asset* asset, double amount, std::string portfolio, std::string algo_datetime, std::string algo_current_data) override {
        // If the order is for 0 shares, then silently pass through.
        if (amount == 0) {
            return;
        }

        std::string normalized_algo_dt = algo_datetime.substr(0, algo_datetime.find(" ")); // assuming algo_datetime is in "YYYY-MM-DD HH:MM:SS" format

        // Fail if the algo is before this Asset's start_date
        std::string asset_start_date = asset->get_start_date();
        if (!asset_start_date.empty()) {
            std::string normalized_start = asset_start_date.substr(0, asset_start_date.find(" "));
            if (normalized_algo_dt < normalized_start) {
                std::map<std::string, std::string> metadata = {{"asset_start_date", normalized_start}};
                handle_violation("asset", amount, algo_datetime, "Metadata: asset_start_date=" + normalized_start);
            }
        }

        // Fail if the algo has passed this Asset's end_date
        std::string asset_end_date = asset->get_end_date();
        if (!asset_end_date.empty()) {
            std::string normalized_end = asset_end_date.substr(0, asset_end_date.find(" "));
            if (normalized_algo_dt > normalized_end) {
                std::map<std::string, std::string> metadata = {{"asset_end_date", normalized_end}};
                handle_violation("asset", amount, algo_datetime, "Metadata: asset_end_date=" + normalized_end);
            }
        }
    }
};

#include <stdexcept>
#include <string>
#include <map>

class AccountControlViolation : public std::runtime_error {
public:
    AccountControlViolation(const std::string& message) : std::runtime_error(message) {}
};

class AccountControl {
public:
    AccountControl(std::map<std::string, std::string> fail_args)
            : fail_args(fail_args) {}

    virtual void validate(std::string portfolio, std::string account, std::string algo_datetime, std::string algo_current_data) = 0;

    void fail() {
        throw AccountControlViolation(repr());
    }

    std::string repr() {
        std::string attrs = "";
        for (const auto& kv : fail_args) {
            attrs += kv.first + "=" + kv.second + ", ";
        }
        attrs = attrs.substr(0, attrs.size() - 2);  // remove trailing comma and space
        return this->getClassName() + "(" + attrs + ")";
    }

protected:
    virtual std::string getClassName() = 0;
    std::map<std::string, std::string> fail_args;
};

class MaxLeverage : public AccountControl {
public:
    MaxLeverage(double max_leverage)
            : AccountControl({{"max_leverage", std::to_string(max_leverage)}}), max_leverage(max_leverage) {
        if (max_leverage < 0) {
            throw std::invalid_argument("max_leverage must be positive.");
        }
    }

    void validate(std::string portfolio, std::string account, std::string algo_datetime, std::string algo_current_data) override {
        double account_leverage = std::stod(account); // assuming account is the leverage

        // Fail if the leverage is greater than the allowed leverage
        if (account_leverage > max_leverage) {
            fail();
        }
    }

protected:
    std::string getClassName() override {
        return "MaxLeverage";
    }

private:
    double max_leverage;
};

#include <ctime>

class MinLeverage : public AccountControl {
public:
    MinLeverage(double min_leverage, std::string deadline)
            : AccountControl({{"min_leverage", std::to_string(min_leverage)}, {"deadline", deadline}}), min_leverage(min_leverage), deadline(deadline) {
        if (min_leverage < 0) {
            throw std::invalid_argument("min_leverage must be positive.");
        }
    }

    void validate(std::string portfolio, std::string account, std::string algo_datetime, std::string algo_current_data) override {
        double account_leverage = std::stod(account); // assuming account is the leverage

        // Fail if the leverage is less than the min leverage after the deadline
        if (algo_datetime > deadline && account_leverage < min_leverage) {
            fail();
        }
    }

protected:
    std::string getClassName() override {
        return "MinLeverage";
    }

private:
    double min_leverage;
    std::string deadline;
};

