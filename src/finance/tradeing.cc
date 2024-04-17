#include <string>
#include <stdexcept>

class Calendar {
    // Assume Calendar class is defined elsewhere
};

class SimulationParameters {
private:
    std::string start_session;
    std::string end_session;
    Calendar trading_calendar;
    double capital_base;
    std::string emission_rate;
    std::string data_frequency;
    std::string arena;

public:
    SimulationParameters(std::string start_session, std::string end_session, Calendar trading_calendar, double capital_base = 1e5, std::string emission_rate = "daily", std::string data_frequency = "daily", std::string arena = "backtest")
            : start_session(start_session), end_session(end_session), trading_calendar(trading_calendar), capital_base(capital_base), emission_rate(emission_rate), data_frequency(data_frequency), arena(arena) {
        // Add checks for start_session, end_session, and trading_calendar here
    }

    double getCapitalBase() const { return capital_base; }
    std::string getEmissionRate() const { return emission_rate; }
    std::string getDataFrequency() const { return data_frequency; }
    void setDataFrequency(std::string val) { data_frequency = val; }
    std::string getArena() const { return arena; }
    void setArena(std::string val) { arena = val; }
    std::string getStartSession() const { return start_session; }
    std::string getEndSession() const { return end_session; }
    Calendar getCalendar() const { return trading_calendar; }

    std::string SimulationParameters::getFirstOpen() const {
        return first_open;
    }

    std::string SimulationParameters::getLastClose() const {
        return last_close;
    }

    std::vector<std::string> SimulationParameters::getSessions() const {
        return this->_trading_calendar.sessions_in_range(this->getStartSession(), this->getEndSession());
    }


    SimulationParameters SimulationParameters::create_new(std::string start_session, std::string end_session, std::string data_frequency = "") {
        if (data_frequency.empty()) {
            data_frequency = this->getDataFrequency();
        }

        return SimulationParameters(
                start_session,
                end_session,
                this->getCalendar(),
                this->getCapitalBase(),
                this->getEmissionRate(),
                data_frequency,
                this->getArena()
        );
    }

    std::ostream& operator<<(std::ostream& os, const SimulationParameters& params) {
        os << "SimulationParameters(\n"
           << "    start_session=" << params.getStartSession() << ",\n"
           << "    end_session=" << params.getEndSession() << ",\n"
           << "    capital_base=" << params.getCapitalBase() << ",\n"
           << "    data_frequency=" << params.getDataFrequency() << ",\n"
           << "    emission_rate=" << params.getEmissionRate() << ",\n"
           << "    first_open=" << params.getFirstOpen() << ",\n"
           << "    last_close=" << params.getLastClose() << ",\n"
           << "    trading_calendar=" << params.getCalendar() << "\n"
           << ")";
        return os;
    }
};