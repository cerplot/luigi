#include <string>
#include <functional>
#include <map>

class Ledger {
    // Assume Ledger class has some fields and methods
};

class Packet {
public:
    std::map<std::string, double> minute_perf;
    std::map<std::string, double> daily_perf;
};

class SimpleLedgerField {
public:
    SimpleLedgerField(std::string ledger_field, std::string packet_field, std::function<double(Ledger&)> getter)
            : _ledger_field(ledger_field), _packet_field(packet_field), _get_ledger_field(getter) {
        if (packet_field.empty()) {
            auto pos = ledger_field.rfind(".");
            _packet_field = (pos == std::string::npos) ? ledger_field : ledger_field.substr(pos + 1);
        }
    }

    void end_of_bar(Packet& packet, Ledger& ledger, /* other parameters */) {
        packet.minute_perf[_packet_field] = _get_ledger_field(ledger);
    }

    void end_of_session(Packet& packet, Ledger& ledger, /* other parameters */) {
        packet.daily_perf[_packet_field] = _get_ledger_field(ledger);
    }

private:
    std::string _ledger_field;
    std::string _packet_field;
    std::function<double(Ledger&)> _get_ledger_field;
};


class DailyLedgerField {
public:
    DailyLedgerField(std::string ledger_field, std::string packet_field, std::function<double(Ledger&)> getter)
            : _ledger_field(ledger_field), _packet_field(packet_field), _get_ledger_field(getter) {
        if (packet_field.empty()) {
            auto pos = ledger_field.rfind(".");
            _packet_field = (pos == std::string::npos) ? ledger_field : ledger_field.substr(pos + 1);
        }
    }

    void end_of_bar(Packet& packet, Ledger& ledger, /* other parameters */) {
        double value = _get_ledger_field(ledger);
        packet.minute_perf[_packet_field] = value;
        packet.cumulative_perf[_packet_field] = value;
    }

    void end_of_session(Packet& packet, Ledger& ledger, /* other parameters */) {
        double value = _get_ledger_field(ledger);
        packet.daily_perf[_packet_field] = value;
        packet.cumulative_perf[_packet_field] = value;
    }

private:
    std::string _ledger_field;
    std::string _packet_field;
    std::function<double(Ledger&)> _get_ledger_field;
};

class StartOfPeriodLedgerField {
public:
    StartOfPeriodLedgerField(std::string ledger_field, std::string packet_field, std::function<double(Ledger&)> getter)
            : _ledger_field(ledger_field), _packet_field(packet_field), _get_ledger_field(getter) {
        if (packet_field.empty()) {
            auto pos = ledger_field.rfind(".");
            _packet_field = (pos == std::string::npos) ? ledger_field : ledger_field.substr(pos + 1);
        }
    }

    void start_of_simulation(Ledger& ledger, /* other parameters */) {
        _start_of_simulation = _get_ledger_field(ledger);
    }

    void start_of_session(Ledger& ledger, /* other parameters */) {
        _previous_day = _get_ledger_field(ledger);
    }

    void _end_of_period(std::string sub_field, Packet& packet, Ledger& ledger) {
        packet.cumulative_perf[_packet_field] = _start_of_simulation;
        packet[sub_field][_packet_field] = _previous_day;
    }

    void end_of_bar(Packet& packet, Ledger& ledger, /* other parameters */) {
        _end_of_period("minute_perf", packet, ledger);
    }

    void end_of_session(Packet& packet, Ledger& ledger, /* other parameters */) {
        _end_of_period("daily_perf", packet, ledger);
    }

private:
    std::string _ledger_field;
    std::string _packet_field;
    std::function<double(Ledger&)> _get_ledger_field;
    double _start_of_simulation;
    double _previous_day;
};


#include <functional>

class Portfolio {
    // Assume Portfolio class has some fields and methods
public:
    double returns;  // Assume this field exists in Portfolio
};

class Ledger {
public:
    double todays_returns;  // Assume this field exists in Ledger
    Portfolio portfolio;  // Assume this field exists in Ledger
};

class Returns {
public:
    void _end_of_period(std::string field, Packet& packet, Ledger& ledger, /* other parameters */) {
        packet[field]["returns"] = ledger.todays_returns;
        packet["cumulative_perf"]["returns"] = ledger.portfolio.returns;
        packet["cumulative_risk_metrics"]["algorithm_period_return"] = ledger.portfolio.returns;
    }

    std::function<void(Packet&, Ledger&, /* other parameters */)> end_of_bar =
            std::bind(&Returns::_end_of_period, this, "minute_perf", std::placeholders::_1, std::placeholders::_2 /*, other placeholders */);

    std::function<void(Packet&, Ledger&, /* other parameters */)> end_of_session =
            std::bind(&Returns::_end_of_period, this, "daily_perf", std::placeholders::_1, std::placeholders::_2 /*, other placeholders */);
};


#include <vector>
#include <cmath>

class BenchmarkSource {
    // Assume BenchmarkSource class has some fields and methods
public:
    std::vector<double> daily_returns(/* parameters */) {
        // Implement this method
    }

    std::vector<double> get_range(/* parameters */) {
        // Implement this method
    }
};

class Calendar {
    // Assume Calendar class has some fields and methods
public:
    std::string session_open(/* parameters */) {
        // Implement this method
    }

    std::string session_close(/* parameters */) {
        // Implement this method
    }
};

class BenchmarkReturnsAndVolatility {
public:
    void start_of_simulation(Ledger& ledger, std::string emission_rate, Calendar& trading_calendar, std::vector<std::string>& sessions, BenchmarkSource& benchmark_source) {
        _daily_returns = benchmark_source.daily_returns(/* parameters */);
        _daily_cumulative_returns = cumulative_returns(_daily_returns);
        _daily_annual_volatility = annual_volatility(_daily_returns);

        if (emission_rate == "daily") {
            // Handle daily emission rate
        } else {
            std::string open_ = trading_calendar.session_open(/* parameters */);
            std::string close = trading_calendar.session_close(/* parameters */);
            std::vector<double> returns = benchmark_source.get_range(/* parameters */);
            _minute_cumulative_returns = cumulative_returns(returns);
            _minute_annual_volatility = annual_volatility(returns);
        }
    }

    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        double r = _minute_cumulative_returns[/* index corresponding to dt */];
        packet["cumulative_risk_metrics"]["benchmark_period_return"] = r;

        double v = _minute_annual_volatility[/* index corresponding to dt */];
        packet["cumulative_risk_metrics"]["benchmark_volatility"] = v;
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string session, int session_ix, /* other parameters */) {
        double r = _daily_cumulative_returns[session_ix];
        packet["cumulative_risk_metrics"]["benchmark_period_return"] = r;

        double v = _daily_annual_volatility[session_ix];
        packet["cumulative_risk_metrics"]["benchmark_volatility"] = v;
    }

private:
    std::vector<double> _daily_returns;
    std::vector<double> _daily_cumulative_returns;
    std::vector<double> _daily_annual_volatility;
    std::vector<double> _minute_cumulative_returns;
    std::vector<double> _minute_annual_volatility;

    std::vector<double> cumulative_returns(const std::vector<double>& returns) {
        std::vector<double> cumulative_returns;
        double cumulative_return = 0;
        for (double r : returns) {
            cumulative_return = (1 + cumulative_return) * (1 + r) - 1;
            cumulative_returns.push_back(cumulative_return);
        }
        return cumulative_returns;
    }

    std::vector<double> annual_volatility(const std::vector<double>& returns) {
        std::vector<double> annual_volatility;
        double mean = 0;
        double M2 = 0;
        for (size_t i = 0; i < returns.size(); ++i) {
            double delta = returns[i] - mean;
            mean += delta / (i + 1);
            M2 += delta * (returns[i] - mean);
            if (i >= 1) {
                double variance_n = M2 / i;
                double variance = variance_n * returns.size() / (returns.size() - 1);
                annual_volatility.push_back(std::sqrt(variance) * std::sqrt(252));
            } else {
                annual_volatility.push_back(std::nan(""));
            }
        }
        return annual_volatility;
    }
};

class Portfolio {
    // Assume Portfolio class has some fields and methods
public:
    double pnl;  // Assume this field exists in Portfolio
};

class PNL {
public:
    void start_of_simulation(Ledger& ledger, /* other parameters */) {
        _previous_pnl = 0.0;
    }

    void start_of_session(Ledger& ledger, /* other parameters */) {
        _previous_pnl = ledger.portfolio.pnl;
    }

    void _end_of_period(std::string field, Packet& packet, Ledger& ledger) {
        double pnl = ledger.portfolio.pnl;
        packet[field]["pnl"] = pnl - _previous_pnl;
        packet["cumulative_perf"]["pnl"] = ledger.portfolio.pnl;
    }

    void end_of_bar(Packet& packet, Ledger& ledger, /* other parameters */) {
        _end_of_period("minute_perf", packet, ledger);
    }

    void end_of_session(Packet& packet, Ledger& ledger, /* other parameters */) {
        _end_of_period("daily_perf", packet, ledger);
    }

private:
    double _previous_pnl;
};

class Portfolio {
    // Assume Portfolio class has some fields and methods
public:
    double cash_flow;  // Assume this field exists in Portfolio
};

class CashFlow {
public:
    void start_of_simulation(Ledger& ledger, /* other parameters */) {
        _previous_cash_flow = 0.0;
    }

    void end_of_bar(Packet& packet, Ledger& ledger, /* other parameters */) {
        double cash_flow = ledger.portfolio.cash_flow;
        packet["minute_perf"]["capital_used"] = cash_flow - _previous_cash_flow;
        packet["cumulative_perf"]["capital_used"] = cash_flow;
    }

    void end_of_session(Packet& packet, Ledger& ledger, /* other parameters */) {
        double cash_flow = ledger.portfolio.cash_flow;
        packet["daily_perf"]["capital_used"] = cash_flow - _previous_cash_flow;
        packet["cumulative_perf"]["capital_used"] = cash_flow;
        _previous_cash_flow = cash_flow;
    }

private:
    double _previous_cash_flow;
};



class Ledger {
    // Assume Ledger class has some fields and methods
public:
    std::vector<Order> orders(std::string dt = "") {
        // Implement this method
    }
};

class Orders {
public:
    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.minute_perf["orders"] = ledger.orders(dt).size();
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.daily_perf["orders"] = ledger.orders().size();
    }
};



class Ledger {
    // Assume Ledger class has some fields and methods
public:
    std::vector<Transaction> transactions(std::string dt = "") {
        // Implement this method
    }
};

class Transactions {
public:
    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.minute_perf["transactions"] = ledger.transactions(dt).size();
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.daily_perf["transactions"] = ledger.transactions().size();
    }
};



class Ledger {
    // Assume Ledger class has some fields and methods
public:
    std::vector<Position> positions(std::string dt = "") {
        // Implement this method
    }
};

class Positions {
public:
    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.minute_perf["positions"] = ledger.positions(dt).size();
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet.daily_perf["positions"] = ledger.positions().size();
    }
};


#include <functional>
#include <cmath>

class Ledger {
    // Assume Ledger class has some fields and methods
public:
    std::vector<double> daily_returns_array;  // Assume this field exists in Ledger
};

class ReturnsStatistic {
public:
    ReturnsStatistic(std::function<double(std::vector<double>&)> function, std::string field_name = "")
            : _function(function), _field_name(field_name) {
        if (_field_name.empty()) {
            _field_name = typeid(function).name();
        }
    }

    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        std::vector<double> returns(ledger.daily_returns_array.begin(), ledger.daily_returns_array.begin() + session_ix + 1);
        double res = _function(returns);
        if (!std::isfinite(res)) {
            res = std::nan("");
        }
        packet["cumulative_risk_metrics"][_field_name] = res;
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        end_of_bar(packet, ledger, dt, session_ix /*, other parameters */);
    }

private:
    std::function<double(std::vector<double>&)> _function;
    std::string _field_name;
};


#include <vector>
#include <cmath>
#include <algorithm>

class BenchmarkSource {
    // Assume BenchmarkSource class has some fields and methods
public:
    std::vector<double> daily_returns(std::string start, std::string end) {
        // Implement this method
    }
};

class AlphaBeta {
public:
    void start_of_simulation(Ledger& ledger, std::string emission_rate, Calendar& trading_calendar, std::vector<std::string>& sessions, BenchmarkSource& benchmark_source) {
        _daily_returns_array = benchmark_source.daily_returns(sessions.front(), sessions.back());
    }

    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        std::map<std::string, double>& risk = packet["cumulative_risk_metrics"];

        std::vector<double> ledger_returns(ledger.daily_returns_array.begin(), ledger.daily_returns_array.begin() + session_ix + 1);
        std::vector<double> benchmark_returns(_daily_returns_array.begin(), _daily_returns_array.begin() + session_ix + 1);

        double alpha, beta;
        alpha_beta_aligned(ledger_returns, benchmark_returns, alpha, beta);

        if (!std::isfinite(alpha)) {
            alpha = std::nan("");
        }
        if (std::isnan(beta)) {
            beta = std::nan("");
        }

        risk["alpha"] = alpha;
        risk["beta"] = beta;
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        end_of_bar(packet, ledger, dt, session_ix /*, other parameters */);
    }

private:
    std::vector<double> _daily_returns_array;

    void alpha_beta_aligned(const std::vector<double>& ledger_returns, const std::vector<double>& benchmark_returns, double& alpha, double& beta) {
        // Implement this method
    }

};
class MaxLeverage {
public:
    void start_of_simulation(/* other parameters */) {
        _max_leverage = 0.0;
    }

    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        _max_leverage = std::max(_max_leverage, ledger.account.leverage);
        packet["cumulative_risk_metrics"]["max_leverage"] = _max_leverage;
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        end_of_bar(packet, ledger, dt, session_ix /*, other parameters */);
    }

private:
    double _max_leverage;
};

class NumTradingDays {
public:
    void start_of_simulation(/* other parameters */) {
        _num_trading_days = 0;
    }

    void start_of_session(/* other parameters */) {
        _num_trading_days += 1;
    }

    void end_of_bar(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        packet["cumulative_risk_metrics"]["trading_days"] = _num_trading_days;
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, /* other parameters */) {
        end_of_bar(packet, ledger, dt, session_ix /*, other parameters */);
    }

private:
    int _num_trading_days;
};


class _ConstantCumulativeRiskMetric {
public:
    _ConstantCumulativeRiskMetric(std::string field, double value)
            : _field(field), _value(value) {}

    void end_of_bar(Packet& packet, /* other parameters */) {
        packet["cumulative_risk_metrics"][_field] = _value;
    }

    void end_of_session(Packet& packet, /* other parameters */) {
        packet["cumulative_risk_metrics"][_field] = _value;
    }

private:
    std::string _field;
    double _value;
};



class PeriodLabel {
public:
    void start_of_session(Ledger& ledger, std::string session, /* other parameters */) {
        std::tm tm = {};
        std::stringstream ss(session);
        ss >> std::get_time(&tm, "%Y-%m-%d");
        std::stringstream label;
        label << std::put_time(&tm, "%Y-%m");
        _label = label.str();
    }

    void end_of_bar(Packet& packet, /* other parameters */) {
        packet["cumulative_risk_metrics"]["period_label"] = _label;
    }

    void end_of_session(Packet& packet, /* other parameters */) {
        end_of_bar(packet /*, other parameters */);
    }

private:
    std::string _label;
};


class _ClassicRiskMetrics {
public:
    void start_of_simulation(Ledger& ledger, std::string emission_rate, std::string trading_calendar, std::vector<std::string>& sessions, BenchmarkSource& benchmark_source) {
        _leverages = std::vector<double>(sessions.size(), std::nan(""));
    }

    void end_of_session(Packet& packet, Ledger& ledger, std::string dt, int session_ix, std::string data_portal) {
        _leverages[session_ix] = ledger.account.leverage;
    }
    static std::map<std::string, double> risk_metric_period(
            std::string start_session,
            std::string end_session,
            std::vector<double>& algorithm_returns,
            std::vector<double>& benchmark_returns,
            std::vector<double>& algorithm_leverages
    ) {
        // Implement the method here...

        std::map<std::string, double> rval;
        rval["algorithm_period_return"] = 0.0;  // Replace with actual calculation
        rval["benchmark_period_return"] = 0.0;  // Replace with actual calculation
        rval["treasury_period_return"] = 0;
        rval["excess_return"] = 0.0;  // Replace with actual calculation
        rval["alpha"] = 0.0;  // Replace with actual calculation
        rval["beta"] = 0.0;  // Replace with actual calculation
        rval["sharpe"] = 0.0;  // Replace with actual calculation
        rval["sortino"] = 0.0;  // Replace with actual calculation
        rval["period_label"] = end_session.substr(0, 7);
        rval["trading_days"] = benchmark_returns.size();
        rval["algo_volatility"] = 0.0;  // Replace with actual calculation
        rval["benchmark_volatility"] = 0.0;  // Replace with actual calculation
        rval["max_drawdown"] = 0.0;  // Replace with actual calculation
        rval["max_leverage"] = *std::max_element(algorithm_leverages.begin(), algorithm_leverages.end());

        return rval;
    }

};