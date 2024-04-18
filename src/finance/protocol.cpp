#include <map>
#include <string>
#include <sstream>
#include <vector>


enum class DataSourceType {
    AS_TRADED_EQUITY,
    MERGER,
    SPLIT,
    DIVIDEND,
    TRADE,
    TRANSACTION,
    ORDER,
    EMPTY,
    DONE,
    CUSTOM,
    BENCHMARK,
    COMMISSION,
    CLOSE_POSITION
};

std::vector<std::string> DIVIDEND_FIELDS = {
        "declared_date",
        "ex_date",
        "gross_amount",
        "net_amount",
        "pay_date",
        "payment_sid",
        "ratio",
        "sid",
};
std::vector<std::string> DIVIDEND_PAYMENT_FIELDS = {
        "id",
        "payment_sid",
        "cash_amount",
        "share_count",
};

struct Event {
    std::map<std::string, std::string> values;

    Event(std::map<std::string, std::string> initial_values) : values(initial_values) {}

    std::map<std::string, std::string> keys() {
        return values;
    }

    bool operator==(const Event& other) const {
        return values == other.values;
    }

    bool contains(const std::string& name) const {
        return values.find(name) != values.end();
    }
};

struct Order : public Event {
    using Event::Event;
};

struct Position {
    Asset asset;
    int amount;
    float cost_basis;
    float last_sale_price;
    std::string last_sale_date;

    Position(Asset asset, int amount, float cost_basis, float last_sale_price, std::string last_sale_date)
            : asset(asset), amount(amount), cost_basis(cost_basis), last_sale_price(last_sale_price), last_sale_date(last_sale_date) {}
    std::string toString() const {
        std::ostringstream os;
        os << "Position("
           << "asset: " << asset << ", "
           << "amount: " << amount << ", "
           << "cost_basis: " << cost_basis << ", "
           << "last_sale_price: " << last_sale_price << ", "
           << "last_sale_date: " << last_sale_date
           << ")";
        return os.str();
    }
    Asset getSid() const {
        return asset;
    }
};

struct Positions : public std::map<std::string, Position> {
    using std::map<std::string, Position>::map;
};

struct Portfolio {
    Positions positions;
    float cash;
    float cash_flow;
    float portfolio_value;
    float starting_cash;
    float positions_value;
    float positions_exposure;

    float pnl;
    float returns;
    std::string start_date;

    Portfolio(std::string start_date, float starting_cash) :
    starting_cash(starting_cash),
    cash(starting_cash),
    portfolio_value(starting_cash),
    start_date(start_date),
    positions_value(0.0),
    positions_exposure(0.0),
    positions(Positions()),
    returns(0.0),
    pnl(0.0),
    cash_flow(0.0)
    {}

    float capital_used() const {
        return cash_flow;
    }
    std::string toString() const {
        std::ostringstream os;
        os << "Portfolio("
           << "cash_flow: " << cash_flow << ", "
           << "starting_cash: " << starting_cash << ", "
           << "portfolio_value: " << portfolio_value << ", "
           << "pnl: " << pnl << ", "
           << "returns: " << returns << ", "
           << "cash: " << cash << ", "
           << "start_date: " << start_date << ", "
           << "positions_value: " << positions_value << ", "
           << "positions_exposure: " << positions_exposure
           << ")";
        return os.str();
    }

    std::map<std::string, float> current_portfolio_weights() const {
        std::map<std::string, float> weights;
        for (const auto& [key, position] : positions) {
            weights[key] = position.last_sale_price * position.amount / portfolio_value;
        }
        return weights;
    }
    float getPortfolioValue() const {
        float total_value = 0.0f;

        // Calculate total portfolio value
        for (const auto& [asset, position] : positions) {
            total_value += position.last_sale_price * position.amount * position.price_multiplier;
        }
        return total_value;
    }
};

struct Account {
    float settled_cash;
    float accrued_interest;
    float buying_power;
    float equity_with_loan;
    float total_positions_value;
    float total_positions_exposure;
    float regt_equity;
    float regt_margin;
    float initial_margin_requirement;
    float maintenance_margin_requirement;
    float available_funds;
    float excess_liquidity;
    float cushion;
    float day_trades_remaining;
    float leverage;
    float net_leverage;
    float net_liquidation;

    std::string toString() const {
        std::ostringstream os;
        os << "Account("
           << "settled_cash: " << settled_cash << ", "
           << "accrued_interest: " << accrued_interest << ", "
           << "buying_power: " << buying_power << ", "
           << "equity_with_loan: " << equity_with_loan << ", "
           << "total_positions_value: " << total_positions_value << ", "
           << "total_positions_exposure: " << total_positions_exposure << ", "
           << "regt_equity: " << regt_equity << ", "
           << "regt_margin: " << regt_margin << ", "
           << "initial_margin_requirement: " << initial_margin_requirement << ", "
           << "maintenance_margin_requirement: " << maintenance_margin_requirement << ", "
           << "available_funds: " << available_funds << ", "
           << "excess_liquidity: " << excess_liquidity << ", "
           << "cushion: " << cushion << ", "
           << "day_trades_remaining: " << day_trades_remaining << ", "
           << "leverage: " << leverage << ", "
           << "net_leverage: " << net_leverage << ", "
           << "net_liquidation: " << net_liquidation
           << ")";
        return os.str();
    }
};