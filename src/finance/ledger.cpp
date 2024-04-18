#include <unordered_map>
#include <map>
#include <string>
#include <vector>

class PositionStats {
public:
    double gross_exposure;
    double gross_value;
    double long_exposure;
    double long_value;
    double net_exposure;
    double net_value;
    double short_exposure;
    double short_value;
    unsigned long longs_count;
    unsigned long shorts_count;
    std::vector<double> position_exposure_array;
    std::map<int, double> position_exposure_series;

    static PositionStats newStats() {
        PositionStats stats;
        stats.position_exposure_series = std::map<int, double>();
        stats.position_exposure_array = std::vector<double>();
        stats.underlying_value_array = std::vector<double>();
        stats.underlying_index_array = std::vector<double>();
        return stats;
    }
};

class Position {
private:
    PositionStats underlying_position;

public:
    Position(PositionStats underlying_position)
            : underlying_position(underlying_position) {}

    PositionStats getUnderlyingPosition() const { return underlying_position; }
};

class Positions : public std::map<int, Position> {
public:
    Position operator[](int key) {
        if (this->find(key) == this->end()) {
            // If key not found, create a new Position with default PositionStats
            (*this)[key] = Position(PositionStats::newStats());
        }
        return (*this)[key];
    }
};

class PositionTracker {
private:
    std::map<std::string, int> positions;
    std::map<std::string, double> unpaid_dividends;
    std::map<std::string, double> unpaid_stock_dividends;
    Positions positions_store;
    std::string data_frequency;
    bool dirty_stats;
    PositionStats stats;

public:
    PositionTracker(std::string data_frequency)
            : data_frequency(data_frequency), dirty_stats(true), stats(PositionStats::newStats()) {}
};

void PositionTracker::update_position(
        Asset asset,
        int amount = 0,
        double last_sale_price = 0.0,
        std::string last_sale_date = "",
        double cost_basis = 0.0
) {
    dirty_stats = true;

    if (positions.find(asset) == positions.end()) {
        Position position(asset);
        positions[asset] = position;
    }

    Position& position = positions[asset];

    if (amount != 0) {
        position.amount = amount;
    }
    if (last_sale_price != 0.0) {
        position.last_sale_price = last_sale_price;
    }
    if (!last_sale_date.empty()) {
        position.last_sale_date = last_sale_date;
    }
    if (cost_basis != 0.0) {
        position.cost_basis = cost_basis;
    }
}

void PositionTracker::execute_transaction(Transaction txn) {
    dirty_stats = true;

    Asset asset = txn.getAsset();

    if (positions.find(asset) == positions.end()) {
        Position position(asset);
        positions[asset] = position;
    }

    Position& position = positions[asset];

    position.update(txn);

    if (position.getAmount() == 0) {
        positions.erase(asset);

        if (_positions_store.find(asset) != _positions_store.end()) {
            _positions_store.erase(asset);
        }
    }
}

void PositionTracker::handle_commission(Asset asset, double cost) {
    if (positions.find(asset) != positions.end()) {
        dirty_stats = true;
        positions[asset].adjust_commission_cost_basis(asset, cost);
    }
}

double PositionTracker::handle_splits(std::vector<std::pair<Asset, double>> splits) {
    double total_leftover_cash = 0.0;

    for (auto& split : splits) {
        Asset asset = split.first;
        double ratio = split.second;

        if (positions.find(asset) != positions.end()) {
            dirty_stats = true;

            Position& position = positions[asset];
            double leftover_cash = position.handle_split(asset, ratio);
            total_leftover_cash += leftover_cash;
        }
    }

    return total_leftover_cash;
}

void PositionTracker::earn_dividends(std::vector<CashDividend> cash_dividends, std::vector<StockDividend> stock_dividends) {
    for (auto& cash_dividend : cash_dividends) {
        dirty_stats = true;

        Asset asset = cash_dividend.getAsset();

        if (positions.find(asset) != positions.end()) {
            Position& position = positions[asset];
            DividendOwed div_owed = position.earn_dividend(cash_dividend);

            if (_unpaid_dividends.find(cash_dividend.getPayDate()) == _unpaid_dividends.end()) {
                _unpaid_dividends[cash_dividend.getPayDate()] = std::vector<DividendOwed>();
            }

            _unpaid_dividends[cash_dividend.getPayDate()].push_back(div_owed);
        }
    }

    for (auto& stock_dividend : stock_dividends) {
        dirty_stats = true;

        Asset asset = stock_dividend.getAsset();

        if (positions.find(asset) != positions.end()) {
            Position& position = positions[asset];
            DividendOwed div_owed = position.earn_stock_dividend(stock_dividend);

            if (_unpaid_stock_dividends.find(stock_dividend.getPayDate()) == _unpaid_stock_dividends.end()) {
                _unpaid_stock_dividends[stock_dividend.getPayDate()] = std::vector<DividendOwed>();
            }

            _unpaid_stock_dividends[stock_dividend.getPayDate()].push_back(div_owed);
        }
    }
}

double PositionTracker::pay_dividends(std::string next_trading_day) {
    double net_cash_payment = 0.0;

    if (_unpaid_dividends.find(next_trading_day) != _unpaid_dividends.end()) {
        std::vector<DividendOwed>& payments = _unpaid_dividends[next_trading_day];
        _unpaid_dividends.erase(next_trading_day);

        for (auto& payment : payments) {
            net_cash_payment += payment.getAmount();
        }
    }

    if (_unpaid_stock_dividends.find(next_trading_day) != _unpaid_stock_dividends.end()) {
        std::vector<DividendOwed>& stock_payments = _unpaid_stock_dividends[next_trading_day];

        for (auto& stock_payment : stock_payments) {
            Asset payment_asset = stock_payment.getPaymentAsset();
            int share_count = stock_payment.getShareCount();

            if (positions.find(payment_asset) == positions.end()) {
                Position position(payment_asset);
                positions[payment_asset] = position;
            }

            Position& position = positions[payment_asset];
            position.amount += share_count;
        }
    }

    return net_cash_payment;
}

#include <cmath> // for std::isnan

Transaction PositionTracker::maybe_create_close_position_transaction(Asset asset, std::string dt, DataPortal data_portal) {
    if (positions.find(asset) == positions.end()) {
        return Transaction(); // Return a default Transaction object
    }

    int amount = positions[asset].getAmount();
    double price = data_portal.get_spot_value(asset, "price", dt, data_frequency);

    // Get the last traded price if price is no longer available
    if (std::isnan(price)) {
        price = positions[asset].getLastSalePrice();
    }

    return Transaction(
            asset,
            -amount,
            dt,
            price,
            ""
    );
}

Positions PositionTracker::get_positions() {
    Positions positions = _positions_store;

    for (auto& [asset, pos] : positions) {
        positions[asset] = pos.getProtocolPosition();
    }

    return positions;
}

std::vector<std::map<std::string, double>> PositionTracker::get_position_list() {
    std::vector<std::map<std::string, double>> position_list;

    for (auto& [asset, position] : positions) {
        if (position.getAmount() != 0) {
            position_list.push_back(position.toDict());
        }
    }

    return position_list;
}


#include <functional> // for std::function

void PositionTracker::sync_last_sale_prices(std::string dt, DataPortal data_portal, bool handle_non_market_minutes = false) {
    dirty_stats = true;

    std::function<double(Asset)> get_price;

    if (handle_non_market_minutes) {
        std::string previous_minute = data_portal.trading_calendar.previous_minute(dt);
        get_price = [&](Asset asset) {
            return data_portal.get_adjusted_value(asset, "price", previous_minute, dt, data_frequency);
        };
    } else {
        get_price = [&](Asset asset) {
            return data_portal.get_scalar_asset_spot_value(asset, "price", dt, data_frequency);
        };
    }

    update_position_last_sale_prices(positions, get_price, dt);
}

PositionStats PositionTracker::getStats() {
    if (dirty_stats) {
        calculate_position_tracker_stats(positions, stats);
        dirty_stats = false;
    }

    return stats;
}

// Equivalent of OrderedDict.move_to_end
template <typename K, typename V>
void move_to_end(std::map<K, V>& m, const K& key) {
    if (m.find(key) != m.end()) {
        V value = m[key];
        m.erase(key);
        m[key] = value;
    }
}

// Equivalent of PeriodStats namedtuple
struct PeriodStats {
    double net_liquidation;
    double gross_leverage;
    double net_leverage;
};

// Equivalent of not_overridden sentinel
const std::string not_overridden = "not_overridden";



class Portfolio; // Forward declaration, replace with actual class if available
class Account; // Forward declaration, replace with actual class if available
class PositionTracker; // Forward declaration, replace with actual class if available

class Ledger {
private:
    bool __dirty_portfolio;
    Portfolio* _immutable_portfolio;
    Portfolio* _portfolio;
    std::vector<double> daily_returns_series;
    std::vector<double> daily_returns_array;
    double _previous_total_returns;
    PositionStats* _position_stats;
    bool _dirty_account;
    Account* _immutable_account;
    Account* _account;
    std::map<std::string, double> _account_overrides;
    PositionTracker* position_tracker;
    std::map<std::string, Transaction> _processed_transactions;
    std::map<std::string, Order> _orders_by_modified;
    std::map<std::string, Order> _orders_by_id;
    std::map<Asset, double> _payout_last_sale_prices;

public:
    Ledger(std::vector<std::string> trading_sessions, double capital_base, std::string data_frequency) {
        if (!trading_sessions.empty()) {
            std::string start = trading_sessions[0];
        } else {
            std::string start = "";
        }

        __dirty_portfolio = false;
        _immutable_portfolio = new Portfolio(start, capital_base);
        _portfolio = new Portfolio(*_immutable_portfolio);

        daily_returns_series = std::vector<double>(trading_sessions.size(), std::nan(""));
        daily_returns_array = daily_returns_series;

        _previous_total_returns = 0;

        _position_stats = nullptr;

        _dirty_account = true;
        _immutable_account = new Account();
        _account = new Account(*_immutable_account);

        _account_overrides = {};

        position_tracker = new PositionTracker(data_frequency);

        _processed_transactions = {};

        _orders_by_modified = {};
        _orders_by_id = {};

        _payout_last_sale_prices = {};
    }

    // Other methods and properties are omitted for brevity
};
double Ledger::getTodaysReturns() const {
    return (portfolio.getReturns() + 1) / (_previous_total_returns + 1) - 1;
}
bool Ledger::isDirtyPortfolio() const {
    return __dirty_portfolio;
}

void Ledger::setDirtyPortfolio(bool value) {
    if (value) {
        __dirty_portfolio = _dirty_account = value;
    } else {
        __dirty_portfolio = value;
    }
}
void Ledger::start_of_session(std::string session_label) {
    _processed_transactions.clear();
    _orders_by_modified.clear();
    _orders_by_id.clear();

    _previous_total_returns = _portfolio->getReturns();
}

void Ledger::end_of_bar(int session_ix) {
    daily_returns_array[session_ix] = getTodaysReturns();
}

void Ledger::end_of_session(int session_ix) {
    daily_returns_series[session_ix] = getTodaysReturns();
}
void Ledger::sync_last_sale_prices(std::string dt, DataPortal data_portal, bool handle_non_market_minutes = false) {
    position_tracker->sync_last_sale_prices(dt, data_portal, handle_non_market_minutes);
    __dirty_portfolio = true;
}

static double calculate_payout(double multiplier, int amount, double old_price, double price) {
    return (price - old_price) * multiplier * amount;
}
void Ledger::cash_flow(double amount) {
    __dirty_portfolio = true;
    Portfolio* p = _portfolio;
    p->cash_flow += amount;
    p->cash += amount;
}

void Ledger::process_transaction(Transaction transaction) {
    Asset asset = transaction.getAsset();

    if (dynamic_cast<Future*>(asset)) {
        double old_price;
        try {
            old_price = _payout_last_sale_prices.at(asset);
        } catch (std::out_of_range&) {
            _payout_last_sale_prices[asset] = transaction.getPrice();
        } else {
            Position& position = position_tracker->positions[asset];
            int amount = position.getAmount();
            double price = transaction.getPrice();

            cash_flow(
                    calculate_payout(
                            asset.getPriceMultiplier(),
                            amount,
                            old_price,
                            price
                    )
            );

            if (amount + transaction.getAmount() == 0) {
                _payout_last_sale_prices.erase(asset);
            } else {
                _payout_last_sale_prices[asset] = price;
            }
        }
    } else {
        cash_flow(-(transaction.getPrice() * transaction.getAmount()));
    }

    position_tracker->execute_transaction(transaction);

    std::map<std::string, double> transaction_dict = transaction.toDict();
    std::string dt = transaction.getDt();

    if (_processed_transactions.find(dt) == _processed_transactions.end()) {
        _processed_transactions[dt] = std::vector<std::map<std::string, double>>();
    }

    _processed_transactions[dt].push_back(transaction_dict);
}

void Ledger::process_splits(std::vector<std::pair<Asset, double>> splits) {
    double leftover_cash = position_tracker->handle_splits(splits);
    if (leftover_cash > 0) {
        cash_flow(leftover_cash);
    }
}

void Ledger::process_order(Order order) {
    std::string dt = order.getDt();

    if (_orders_by_modified.find(dt) == _orders_by_modified.end()) {
        _orders_by_modified[dt] = std::map<std::string, Order>{{order.getId(), order}};
        _orders_by_id[order.getId()] = order;
    } else {
        _orders_by_id[order.getId()] = _orders_by_modified[dt][order.getId()] = order;
        // To preserve the order of the orders by modified date
        move_to_end(_orders_by_modified[dt], order.getId());
    }

    move_to_end(_orders_by_id, order.getId());
}

void Ledger::process_commission(Commission commission) {
    Asset asset = commission["asset"];
    double cost = commission["cost"];

    position_tracker->handle_commission(asset, cost);
    cash_flow(-cost);
}

void Ledger::close_position(Asset asset, std::string dt, DataPortal data_portal) {
    Transaction txn = position_tracker->maybe_create_close_position_transaction(asset, dt, data_portal);
    // In C++, a default-constructed object is not equivalent to None in Python.
    // You need to define a way to check if the transaction is valid or not.
    // Here, we assume that a Transaction object is invalid if its Asset is null.
    if (txn.getAsset() != nullptr) {
        process_transaction(txn);
    }
}

void Ledger::process_dividends(std::string next_session, AssetFinder asset_finder, AdjustmentReader adjustment_reader) {
    PositionTracker* position_tracker = this->position_tracker;

    std::set<Asset> held_sids = position_tracker->getPositions();

    if (!held_sids.empty()) {
        std::vector<CashDividend> cash_dividends = adjustment_reader.get_dividends_with_ex_date(held_sids, next_session, asset_finder);
        std::vector<StockDividend> stock_dividends = adjustment_reader.get_stock_dividends_with_ex_date(held_sids, next_session, asset_finder);

        position_tracker->earn_dividends(cash_dividends, stock_dividends);
    }

    cash_flow(position_tracker->pay_dividends(next_session));
}

void Ledger::capital_change(double change_amount) {
    update_portfolio();
    Portfolio* portfolio = _portfolio;

    portfolio->portfolio_value += change_amount;
    portfolio->cash += change_amount;
}


std::vector<std::map<std::string, double>> Ledger::getTransactions(std::string dt = "") {
    if (dt.empty()) {
        std::vector<std::map<std::string, double>> all_transactions;
        for (auto& by_day : _processed_transactions) {
            for (auto& txn : by_day.second) {
                all_transactions.push_back(txn);
            }
        }
        return all_transactions;
    }

    if (_processed_transactions.find(dt) != _processed_transactions.end()) {
        return _processed_transactions[dt];
    }

    return std::vector<std::map<std::string, double>>();
}

std::vector<std::map<std::string, double>> Ledger::getOrders(std::string dt = "") {
    if (dt.empty()) {
        std::vector<std::map<std::string, double>> all_orders;
        for (auto& order : _orders_by_id) {
            all_orders.push_back(order.second.toDict());
        }
        return all_orders;
    }

    if (_orders_by_modified.find(dt) != _orders_by_modified.end()) {
        std::vector<std::map<std::string, double>> orders;
        for (auto& order : _orders_by_modified[dt]) {
            orders.push_back(order.second.toDict());
        }
        return orders;
    }

    return std::vector<std::map<std::string, double>>();
}


std::vector<std::map<std::string, double>> Ledger::getPositions() {
    return position_tracker->get_position_list();
}

double Ledger::getPayoutTotal(std::map<Asset, Position> positions) {
    double total = 0.0;
    for (auto& [asset, old_price] : _payout_last_sale_prices) {
        Position& position = positions[asset];
        _payout_last_sale_prices[asset] = double price = position.getLastSalePrice();
        int amount = position.getAmount();
        total += calculate_payout(
                asset.getPriceMultiplier(),
                amount,
                old_price,
                price
        );
    }

    return total;
}

void Ledger::update_portfolio() {
    if (!__dirty_portfolio) {
        return;
    }

    Portfolio* portfolio = _portfolio;
    PositionTracker* pt = position_tracker;

    portfolio->positions = pt->get_positions();
    PositionStats position_stats = pt->getStats();

    portfolio->positions_value = double position_value = position_stats.net_value;
    portfolio->positions_exposure = position_stats.net_exposure;
    cash_flow(getPayoutTotal(pt->positions));

    double start_value = portfolio->portfolio_value;

    // update the new starting value
    portfolio->portfolio_value = double end_value = portfolio->cash + position_value;

    double pnl = end_value - start_value;
    double returns;
    if (start_value != 0) {
        returns = pnl / start_value;
    } else {
        returns = 0.0;
    }

    portfolio->pnl += pnl;
    portfolio->returns = (1 + portfolio->returns) * (1 + returns) - 1;

    // the portfolio has been fully synced
    __dirty_portfolio = false;
}

Portfolio Ledger::getPortfolio() {
    update_portfolio();
    return *_immutable_portfolio;
}

#include <cmath> // for std::numeric_limits

std::tuple<double, double, double> Ledger::calculate_period_stats() {
    PositionStats position_stats = position_tracker->getStats();
    double portfolio_value = _portfolio->portfolio_value;

    double gross_leverage;
    double net_leverage;

    if (portfolio_value == 0) {
        gross_leverage = net_leverage = std::numeric_limits<double>::infinity();
    } else {
        gross_leverage = position_stats.gross_exposure / portfolio_value;
        net_leverage = position_stats.net_exposure / portfolio_value;
    }

    return std::make_tuple(portfolio_value, gross_leverage, net_leverage);
}



void Ledger::override_account_fields(
        double settled_cash = std::numeric_limits<double>::quiet_NaN(),
        double accrued_interest = std::numeric_limits<double>::quiet_NaN(),
        double buying_power = std::numeric_limits<double>::quiet_NaN(),
        double equity_with_loan = std::numeric_limits<double>::quiet_NaN(),
        double total_positions_value = std::numeric_limits<double>::quiet_NaN(),
        double total_positions_exposure = std::numeric_limits<double>::quiet_NaN(),
        double regt_equity = std::numeric_limits<double>::quiet_NaN(),
        double regt_margin = std::numeric_limits<double>::quiet_NaN(),
        double initial_margin_requirement = std::numeric_limits<double>::quiet_NaN(),
        double maintenance_margin_requirement = std::numeric_limits<double>::quiet_NaN(),
        double available_funds = std::numeric_limits<double>::quiet_NaN(),
        double excess_liquidity = std::numeric_limits<double>::quiet_NaN(),
        double cushion = std::numeric_limits<double>::quiet_NaN(),
        int day_trades_remaining = std::numeric_limits<int>::quiet_NaN(),
        double leverage = std::numeric_limits<double>::quiet_NaN(),
        double net_leverage = std::numeric_limits<double>::quiet_NaN(),
        double net_liquidation = std::numeric_limits<double>::quiet_NaN()
) {
    _dirty_account = true;
    _account_overrides = {
            {"settled_cash", settled_cash},
            {"accrued_interest", accrued_interest},
            {"buying_power", buying_power},
            {"equity_with_loan", equity_with_loan},
            {"total_positions_value", total_positions_value},
            {"total_positions_exposure", total_positions_exposure},
            {"regt_equity", regt_equity},
            {"regt_margin", regt_margin},
            {"initial_margin_requirement", initial_margin_requirement},
            {"maintenance_margin_requirement", maintenance_margin_requirement},
            {"available_funds", available_funds},
            {"excess_liquidity", excess_liquidity},
            {"cushion", cushion},
            {"day_trades_remaining", day_trades_remaining},
            {"leverage", leverage},
            {"net_leverage", net_leverage},
            {"net_liquidation", net_liquidation}
    };
}

Account Ledger::getAccount() {
    if (_dirty_account) {
        Portfolio portfolio = getPortfolio();

        Account* account = _account;

        account->settled_cash = portfolio.cash;
        account->accrued_interest = 0.0;
        account->buying_power = std::numeric_limits<double>::infinity();
        account->equity_with_loan = portfolio.portfolio_value;
        account->total_positions_value = portfolio.portfolio_value - portfolio.cash;
        account->total_positions_exposure = portfolio.positions_exposure;
        account->regt_equity = portfolio.cash;
        account->regt_margin = std::numeric_limits<double>::infinity();
        account->initial_margin_requirement = 0.0;
        account->maintenance_margin_requirement = 0.0;
        account->available_funds = portfolio.cash;
        account->excess_liquidity = portfolio.cash;
        account->cushion = (portfolio.portfolio_value != 0) ? (portfolio.cash / portfolio.portfolio_value) : std::numeric_limits<double>::quiet_NaN();
        account->day_trades_remaining = std::numeric_limits<double>::infinity();

        std::tie(account->net_liquidation, account->gross_leverage, account->net_leverage) = calculate_period_stats();

        account->leverage = account->gross_leverage;

        // apply the overrides
        for (auto& [k, v] : _account_overrides) {
            account->setAttribute(k, v);
        }

        // the account has been fully synced
        _dirty_account = false;
    }

    return *_immutable_account;
}
