#include <string>
#include <vector>
#include <tuple>

class CancelPolicy; // Forward declaration, replace with actual class if available
class Asset; // Forward declaration, replace with actual class if available
class ExecutionStyle; // Forward declaration, replace with actual class if available
class BarData; // Forward declaration, replace with actual class if available

class Blotter {
public:
    Blotter(CancelPolicy* cancel_policy = nullptr)
            : cancel_policy_(cancel_policy ? cancel_policy : new NeverCancel()),
              current_dt_(nullptr) {}

    void set_date(std::string dt) {
        current_dt_ = dt;
    }

    virtual std::string order(Asset* asset, int amount, ExecutionStyle* style, std::string order_id = "") = 0;

    std::vector<std::string> batch_order(std::vector<std::tuple<Asset*, int, ExecutionStyle*, std::string>> order_arg_lists) {
        std::vector<std::string> order_ids;
        for (auto& order_args : order_arg_lists) {
            order_ids.push_back(order(std::get<0>(order_args), std::get<1>(order_args), std::get<2>(order_args), std::get<3>(order_args)));
        }
        return order_ids;
    }
    virtual void cancel(int order_id, bool relay_status = true) = 0;
    virtual void cancel_all_orders_for_asset(Asset* asset, bool warn = false, bool relay_status = true) = 0;
    virtual void execute_cancel_policy(std::string event) = 0;
    virtual void reject(int order_id, std::string reason = "") = 0;
    virtual void hold(int order_id, std::string reason = "") = 0;
    virtual void process_splits(std::vector<std::tuple<Asset*, double>> splits) = 0;
    virtual std::tuple<std::vector<Transaction*>, std::vector<Commission*>, std::vector<Order*>> get_transactions(BarData* bar_data) = 0;
    virtual void prune_orders(std::vector<Order*> closed_orders) = 0;

private:
    CancelPolicy* cancel_policy_;
    std::string current_dt_;
};

#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <stdexcept>
#include <algorithm>

class Asset; // Forward declaration, replace with actual class if available
class ExecutionStyle; // Forward declaration, replace with actual class if available
class Order; // Forward declaration, replace with actual class if available
class BarData; // Forward declaration, replace with actual class if available
class CancelPolicy; // Forward declaration, replace with actual class if available

class SimulationBlotter : public Blotter {
public:
    SimulationBlotter(
            std::unique_ptr<SlippageModel> equity_slippage = nullptr,
            std::unique_ptr<SlippageModel> future_slippage = nullptr,
            std::unique_ptr<CommissionModel> equity_commission = nullptr,
            std::unique_ptr<CommissionModel> future_commission = nullptr,
            CancelPolicy* cancel_policy = nullptr)
            : Blotter(cancel_policy),
              equity_slippage_(equity_slippage ? std::move(equity_slippage) : std::make_unique<FixedBasisPointsSlippage>()),
              future_slippage_(future_slippage ? std::move(future_slippage) : std::make_unique<VolatilityVolumeShare>(DEFAULT_FUTURE_VOLUME_SLIPPAGE_BAR_LIMIT)),
              equity_commission_(equity_commission ? std::move(equity_commission) : std::make_unique<PerShare>()),
              future_commission_(future_commission ? std::move(future_commission) : std::make_unique<PerContract>(DEFAULT_PER_CONTRACT_COST, FUTURE_EXCHANGE_FEES_BY_SYMBOL)) {}

    std::string order(Asset* asset, int amount, ExecutionStyle* style, std::string order_id = "") override {
        if (amount == 0) {
            return "";
        } else if (amount > max_shares_) {
            throw std::overflow_error("Can't order more than " + std::to_string(max_shares_) + " shares");
        }

        bool is_buy = amount > 0;
        auto order = std::make_unique<Order>(current_dt_, asset, amount, style->get_stop_price(is_buy), style->get_limit_price(is_buy), order_id);

        open_orders_[order->asset].push_back(order.get());
        orders_[order->id] = std::move(order);
        new_orders_.push_back(orders_[order->id].get());

        return order->id;
    }

    void cancel(std::string order_id, bool relay_status = true) override {
        if (orders_.find(order_id) == orders_.end()) {
            return;
        }

        Order* cur_order = orders_[order_id].get();

        if (cur_order->open) {
            auto& order_list = open_orders_[cur_order->asset];
            order_list.erase(std::remove(order_list.begin(), order_list.end(), cur_order), order_list.end());
            new_orders_.erase(std::remove(new_orders_.begin(), new_orders_.end(), cur_order), new_orders_.end());
            cur_order->cancel();
            cur_order->dt = current_dt_;
            if (relay_status) {
                new_orders_.push_back(cur_order);
            }
        }
    }

    void cancel_all_orders_for_asset(Asset* asset, bool warn = false, bool relay_status = true) override {
        auto& orders = open_orders_[asset];
        for (auto& order : orders) {
            cancel(order->id, relay_status);
        }
        orders.clear();
    }

    void execute_cancel_policy(std::string event) override {
        if (cancel_policy_->should_cancel(event)) {
            bool warn = cancel_policy_->warn_on_cancel();
            for (auto& asset_orders_pair : open_orders_) {
                cancel_all_orders_for_asset(asset_orders_pair.first, warn, false);
            }
        }
    }

    void reject(std::string order_id, std::string reason = "") override {
        if (orders_.find(order_id) == orders_.end()) {
            return;
        }

        Order* cur_order = orders_[order_id].get();

        auto& order_list = open_orders_[cur_order->asset];
        order_list.erase(std::remove(order_list.begin(), order_list.end(), cur_order), order_list.end());

        new_orders_.erase(std::remove(new_orders_.begin(), new_orders_.end(), cur_order), new_orders_.end());
        cur_order->reject(reason);
        cur_order->dt = current_dt_;

        new_orders_.push_back(cur_order);
    }

    void hold(std::string order_id, std::string reason = "") override {
        if (orders_.find(order_id) == orders_.end()) {
            return;
        }

        Order* cur_order = orders_[order_id].get();

        if (cur_order->open) {
            new_orders_.erase(std::remove(new_orders_.begin(), new_orders_.end(), cur_order), new_orders_.end());
            cur_order->hold(reason);
            cur_order->dt = current_dt_;

            new_orders_.push_back(cur_order);
        }
    }

    void process_splits(std::vector<std::pair<Asset*, double>> splits) override {
        for (auto& [asset, ratio] : splits) {
            if (open_orders_.find(asset) == open_orders_.end()) {
                continue;
            }
            auto& orders_to_modify = open_orders_[asset];
            for (auto& order : orders_to_modify) {
                order->handle_split(ratio);
            }
        }
    }

    std::tuple<std::vector<Transaction>, std::vector<Commission>, std::vector<Order*>> get_transactions(BarData* bar_data) override {
        std::vector<Order*> closed_orders;
        std::vector<Transaction> transactions;
        std::vector<Commission> commissions;

        if (!open_orders_.empty()) {
            for (auto& [asset, asset_orders] : open_orders_) {
                SlippageModel* slippage = slippage_models_[typeid(*asset)];

                for (auto& [order, txn] : slippage->simulate(bar_data, asset, asset_orders)) {
                    CommissionModel* commission = commission_models_[typeid(*asset)];
                    double additional_commission = commission->calculate(order, txn);

                    if (additional_commission > 0) {
                        commissions.push_back({order->asset, order, additional_commission});
                    }

                    order->filled += txn.amount;
                    order->commission += additional_commission;

                    order->dt = txn.dt;

                    transactions.push_back(txn);

                    if (!order->open) {
                        closed_orders.push_back(order);
                    }
                }
            }
        }

        return {transactions, commissions, closed_orders};
    }

    void prune_orders(std::vector<Order*> closed_orders) override {
        for (auto& order : closed_orders) {
            Asset* asset = order->asset;
            auto& asset_orders = open_orders_[asset];
            asset_orders.erase(std::remove(asset_orders.begin(), asset_orders.end(), order), asset_orders.end());
        }

        for (auto it = open_orders_.begin(); it != open_orders_.end();) {
            if (it->second.empty()) {
                it = open_orders_.erase(it);
            } else {
                ++it;
            }
        }
    }

private:
    std::unordered_map<Asset*, std::vector<Order*>> open_orders_;
    std::unordered_map<std::string, std::unique_ptr<Order>> orders_;
    std::vector<Order*> new_orders_;
    int max_shares_ = 1e11;
    std::unordered_map<std::type_index, std::unique_ptr<SlippageModel>> slippage_models_;
    std::unordered_map<std::type_index, std::unique_ptr<CommissionModel>> commission_models_;
};
