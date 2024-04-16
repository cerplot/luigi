#include <vector>
#include <map>
#include <string>
#include <algorithm>

class AlgorithmSimulator {
public:
    AlgorithmSimulator(Algo* algo, SimParams* sim_params, DataPortal* data_portal, Clock* clock, BenchmarkSource* benchmark_source, Restrictions* restrictions)
            : algo(algo), sim_params(sim_params), data_portal(data_portal), clock(clock), benchmark_source(benchmark_source), restrictions(restrictions) {
        // Initialization logic here
    }
    std::string get_simulation_dt() {
        return simulation_dt;
    }
    std::vector<CapitalChangePacket> AlgorithmSimulator::every_bar(std::string dt_to_use) {
        std::vector<CapitalChangePacket> capital_change_packets;

        // Calculate minute capital changes
        std::vector<CapitalChange> capital_changes = this->calculate_minute_capital_changes(dt_to_use);
        for (auto& capital_change : capital_changes) {
            capital_change_packets.push_back(CapitalChangePacket(capital_change));
        }

        this->simulation_dt = dt_to_use;
        this->algo->on_dt_changed(dt_to_use);

        Blotter* blotter = this->algo->blotter;

        // Handle any transactions and commissions coming out new orders
        // placed in the last bar
        auto [new_transactions, new_commissions, closed_orders] = blotter->get_transactions(this->current_data);

        blotter->prune_orders(closed_orders);

        for (auto& transaction : new_transactions) {
            this->metrics_tracker->process_transaction(transaction);

            // since this order was modified, record it
            Order order = blotter->orders[transaction.order_id];
            this->metrics_tracker->process_order(order);
        }

        for (auto& commission : new_commissions) {
            this->metrics_tracker->process_commission(commission);
        }

        this->algo->event_manager->handle_data(this->algo, this->current_data, dt_to_use);

        // grab any new orders from the blotter, then clear the list.
        // this includes cancelled orders.
        std::vector<Order> new_orders = blotter->new_orders;
        blotter->new_orders.clear();

        // if we have any new orders, record them so that we know
        // in what perf period they were placed.
        for (auto& new_order : new_orders) {
            this->metrics_tracker->process_order(new_order);
        }

        return capital_change_packets;
    }
    void transform() {
        Algo* algo = algo;
        MetricsTracker* metrics_tracker = algo->metrics_tracker;
        double emission_rate = metrics_tracker->emission_rate;
        std::vector<Message> messages;

        // Define the function pointers
        void (Blotter::*execute_order_cancellation_policy)();
        std::vector<CapitalChange> (AlgorithmSimulator::*calculate_minute_capital_changes)(std::string);

        if (this->algo->data_frequency == "minute") {
            execute_order_cancellation_policy = &Blotter::execute_cancel_policy;
            calculate_minute_capital_changes = &AlgorithmSimulator::calculate_minute_capital_changes;
        } else if (this->algo->data_frequency == "daily") {
            execute_order_cancellation_policy = &Blotter::execute_daily_cancel_policy;
            calculate_minute_capital_changes = &AlgorithmSimulator::calculate_no_capital_changes;
        } else {
            execute_order_cancellation_policy = &Blotter::do_nothing;
            calculate_minute_capital_changes = &AlgorithmSimulator::calculate_no_capital_changes;
        }

        for (auto dt_action : this->clock->timestamps_actions) {
            std::string dt = dt_action.first;
            int action = dt_action.second;

            if (action == BAR) {
                std::vector<CapitalChangePacket> capital_change_packets = (this->*calculate_minute_capital_changes)(dt);
                for (auto& packet : capital_change_packets) {
                    messages.push_back(Message(packet));
                }
            } else if (action == SESSION_START) {
                std::vector<CapitalChangePacket> capital_change_packets = once_a_day(dt);
                for (auto& packet : capital_change_packets) {
                    messages.push_back(Message(packet));
                }
            } else if (action == SESSION_END) {
                // End of the session.
                std::map<std::string, Position> positions = this->metrics_tracker->positions;
                std::vector<Asset> position_assets = this->algo->asset_finder->retrieve_all(positions);
                cleanup_expired_assets(dt, position_assets);

                (this->algo->blotter->*execute_order_cancellation_policy)();
                this->algo->validate_account_controls();

                messages.push_back(get_daily_message(dt, this->algo, this->metrics_tracker));
            } else if (action == BEFORE_TRADING_START_BAR) {
                this->simulation_dt = dt;
                this->algo->on_dt_changed(dt);
                this->algo->before_trading_start(this->current_data);
            } else if (action == MINUTE_END) {
                messages.push_back(get_minute_message(dt, this->algo, this->metrics_tracker));
            }
        }

        Message risk_message = this->metrics_tracker->handle_simulation_end(this->data_portal);
        messages.push_back(risk_message);

        return messages;
    }
    std::vector<CapitalChangePacket> once_a_day(std::string midnight_dt) {
        std::vector<CapitalChangePacket> capital_change_packets;

        // Calculate capital changes
        std::vector<CapitalChange> capital_changes = algo->calculate_capital_changes(midnight_dt, this->emission_rate, true);
        for (auto& capital_change : capital_changes) {
            capital_change_packets.push_back(CapitalChangePacket(capital_change));
        }
        simulation_dt = midnight_dt;
        algo->on_dt_changed(midnight_dt);

        metrics_tracker->handle_market_open(midnight_dt, this->data_portal);

        // Handle any splits that impact any positions or any open orders
        std::set<Asset> assets_we_care_about;
        for (auto& position : this->metrics_tracker->positions) {
            assets_we_care_about.insert(position.first);
        }
        for (auto& order : this->algo->blotter->open_orders) {
            assets_we_care_about.insert(order.first);
        }

        if (!assets_we_care_about.empty()) {
            std::map<Asset, Split> splits = data_portal->get_splits(assets_we_care_about, midnight_dt);
            if (!splits.empty()) {
                algo->blotter->process_splits(splits);
                metrics_tracker->handle_splits(splits);
            }
        }

        return capital_change_packets;
    }

    void on_exit() {
        // Remove references to algo, data portal, et al. to break cycles
        // and ensure deterministic cleanup of these objects when the
        // simulation finishes.
        algo = nullptr;
        benchmark_source = nullptr;
        current_data = nullptr;
        data_portal = nullptr;
    }

    void cleanup_expired_assets(std::string dt, std::vector<Asset> position_assets) {
        Algo* algo = this->algo;

        // Function to check if asset is past its auto close date
        auto past_auto_close_date = [dt](Asset asset) {
            std::string acd = asset.auto_close_date;
            if (!acd.empty()) {
                acd = tz_localize(acd, dt);
            }
            return !acd.empty() && acd <= dt;
        };

        // Remove positions in any assets that have reached their auto_close date
        std::vector<Asset> assets_to_clear;
        for (auto& asset : position_assets) {
            if (past_auto_close_date(asset)) {
                assets_to_clear.push_back(asset);
            }
        }

        MetricsTracker* metrics_tracker = algo->metrics_tracker;
        DataPortal* data_portal = this->data_portal;
        for (auto& asset : assets_to_clear) {
            metrics_tracker->process_close_position(asset, dt, data_portal);
        }

        // Remove open orders for any assets that have reached their auto close date
        Blotter* blotter = algo->blotter;
        std::vector<Asset> assets_to_cancel;
        for (auto& asset : blotter->open_orders) {
            if (past_auto_close_date(asset)) {
                assets_to_cancel.push_back(asset);
            }
        }

        for (auto& asset : assets_to_cancel) {
            blotter->cancel_all_orders_for_asset(asset);
        }

        // Process cancelled orders
        std::vector<Order> new_orders_copy = blotter->new_orders;
        for (auto& order : new_orders_copy) {
            if (order.status == ORDER_STATUS::CANCELLED) {
                metrics_tracker->process_order(order);
                blotter->new_orders.erase(std::remove(blotter->new_orders.begin(), blotter->new_orders.end(), order), blotter->new_orders.end());
            }
        }
    }

    Message get_daily_message(std::string dt, Algo* algo, MetricsTracker* metrics_tracker) {
        std::map<std::string, double> recorded_vars = algo->recorded_vars;
        Message perf_message = metrics_tracker->handle_market_close(dt, this->data_portal);
        perf_message["daily_perf"]["recorded_vars"] = recorded_vars;
        return perf_message;
    }

    Message  get_minute_message(std::string dt, Algo* algo, MetricsTracker* metrics_tracker) {
        std::map<std::string, double> rvars = algo->recorded_vars;
        Message minute_message = metrics_tracker->handle_minute_close(dt, this->data_portal);
        minute_message["minute_perf"]["recorded_vars"] = rvars;
        return minute_message;
    }

private:
    Algo* algo;
    SimParams* sim_params;
    DataPortal* data_portal;
    Clock* clock;
    BenchmarkSource* benchmark_source;
    Restrictions* restrictions;

    void handle_event(std::string dt) {
        // Handle event at timestamp dt
        // This is a simplified version, actual implementation will depend on your specific requirements
    }
};