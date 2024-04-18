#include <cmath>
#include <ctime>
#include <string>
#include <vector>
#include <map>

class Position {
private:
    Asset* asset;
    int amount;
    double cost_basis;
    double last_sale_price;
    std::time_t last_sale_date;

public:
    Position(Asset* asset, int amount = 0, double cost_basis = 0.0, double last_sale_price = 0.0, std::time_t last_sale_date = 0)
            : asset(asset), amount(amount), cost_basis(cost_basis), last_sale_price(last_sale_price), last_sale_date(last_sale_date) {}

    // asset - the asset held in this position
    // amount -whole number of shares in the position
    // last_sale_price - price at last sale of the asset on the exchange
    // cost_basis - average price at which the shares in the position were acquired

    std::map<std::string, double> earn_dividend(Dividend dividend) {
        return {{"amount", amount * dividend.amount}};
    }

    std::map<std::string, double> earn_stock_dividend(StockDividend stock_dividend) {
        return {
                {"payment_asset", stock_dividend.payment_asset},
                {"share_count", std::floor(this->amount * stock_dividend.ratio)}
        };
    }

    double handle_split(Asset* asset, double ratio) {
        if (this->asset != asset) {
            throw std::invalid_argument("Updating split with the wrong asset!");
        }

        // adjust the # of shares by the ratio
        double raw_share_count = amount / ratio;

        // e.g., 33
        int full_share_count = std::floor(raw_share_count);

        // e.g., 0.333
        double fractional_share_count = raw_share_count - full_share_count;

        // adjust the cost basis to the nearest cent, e.g., 60.0
        double new_cost_basis = std::round(this->cost_basis * ratio * 100) / 100;

        this->cost_basis = new_cost_basis;
        this->amount = full_share_count;

        double return_cash = std::round(fractional_share_count * new_cost_basis * 100) / 100;

        std::cout << "after split: " << this->to_string() << std::endl;
        std::cout << "returning cash: " << return_cash << std::endl;

        // return the leftover cash, which will be converted into cash
        // (rounded to the nearest cent)
        return return_cash;
    }

    void update(Transaction txn) {
        if (asset != txn.asset) {
            throw std::invalid_argument("Updating position with txn for a different asset");
        }

        int total_shares = amount + txn.amount;

        if (total_shares == 0) {
            cost_basis = 0.0;
        } else {
            int prev_direction = std::copysign(1, amount);
            int txn_direction = std::copysign(1, txn.amount);

            if (prev_direction != txn_direction) {
                // we're covering a short or closing a position
                if (std::abs(txn.amount) > std::abs(amount)) {
                    // we've closed the position and gone short
                    // or covered the short position and gone long
                    this->cost_basis = txn.price;
                }
            } else {
                double prev_cost = this->cost_basis * this->amount;
                double txn_cost = txn.amount * txn.price;
                double total_cost = prev_cost + txn_cost;
                this->cost_basis = total_cost / total_shares;
            }

            // Update the last sale price if txn is the best data we have so far
            if (this->last_sale_date == 0 || txn.dt > this->last_sale_date) {
                this->last_sale_price = txn.price;
                this->last_sale_date = txn.dt;
            }
        }

        this->amount = total_shares;
    }

    void adjust_commission_cost_basis(Asset* asset, double cost) {
        if (asset != this->asset) {
            throw std::invalid_argument("Updating a commission for a different asset?");
        }
        if (cost == 0.0) {
            return;
        }
        // If we no longer hold this position, there is no cost basis to adjust.
        if (amount == 0) {
            return;
        }

        double prev_cost = cost_basis * amount;
        double cost_to_use;
        if (dynamic_cast<Future*>(asset) != nullptr) { // Future is a subclass of Asset
            cost_to_use = cost / asset->price_multiplier; // price_multiplier is a public member of Asset
        } else {
            cost_to_use = cost;
        }
        double new_cost = prev_cost + cost_to_use;
        this->cost_basis = new_cost / amount;
    }

    std::string to_string() {
        std::ostringstream oss;
        oss << "Asset: " << asset->to_string() // Assuming Asset class has a to_string method
            << ", Amount: " << amount
            << ", Cost Basis: " << cost_basis
            << ", Last Sale Price: " << last_sale_price;
        return oss.str();
    }

    std::map<std::string, double> to_dict() {
        return {
                {"sid", asset},
                {"amount", amount},
                {"cost_basis", cost_basis},
                {"last_sale_price", last_sale_price}
        };
    }
};