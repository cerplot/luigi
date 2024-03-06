#ifndef TRADINGALGO_H
#define TRADINGALGO_H
#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>
#include <map>
#include <string>
#include <functional>
#include <stdexcept>
#include <map>
#include <string>
#include <functional>
#include <string>
#include <map>
#include <string>
#include <ctime>
#include <stdexcept>
#include <cassert>
#include <variant>
#include <map>
#include <string>
#include <ctime>
#include <stdexcept>
#include <cmath>
#include <stdexcept>
#include <cassert>
#include <variant>
#include <map>
#include <string>
#include <ctime>

#include "Asset.h" // Assuming Asset.h is the header file for Asset class
#include "Order.h" // Assuming Order.h is the header file for Order class
#include "Pipeline.h" // Assuming Pipeline.h is the header file for Pipeline class
#include "Domain.h" // Assuming Domain.h is the header file for Domain class

class TradingAlgorithm {
private:
    std::vector<std::string> trading_controls;
    std::vector<std::string> account_controls;
    std::map<std::string, std::string> recorded_vars;
    std::map<std::string, std::string> namespace_;
    std::string platform;
    std::string logger;
    std::string data_portal;
    std::string asset_finder;
    std::string benchmark_returns;
    std::string sim_params;
    std::string trading_calendar;
    std::string metrics_tracker;
    std::string _last_sync_time;
    std::string _metrics_set;
    std::string _pipelines;
    std::string _pipeline_cache;
    std::string blotter;
    std::string _symbol_lookup_date;
    std::string algoscript;
    std::string _initialize;
    std::string _before_trading_start;
    std::string _analyze;
    bool _in_before_trading_start;
    std::string event_manager;
    std::string _handle_data;
    std::map<std::string, std::string> initialize_kwargs;
    std::string benchmark_sid;
    std::map<std::string, std::string> capital_changes;
    std::map<std::string, std::string> capital_change_deltas;
    std::string restrictions;
    bool initialized;
public:
    TradingAlgorithm();
    TradingAlgorithm(std::any sim_params,
                     std::any data_portal = nullptr,
                     std::any asset_finder = nullptr,
                     std::unordered_map<std::string, std::any> namespace_ = {},
                     std::string script = "",
                     std::string algo_filename = "",
                     std::function<void()> initialize = nullptr,
                     std::function<void()> handle_data = nullptr,
                     std::function<void()> before_trading_start = nullptr,
                     std::function<void()> analyze = nullptr,
                     std::any trading_calendar = nullptr,
                     std::any metrics_set = nullptr,
                     std::any blotter = nullptr,
                     std::string platform="tengine",
                     std::unordered_map<std::string, std::any> capital_changes = {},
                     std::function<std::any()> get_pipeline_loader = nullptr,
                     std::function<std::any()> create_event_context = nullptr,
                     std::unordered_map<std::string, std::any> initialize_kwargs = {});

    ~TradingAlgorithm();

    void init_engine(std::function<SimplePipelineEngine * ()> get_loader);
    void initialize();
    void before_trading_start(Data data);
    void handle_data(Data data);
    void analyze(Performance perf);
    std::string repr();
    void _create_clock();
    BenchmarkSource _create_benchmark_source();
    MetricsTracker _create_metrics_tracker();
    void _create_generator(SimParams sim_params);
    void compute_eager_pipelines();
    Generator *get_generator();
    std::vector<Performance> run(DataPortal *data_portal = nullptr);
    std::vector<Performance> _create_daily_stats(std::vector<Performance> perfs);
    std::vector<std::map<std::string, double>> calculate_capital_changes();
    std::variant<std::string, std::map<std::string, std::variant<std::string, double, std::string>>> get_environment(std::string field = "platform");
    PandasRequestsCSV *fetch_csv();
    void add_event(EventRule rule, std::function<void(Context, Data)> callback);
    void schedule_function();
    void record(std::map<std::string, double> kwargs);
    void set_benchmark(Asset *benchmark);
    ContinuousFuture *continuous_future();
    Equity *symbol(std::string symbol_str, std::string country_code = "");
    std::vector<Equity *> symbols(std::vector<std::string> args, std::string country_code = "");
    Asset *sid(int sid);
    Future *future_symbol(std::string symbol);
    double _calculate_order_value_amount(Asset *asset, double value);
    bool _can_order_asset(Asset *asset);
    std::string order(Asset *asset, int amount, double limit_price = 0.0, double stop_price = 0.0);
    std::pair<int, ExecutionStyle *> _calculate_order(Asset *asset, int amount, double limit_price = 0.0, double stop_price = 0.0);
    static int round_order(int amount);
    void validate_order_params(Asset *asset, int amount, double limit_price, double stop_price);
    static ExecutionStyle * __convert_order_params_for_blotter(Asset *asset, double limit_price, double stop_price);
    std::string order_value(Asset *asset, double value, double limit_price = 0.0, double stop_price = 0.0);
    std::map<std::string, double> recorded_vars();
    void _sync_last_sale_prices(std::tm *dt = nullptr);
    Portfolio portfolio();
    Account account();
    void set_logger(std::string logger);
    void on_dt_changed(std::tm *dt);
    std::tm *get_datetime(std::string tz = "");
    void set_slippage(EquitySlippageModel *us_equities = nullptr, FutureSlippageModel *us_futures = nullptr);
    void set_commission(EquityCommissionModel *us_equities = nullptr);
    void set_cancel_policy(CancelPolicy *cancel_policy);
    void set_symbol_lookup_date(std::tm *dt);
    void order_percent(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0);
    void order_target(Asset *asset, int target, double limit_price = 0.0, double stop_price = 0.0);
    void order_target_value(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0);
    void order_target_percent(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0);
    void batch_market_order(std::map<Asset *, int> share_counts);
    std::map<Asset *, std::vector<Order *>> get_open_orders(Asset *asset = nullptr);
    Order *get_order(std::string order_id);
    void cancel_order(std::variant<std::string, Order *> order_param);
    void register_account_control(AccountControl *control);
    void validate_account_controls();
    void set_max_leverage(double max_leverage);
    void set_min_leverage(double min_leverage, std::tm *grace_period);
    void register_trading_control(TradingControl *control);
    void set_max_position_size(Asset *asset = nullptr, int max_shares = 0, double max_notional = 0.0);
    void set_max_order_size(Asset *asset = nullptr, int max_shares = 0, double max_notional = 0.0);
    void set_max_order_count(int max_count, std::string on_error = "fail");
    void set_do_not_order_list(std::vector<Asset *> restricted_list, std::string on_error = "fail");
    void set_asset_restrictions(Restrictions *restrictions, std::string on_error = "fail");
    void set_long_only(std::string on_error = "fail");
    Pipeline *attach_pipeline(Pipeline *pipeline, std::string name, int chunks = 0, bool eager = true);
    std::map<std::string, std::vector<Asset *>> pipeline_output(std::string name);
    std::map<std::string, std::vector<Asset *>> _pipeline_output(Pipeline *pipeline, int chunks, std::string name);
    std::map<std::string, std::vector<Asset *>> run_pipeline(Pipeline *pipeline, std::tm *start_session, int chunksize);
    static std::string default_pipeline_domain(std::string calendar);
    static std::string default_fetch_csv_country_code(std::string calendar);
    static std::vector<std::function<void()>> all_api_methods();
};

#endif // TRADINGALGO_H