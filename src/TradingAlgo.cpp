#include "TradingAlgo.h"


// Assuming BUILT_IN_DOMAINS is a vector of Domain objects
std::vector<Domain> BUILT_IN_DOMAINS = {...};

std::map<std::string, Domain> _DEFAULT_DOMAINS;
std::map<std::string, std::string> _DEFAULT_FETCH_CSV_COUNTRY_CODES;

for (const auto &domain: BUILT_IN_DOMAINS) {
    _DEFAULT_DOMAINS[domain.calendar_name] = domain;
    _DEFAULT_FETCH_CSV_COUNTRY_CODES[domain.calendar_name] = domain.
country_code;
}

// Include us_futures, which doesn't have a pipeline domain.
_DEFAULT_FETCH_CSV_COUNTRY_CODES["us_futures"] = "US";


class NoBenchmark : public std::runtime_error {
public:
    NoBenchmark() : std::runtime_error("Must specify either benchmark_sid or benchmark_returns.") {}
};

TradingAlgorithm::TradingAlgorithm(
        SimParams sim_params,
        AssetFinder* asset_finder = nullptr,
        std::map<std::string, std::function<void()>> namespace_ = {},
        Calendar* trading_calendar = nullptr,
        MetricsSet* metrics_set = nullptr,
        Blotter* blotter = nullptr,
        BlotterClass* blotter_class = nullptr,
        CancelPolicy* cancel_policy = nullptr,
        CapitalChanges* capital_changes = nullptr,
        std::function<ContextManager(BarData)> create_event_context = nullptr,
        std::map<std::string, std::any> initialize_kwargs = {}
) {
    // List of trading controls to be used to validate orders.
    trading_controls = {};
    // List of account controls to be checked on each tick.
    account_controls = {};
    recorded_vars = {};
    logger = getLogger();

    sim_params = sim_params;
    trading_calendar = sim_params->trading_calendar;

    metrics_tracker = nullptr;
    _last_sync_time = nullptr;
    _metrics_set = load_metrics_set("default");

    cancel_policy = cancel_policy != nullptr ? cancel_policy : new NeverCancel();
    blotter_class = blotter_class != nullptr ? blotter_class : new SimulationBlotter();
    blotter = new blotter_class(cancel_policy);

    event_manager = new EventManager(create_event_context);
    event_manager->add_event(new Event(
            new Always(),
            // We pass handle_data to get the unbound method.
            // We will explicitly pass the algorithm to bind it again.
            this->handle_data),
            true
    );

    if (sim_params->capital_base <= 0) {
        throw std::runtime_error("ZeroCapitalError");
    }

    initialized = false;
    initialize_kwargs = initialize_kwargs;
    // A dictionary of capital changes, keyed by timestamp, indicating the
    //target/delta of the capital changes, along with values
    capital_changes = new CapitalChanges();
    // A dictionary of the actual capital change deltas, keyed by timestamp
    capital_change_deltas = {};
    restrictions = new NoRestrictions();
}

void TradingAlgorithm::init_engine(std::function<SimplePipelineEngine * ()> get_loader) {

}

void TradingAlgorithm::initialize() {
    // initialize the algorithm
    // called once before the start of the simulation
}

void TradingAlgorithm::before_trading_start(Data data) {
    // called once before each trading day
    handle_non_market_minutes(data);
    _in_before_trading_start = False
}

void TradingAlgorithm::handle_data(Data data) {
    // called once for each event
}

void TradingAlgorithm::analyze(Performance perf) {
    // This function is called once at the end of the backtest
    // and is passed the context and the performance data.
}

std::string TradingAlgorithm::repr() {
    /* this does not yet represent a string that can be used
    to instantiate an exact copy of an algorithm.

    However, it is getting close, and provides some value as something
    that can be inspected interactively.
     */
    std::ostringstream repr;
    repr << "TradingAlgorithm("
         << "capital_base=" << capital_base << ", "
         << "sim_params=" << "" << ", "
         << "initialized=" << initialized << ", "
         << "slippage_models=" << blotter.slippage_models.repr() << ", "
         << "commission_models=" << blotter.commission_models.repr() << ", "
         << "blotter=" << blotter.repr() << ", "
         << "recorded_vars=" << recorded_vars.repr() << ")";
    return repr.str();
}

void TradingAlgorithm::_create_clock() {
    std::map<std::string, std::string> market_closes = trading_calendar.schedule[sim_params.sessions]["close"];
    std::map<std::string, std::string> market_opens = trading_calendar.first_minutes[sim_params.sessions];
    bool minutely_emission = false;

    minutely_emission = this->sim_params.emission_rate == "minute";

    std::map<std::string, std::string> execution_opens;
    std::map<std::string, std::string> execution_closes;

    if (this->trading_calendar.name == "us_futures") {
        execution_opens = trading_calendar.execution_time_from_open(market_opens);
        execution_closes = trading_calendar.execution_time_from_close(market_closes);
    } else {
        execution_opens = market_opens;
        execution_closes = market_closes;
    }
    // FIXME generalize these values
    std::map<std::string, std::string> before_trading_start_minutes = days_at_time(
            sim_params.sessions, time(8, 45), "US/Eastern", 0);

    clock = new MinuteSimulationClock(
            sim_params.sessions,
            execution_opens,
            execution_closes,
            before_trading_start_minutes,
            minutely_emission
    );
}

MetricsTracker TradingAlgorithm::_create_metrics_tracker() {
    return MetricsTracker(
            trading_calendar,
            sim_params.start_session,
            sim_params.end_session,
            sim_params.capital_base,
            sim_params.emission_rate,
            sim_params.data_frequency,
            asset_finder,
            _metrics_set
    );
}

void TradingAlgorithm::_create_generator(SimParams sim_params) {
    if (sim_params != nullptr) {
        this->sim_params = sim_params;
    }

    metrics_tracker = this->_create_metrics_tracker();

    // Set the dt initially to the period start by forcing it to change.
    on_dt_changed(this->sim_params.start_session);

    if (!initialized) {
        initialize(initialize_kwargs);
        initialized = true;
    }

    trading_client = new AlgorithmSimulator(
            this, sim_params, data_portal,
            _create_clock(),
            restrictions);
    metrics_tracker.handle_start_of_simulation();
    trading_client.transform();
}


Generator *TradingAlgorithm::get_generator() {
    // Override this method to add new logic to the construction
    // of the generator. Overrides can use the _create_generator
    // method to get a standard construction generator.
    return _create_generator(sim_params);
}

std::vector<Performance> TradingAlgorithm::run(DataPortal *data_portal = nullptr) {

    // Create tengine and loop through simulated_trading.
    // Each iteration returns a perf dictionary
    std::vector<Performance> perfs;
    try {
        Generator *generator = get_generator();
        while (generator->has_next()) {
            perfs.push_back(generator->next());
        }
        // convert perf dict to pandas dataframe
        std::vector<Performance> daily_stats = this->_create_daily_stats(perfs);
        analyze(daily_stats);
    } catch (...) {
        data_portal = nullptr;
        metrics_tracker = nullptr;
        throw;
    }

    return daily_stats;
}

std::vector<Performance> TradingAlgorithm::_create_daily_stats(std::vector<Performance> perfs) {
    // create daily and cumulative stats dataframe
    std::vector<Performance> daily_perfs;
    // TODO: the loop here could overwrite expected properties
    // of daily_perf. Could potentially raise or log a
    // warning.
    for (Performance perf: perfs) {
        if (perf.find("daily_perf") != perf.end()) {
            perf["daily_perf"].insert(perf["daily_perf"].end(), perf["daily_perf"]["recorded_vars"].begin(),
                                      perf["daily_perf"]["recorded_vars"].end());
            perf["daily_perf"].erase("recorded_vars");
            perf["daily_perf"].insert(perf["daily_perf"].end(), perf["cumulative_risk_metrics"].begin(),
                                      perf["cumulative_risk_metrics"].end());
            daily_perfs.push_back(perf["daily_perf"]);
        } else {
            risk_report = perf;
        }
    }
    // In C++, we don't have a direct equivalent to pandas DataFrame.
    // You might want to use a different data structure to hold your daily stats,
    // such as a std::vector, std::map, or a custom class.

    return daily_perfs;
}

std::vector<std::map<std::string, double>> TradingAlgorithm::calculate_capital_changes(
        std::string dt, std::string emission_rate, bool is_interday, double portfolio_value_adjustment = 0.0
) {
    // If there is a capital change for a given dt, this means the change
    // occurs before `handle_data` on the given dt. In the case of the
    // change being a target value, the change will be computed on the
    // portfolio value according to prices at the given dt

    // `portfolio_value_adjustment`, if specified, will be removed from the
    // portfolio_value of the cumulative performance when calculating deltas
    // from target capital changes.

    // CHECK is try/catch faster than search?

    std::map<std::string, double> capital_change;
    try {
        capital_change = this->capital_changes.at(dt);
    } catch (std::out_of_range &) {
        return std::vector<std::map<std::string, double>>();
    }

    _sync_last_sale_prices();
    double capital_change_amount;
    double target;
    if (capital_change["type"] == "target") {
        target = capital_change["value"];
        capital_change_amount = target - (
                this->portfolio.portfolio_value - portfolio_value_adjustment
        );

        std::cout << "Processing capital change to target " << target << " at " << dt << ". Capital "
                  << "change delta is " << capital_change_amount << std::endl;
    } else if (capital_change["type"] == "delta") {
        target = 0;
        capital_change_amount = capital_change["value"];
        std::cout << "Processing capital change of delta " << capital_change_amount << " at " << dt << std::endl;
    } else {
        std::cerr << "Capital change " << capital_change << " does not indicate a valid type "
                  << "('target' or 'delta')" << std::endl;
        return std::vector<std::map<std::string, double>>();
    }

    capital_change_deltas[dt] = capital_change_amount;
    metrics_tracker.capital_change(capital_change_amount);

    std::vector<std::map<std::string, double>> result;
    result.push_back({
                             {"capital_change", {
                                     {"date", dt},
                                     {"type", "cash"},
                                     {"target", target},
                                     {"delta", capital_change_amount},
                             }}
                     });

    return result;
}
std::variant<std::string, std::map<std::string, std::variant<std::string, double, std::string>>>
TradingAlgorithm::get_environment(std::string field = "platform") {
    // Query the execution environment.

    std::map<std::string, std::variant<std::string, double, std::string>> env = {
            {"arena",          this->sim_params.arena},
            {"data_frequency", this->sim_params.data_frequency},
            {"start",          this->sim_params.first_open},
            {"end",            this->sim_params.last_close},
            {"capital_base",   this->sim_params.capital_base},
            {"platform",       this->_platform},
    };

    if (field == "*") {
        return env;
    } else {
        try {
            return env.at(field);
        } catch (std::out_of_range &) {
            throw std::invalid_argument(field + " is not a valid field for get_environment");
        }
    }
}


void TradingAlgorithm::add_event(EventRule rule, std::function<void(Context, Data)> callback) {
    // Adds an event to the algorithm's EventManager.

    event_manager.add_event(
            Event(rule, callback)
    );
}

void TradingAlgorithm::schedule_function(
        std::function<void(Context, Data)> func,
        EventRule *date_rule = nullptr,
        EventRule *time_rule = nullptr,
        bool half_days = true,
        std::string calendar = ""
) {
    // Schedule a function to be called repeatedly in the future.

    // When the user calls schedule_function(func, <time_rule>), assume that
    // the user meant to specify a time rule but no date rule, instead of
    // a date rule and no time rule as the signature suggests
    if (dynamic_cast<AfterOpen *>(date_rule) || dynamic_cast<BeforeClose *>(date_rule) && !time_rule) {
        std::cerr << "Got a time rule for the second positional argument "
                  << "date_rule. You should use keyword argument "
                  << "time_rule= when calling schedule_function without "
                  << "specifying a date_rule" << std::endl;
    }

    date_rule = date_rule ? date_rule : new EveryDay();
    time_rule = (
            (time_rule ? time_rule : new EveryMinute())
    if this->sim_params.data_frequency == "minute"
    else
        // If we are in daily mode the time_rule is ignored.
        new EveryMinute()
    );

    // Check the type of the algorithm's schedule before pulling calendar
    // Note that the ExchangeTradingSchedule is currently the only
    // TradingSchedule class, so this is unlikely to be hit
    Calendar *cal;
    if (calendar.empty()) {
        cal = this->trading_calendar;
    } else if (calendar == "US_EQUITIES") {
        cal = get_calendar("XNYS");  // This function needs to be implemented
    } else if (calendar == "US_FUTURES") {
        cal = get_calendar("us_futures");  // This function needs to be implemented
    } else {
        throw std::invalid_argument("Invalid calendar: " + calendar);
    }

    this->add_event(
            make_eventrule(date_rule, time_rule, cal, half_days),  // This function needs to be implemented
            func
    );
}

void TradingAlgorithm::record(std::map<std::string, double> kwargs) {
    // Track and record values each day.

    for (auto const &item: kwargs) {
        std::string name = item.first;
        double value = item.second;
        recorded_vars[name] = value;
    }
}

class SetBenchmarkOutsideInitialize : public std::runtime_error {
public:
    SetBenchmarkOutsideInitialize() : std::runtime_error("Cannot set benchmark after initialize.") {}
};

class ContinuousFuture {
    // This class needs to be implemented
};

ContinuousFuture *TradingAlgorithm::continuous_future(
        std::string root_symbol_str,
        int offset = 0,
        std::string roll = "volume",
        std::string adjustment = "mul"
) {
    // Create a specifier for a continuous contract.

    // Ensure root_symbol_str is in upper case
    std::transform(root_symbol_str.begin(), root_symbol_str.end(), root_symbol_str.begin(), ::toupper);

    return this->asset_finder.create_continuous_future(
            root_symbol_str, offset, roll, adjustment);
}

Equity *TradingAlgorithm::symbol(std::string symbol_str, std::string country_code = "") {
    // Lookup an Equity by its ticker symbol.

    // Ensure symbol_str is in upper case
    std::transform(symbol_str.begin(), symbol_str.end(), symbol_str.begin(), ::toupper);

    // If the user has not set the symbol lookup date,
    // use the end_session as the date for symbol->sid resolution.
    std::string _lookup_date = (
            ! _symbol_lookup_date.empty()
            ? _symbol_lookup_date
            : sim_params.end_session
    );

    return asset_finder.lookup_symbol(symbol_str, _lookup_date, country_code);
}

std::vector<Equity *> symbols(std::vector<std::string> args, std::string country_code = "") {
    // Lookup multiple Equities as a list.

    std::vector<Equity *> equities;
    for (std::string identifier: args) {
        equities.push_back(this->symbol(identifier, country_code));
    }

    return equities;
}

Asset *sid(int sid) {
    // Lookup an Asset by its unique asset identifier.
    return asset_finder.retrieve_asset(sid);
}

Future *future_symbol(std::string symbol) {
    // Lookup a futures contract with a given symbol.

    // Ensure symbol is in upper case
    std::transform(symbol.begin(), symbol.end(), symbol.begin(), ::toupper);

    return this->asset_finder.lookup_future_symbol(symbol);
}

double _calculate_order_value_amount(Asset *asset, double value) {
    // Calculates how many shares/contracts to order based on the type of
    // asset being ordered.

    // Make sure the asset exists, and that there is a last price for it.
    std::string normalized_date = trading_calendar.minute_to_session(this->datetime);

    if (normalized_date < asset->start_date) {
        throw std::runtime_error(
                "Cannot order " + asset->symbol + ", as it started trading on"
                                                  " " + asset->start_date
        );
    } else if (normalized_date > asset->end_date) {
        throw std::runtime_error(
                "Cannot order " + asset->symbol + ", as it stopped trading on"
                                                  " " + asset->end_date
        );
    } else {
        double last_price = trading_client.current_data.current(asset, "price");

        if (std::isnan(last_price)) {
            throw std::runtime_error(
                    "Cannot order " + asset->symbol + " on " + datetime +
                    " as there is no last price for the security."
            );
        }
    }

    if (last_price == 0) {
        std::string zero_message = "Price of 0 for " + asset->symbol + "; can't infer value";
        // Don't place any order
        return 0;
    }

    double value_multiplier = asset->price_multiplier;

    return value / (last_price * value_multiplier);
}

bool TradingAlgorithm::_can_order_asset(Asset *asset) {
    if (asset == nullptr) {
        throw std::runtime_error(
                "Passing non-Asset argument to 'order()' is not supported."
                " Use 'sid()' or 'symbol()' methods to look up an Asset."
        );
    }

    if (!asset->auto_close_date.empty()) {
        std::string day = this->trading_calendar.minute_to_session(this->get_datetime());

        if (day > std::min(asset->end_date, asset->auto_close_date)) {
            std::cout << "Cannot place order for " << asset->symbol << ", as it has de-listed. "
                      << "Any existing positions for this asset will be "
                      << "liquidated on "
                      << asset->auto_close_date << ".\n";
            return false;
        }
    }
    return true;
}

std::string TradingAlgorithm::order(Asset *asset, int amount, double limit_price = 0.0, double stop_price = 0.0,
                                    ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return "";
    }
    int amount;
    ExecutionStyle *style;
    std::tie(amount, style) = _calculate_order(asset, amount, limit_price, stop_price, style);
    return blotter.order(asset, amount, style);
}

std::pair<int, ExecutionStyle *>
TradingAlgorithm::_calculate_order(Asset *asset, int amount, double limit_price = 0.0, double stop_price = 0.0,
                                   ExecutionStyle *style = nullptr) {
    amount = round_order(amount);
    validate_order_params(asset, amount, limit_price, stop_price, style);

    // Convert deprecated limit_price and stop_price parameters to use
    // ExecutionStyle objects.
    style = __convert_order_params_for_blotter(asset, limit_price, stop_price, style);
    return std::make_pair(amount, style);
}

// this is static
int TradingAlgorithm::round_order(int amount) {
    return static_cast<int>(std::round(amount));
}

void TradingAlgorithm::validate_order_params(Asset *asset, int amount, double limit_price, double stop_price,
                                             ExecutionStyle *style) {
    if (!this->initialized) {
        throw std::runtime_error(
                "order() can only be called from within handle_data()"
        );
    }

    if (style) {
        if (limit_price > 0.0) {
            throw std::runtime_error(
                    "Passing both limit_price and style is not supported."
            );
        }
        if (stop_price > 0.0) {
            throw std::runtime_error(
                    "Passing both stop_price and style is not supported."
            );
        }
    }
    for (auto const &control: trading_controls) {
        control.validate(
                asset, amount, portfolio, get_datetime(), trading_client.current_data);
    }
}

ExecutionStyle * TradingAlgorithm::__convert_order_params_for_blotter(Asset *asset, double limit_price, double stop_price,
                                                     ExecutionStyle *style) {
    if (style) {
        assert(limit_price == 0.0 && stop_price == 0.0);
        return style;
    }
    if (limit_price > 0.0 && stop_price > 0.0) {
        return new StopLimitOrder(limit_price, stop_price, asset);
    }
    if (limit_price > 0.0) {
        return new LimitOrder(limit_price, asset);
    }
    if (stop_price > 0.0) {
        return new StopOrder(stop_price, asset);
    }
    return new MarketOrder();
}

std::string TradingAlgorithm::order_value(Asset *asset, double value, double limit_price = 0.0, double stop_price = 0.0,
                                          ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return "";
    }

    double amount = _calculate_order_value_amount(asset, value);
    return order(asset, amount, limit_price, stop_price, style);
}

std::map<std::string, double> TradingAlgorithm::recorded_vars() {
    return this->_recorded_vars;
}

void TradingAlgorithm::_sync_last_sale_prices(std::tm *dt = nullptr) {
    if (dt == nullptr) {
        dt = this->datetime;
    }

    if (std::difftime(std::mktime(dt), std::mktime(this->_last_sync_time)) != 0) {
        this->metrics_tracker.sync_last_sale_prices(dt, this->data_portal);
        this->_last_sync_time = dt;
    }
}

Portfolio TradingAlgorithm::portfolio() {
    _sync_last_sale_prices();
    return this->metrics_tracker.portfolio;
}

Account TradingAlgorithm::account() {
    _sync_last_sale_prices();
    return this->metrics_tracker.account;
}

void TradingAlgorithm::set_logger(std::string logger) {
    this->logger = logger;
}

void TradingAlgorithm::on_dt_changed(std::tm *dt) {
    this->datetime = dt;
    this->blotter.set_date(dt);
}

std::tm *TradingAlgorithm::get_datetime(std::string tz) {
    std::tm *dt = datetime;
    assert(dt->tm_zone == "UTC");  // Algorithm should have utc datetime
    if (!tz.empty()) {
        // Convert dt to the specified timezone
        // This requires a timezone library such as date.h or Boost.DateTime
    }
    return dt;
}

void
TradingAlgorithm::set_slippage(EquitySlippageModel *us_equities = nullptr, FutureSlippageModel *us_futures = nullptr) {
    if (this->initialized) {
        throw std::runtime_error("Cannot set slippage after initialize.");
    }

    if (us_equities != nullptr) {
        if (std::find(us_equities->allowed_asset_types.begin(), us_equities->allowed_asset_types.end(), "Equity") ==
            us_equities->allowed_asset_types.end()) {
            throw std::runtime_error("IncompatibleSlippageModel: The given model does not support equities.");
        }
        this->blotter.slippage_models["Equity"] = us_equities;
    }

    if (us_futures != nullptr) {
        if (std::find(us_futures->allowed_asset_types.begin(), us_futures->allowed_asset_types.end(), "Future") ==
            us_futures->allowed_asset_types.end()) {
            throw std::runtime_error("IncompatibleSlippageModel: The given model does not support futures.");
        }
        this->blotter.slippage_models["Future"] = us_futures;
    }
}

void TradingAlgorithm::set_commission(EquityCommissionModel *us_equities = nullptr,
                                      FutureCommissionModel *us_futures = nullptr) {
    if (this->initialized) {
        throw std::runtime_error("Cannot set commission after initialize.");
    }

    if (us_equities != nullptr) {
        if (std::find(us_equities->allowed_asset_types.begin(), us_equities->allowed_asset_types.end(), "Equity") ==
            us_equities->allowed_asset_types.end()) {
            throw std::runtime_error("IncompatibleCommissionModel: The given model does not support equities.");
        }
        this->blotter.commission_models["Equity"] = us_equities;
    }

    if (us_futures != nullptr) {
        if (std::find(us_futures->allowed_asset_types.begin(), us_futures->allowed_asset_types.end(), "Future") ==
            us_futures->allowed_asset_types.end()) {
            throw std::runtime_error("IncompatibleCommissionModel: The given model does not support futures.");
        }
        this->blotter.commission_models["Future"] = us_futures;
    }
}

void TradingAlgorithm::set_cancel_policy(CancelPolicy *cancel_policy) {
    if (!dynamic_cast<CancelPolicy *>(cancel_policy)) {
        throw std::runtime_error("UnsupportedCancelPolicy");
    }

    if (initialized) {
        throw std::runtime_error("Cannot set cancel policy after initialize.");
    }

    blotter.cancel_policy = cancel_policy;
}

void TradingAlgorithm::set_symbol_lookup_date(std::tm *dt) {
    // Convert dt to UTC
    // This requires a timezone library such as date.h or Boost.DateTime
    _symbol_lookup_date = dt;
}

void TradingAlgorithm::order_percent(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0,
                                     ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return;
    }

    double amount = _calculate_order_target_percent_amount(asset, target);
    order(asset, amount, limit_price, stop_price, style);
}

void TradingAlgorithm::order_target(Asset *asset, int target, double limit_price = 0.0, double stop_price = 0.0,
                                    ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return;
    }

    int amount = _calculate_order_target_amount(asset, target);
    this->order(asset, amount, limit_price, stop_price, style);
}

void
TradingAlgorithm::order_target_value(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0,
                                     ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return;
    }

    double target_amount = this->_calculate_order_value_amount(asset, target);
    int amount = _calculate_order_target_amount(asset, target_amount);
    this->order(asset, amount, limit_price, stop_price, style);
}

void
TradingAlgorithm::order_target_percent(Asset *asset, double target, double limit_price = 0.0, double stop_price = 0.0,
                                       ExecutionStyle *style = nullptr) {
    if (!_can_order_asset(asset)) {
        return;
    }

    double amount = _calculate_order_target_percent_amount(asset, target);
    this->order(asset, amount, limit_price, stop_price, style);
}

void TradingAlgorithm::batch_market_order(std::map<Asset *, int> share_counts) {
    ExecutionStyle *style = new MarketOrder();
    std::vector<std::tuple<Asset *, int, ExecutionStyle *>> order_args;
    for (auto const &[asset, amount]: share_counts) {
        if (amount) {
            order_args.push_back(std::make_tuple(asset, amount, style));
        }
    }
    blotter.batch_order(order_args);
}

std::map<Asset *, std::vector<Order *>> TradingAlgorithm::get_open_orders(Asset *asset = nullptr) {
    if (asset == nullptr) {
        std::map<Asset *, std::vector<Order *>> open_orders;
        for (auto const &[key, orders]: this->blotter.open_orders) {
            if (!orders.empty()) {
                open_orders[key] = orders;
            }
        }
        return open_orders;
    } else {
        if (blotter.open_orders.find(asset) != blotter.open_orders.end()) {
            return {asset, blotter.open_orders[asset]};
        }
        return {};
    }
}

Order *TradingAlgorithm::get_order(std::string order_id) {
    if (blotter.orders.find(order_id) != blotter.orders.end()) {
        return blotter.orders[order_id]->to_api_obj();
    }
    return nullptr;
}

void TradingAlgorithm::cancel_order(std::variant<std::string, Order *> order_param) {
    std::string order_id;
    if (std::holds_alternative<Order *>(order_param)) {
        order_id = std::get<Order *>(order_param)->id;
    } else {
        order_id = std::get<std::string>(order_param);
    }
    blotter.cancel(order_id);
}

void TradingAlgorithm::register_account_control(AccountControl *control) {
    if (initialized) {
        throw RegisterAccountControlPostInit();
    }
    account_controls.push_back(control);
}

void TradingAlgorithm::validate_account_controls() {
    for (AccountControl *control: account_controls) {
        control->validate(portfolio, account, get_datetime(), trading_client.current_data);
    }
}

void TradingAlgorithm::set_max_leverage(double max_leverage) {
    AccountControl *control = new MaxLeverage(max_leverage);
    register_account_control(control);
}

void TradingAlgorithm::set_min_leverage(double min_leverage, std::tm *grace_period) {
    std::tm *deadline = this->sim_params.start_session + grace_period;
    AccountControl *control = new MinLeverage(min_leverage, deadline);
    register_account_control(control);
}

void TradingAlgorithm::register_trading_control(TradingControl *control) {
    if (initialized) {
        throw RegisterTradingControlPostInit();
    }
    trading_controls.push_back(control);
}

void TradingAlgorithm::set_max_position_size(Asset *asset = nullptr, int max_shares = 0, double max_notional = 0.0,
                                             std::string on_error = "fail") {
    TradingControl *control = new MaxPositionSize(asset, max_shares, max_notional, on_error);
    register_trading_control(control);
}

void TradingAlgorithm::set_max_order_size(Asset *asset = nullptr, int max_shares = 0, double max_notional = 0.0,
                                          std::string on_error = "fail") {
    TradingControl *control = new MaxOrderSize(asset, max_shares, max_notional, on_error);
    register_trading_control(control);
}

void TradingAlgorithm::set_max_order_count(int max_count, std::string on_error = "fail") {
    TradingControl *control = new MaxOrderCount(on_error, max_count);
    register_trading_control(control);
}

void TradingAlgorithm::set_do_not_order_list(std::vector<Asset *> restricted_list, std::string on_error = "fail") {
    Restrictions *restrictions = new StaticRestrictions(restricted_list);
    set_asset_restrictions(restrictions, on_error);
}

void TradingAlgorithm::set_asset_restrictions(Restrictions *restrictions, std::string on_error = "fail") {
    TradingControl *control = new RestrictedListOrder(on_error, restrictions);
    register_trading_control(control);
    this->restrictions |= restrictions;
}

void TradingAlgorithm::set_long_only(std::string on_error = "fail") {
    register_trading_control(new LongOnly(on_error));
}


std::string TradingAlgorithm::default_fetch_csv_country_code(std::string calendar) {
    return _DEFAULT_FETCH_CSV_COUNTRY_CODES[calendar];
}

std::vector<std::function<void()>> TradingAlgorithm::all_api_methods() {
    std::vector<std::function<void()>> api_methods;
    for (auto const &[name, method]: TradingAlgorithm::_pipelines) {
        if (method.is_api_method) {
            api_methods.push_back(method);
        }
    }
    return api_methods;
}
