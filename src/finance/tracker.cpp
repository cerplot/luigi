
class MetricsTracker {
public:
    MetricsTracker(
            std::string trading_calendar,
            std::string first_session,
            std::string last_session,
            double capital_base,
            std::string emission_rate,
            std::string data_frequency,
            std::string asset_finder,
            std::vector<std::string> metrics
    ) : emission_rate(emission_rate),
        trading_calendar(trading_calendar),
        first_session(first_session),
        last_session(last_session),
        capital_base(capital_base),
        asset_finder(asset_finder),
        current_session(first_session),
        session_count(0),
        ledger(sessions, capital_base, data_frequency)
    {
        // Initialize sessions and total_session_count
        // You need to implement sessions_in_range function in trading_calendar
        sessions = trading_calendar.sessions_in_range(first_session, last_session);
        total_session_count = sessions.size();

        // Initialize market_open and market_close
        // You need to implement _execution_open_and_close function
        std::tie(market_open, market_close) = _execution_open_and_close(trading_calendar, first_session);

        // Initialize progress function
        if (emission_rate == "minute") {
            progress = []() { return 1.0; };
        } else {
            progress = [this]() { return static_cast<double>(session_count) / total_session_count; };
        }

        // Initialize hooks
        for (const auto& hook : hooks) {
            std::vector<std::function<void()>> registered;
            for (const auto& metric : metrics) {
                // You need to implement getattr function
                auto impl = getattr(metric, hook);
                if (impl) {
                    registered.push_back(impl);
                }
            }
            hook_implementations[hook] = [registered]() {
                for (const auto& impl : registered) {
                    impl();
                }
            };
        }
    }

    void handle_start_of_simulation(BenchmarkSource& benchmark_source) {
        this->benchmark_source = benchmark_source;
        start_of_simulation(
                ledger,
                emission_rate,
                trading_calendar,
                sessions,
                benchmark_source
        );
    }

    Packet handle_minute_close(std::string dt, std::string data_portal) {
        // Implement the method here...
        Packet packet;
        return packet;
    }

    void handle_market_open(std::string session_label, std::string data_portal) {
        // Implement the method here...
    }

    Packet handle_market_close(std::string dt, std::string data_portal) {
        // Implement the method here...
        Packet packet;
        return packet;
    }

    Packet handle_simulation_end(std::string data_portal) {
        // Implement the method here...
        Packet packet;
        return packet;
    }

    // Implement the other methods here...

private:
    std::string emission_rate;
    std::string trading_calendar;
    std::string first_session;
    std::string last_session;
    double capital_base;
    std::string asset_finder;
    std::string current_session;
    std::string market_open;
    std::string market_close;
    int session_count;
    std::vector<std::string> sessions;
    int total_session_count;
    Ledger ledger;
    BenchmarkSource benchmark_source;
};
