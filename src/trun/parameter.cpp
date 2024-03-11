#include <string>
#include <map>
#include <functional>
#include <stdexcept>
#include <algorithm>
#include <filesystem>
#include <set>
#include <functional>
#include <tuple>
#include <nlohmann/json.hpp>
#include <map>
#include <string>
#include <vector>
#include <sstream>
#include <regex>
#include <stdexcept>
#include <chrono>
#include <ctime>
#include <string>
#include <stdexcept>


enum class ParameterVisibility {
    PUBLIC = 0, //default
    HIDDEN = 1,
    PRIVATE = 2
};

bool has_value(ParameterVisibility value) {
    return value == ParameterVisibility::PUBLIC || value == ParameterVisibility::HIDDEN || value == ParameterVisibility::PRIVATE;
}

int serialize(ParameterVisibility value) {
    return static_cast<int>(value);
}

class ParameterException : public std::exception {
public:
    const char* what() const throw() {
        return "Base exception.";
    }
};

class MissingParameterException : public ParameterException {
public:
    const char* what() const throw() {
        return "Exception signifying that there was a missing Parameter.";
    }
};

class UnknownParameterException : public ParameterException {
public:
    const char* what() const throw() {
        return "Exception signifying that an unknown Parameter was supplied.";
    }
};

class DuplicateParameterException : public ParameterException {
public:
    const char* what() const throw() {
        return "Exception signifying that a Parameter was specified multiple times.";
    }
};

class OptionalParameterTypeWarning : public std::exception {
public:
    const char* what() const throw() {
        return "Warning class for OptionalParameterMixin with wrong type.";
    }
};

class UnconsumedParameterWarning : public std::exception {
public:
    const char* what() const throw() {
        return "Warning class for parameters that are not consumed by the step.";
    }
};


class Parameter {
private:
    std::string name;
    static int counter;
    std::string defaultValue;
    std::function<std::string(std::vector<std::string>)> batchMethod;
    bool significant;
    bool positional;
    ParameterVisibility visibility;
    std::string description;
    bool alwaysInHelp;
    int order;

public:
    Parameter(
            std::string name,
            std::string defaultValue = "",
            bool significant = true,
            std::string description = "",
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : defaultValue(defaultValue), significant(significant), positional(positional), visibility(visibility),
              description(description), alwaysInHelp(alwaysInHelp), batchMethod(batchMethod) {
        order = counter++;
    }

    virtual std::string parse(std::string x) {
        return x;  // default implementation
    }

    virtual std::string serialize(std::string x) {
        return x;  // default implementation
    }

    std::string normalize(std::string x) {
        return x;  // default implementation
    }

    std::string getValueFromConfig(std::string section, std::string name) {
        if (_config.find(section) != _config.end() && _config[section].find(name) != _config[section].end()) {
            return _config[section][name];
        }
        return _no_value;  // probably should be nullptr
    }

    std::string getValue(std::string step_name, std::string param_name) {
        for (auto const& [value, warn] : valueIterator(step_name, param_name)) {
            if (value != _no_value) {
                if (!warn.empty()) {
                    std::cerr << "DeprecationWarning: " << warn << std::endl;
                }
                return value;
            }
        }
        return _no_value;
    }
    static std::string parser_global_dest(const std::string& param_name, const std::string& step_name) {
        return step_name + "_" + param_name;
    }
    static std::map<std::string, std::string> parser_kwargs(const std::string& param_name, const std::string& step_name = "") {
        std::map<std::string, std::string> kwargs;
        kwargs["action"] = "store";
        kwargs["dest"] = step_name.empty() ? param_name : parser_global_dest(param_name, step_name);
        return kwargs;
    }

    std::vector<std::pair<std::string, std::string>> valueIterator(std::string step_name, std::string param_name) {
        std::vector<std::pair<std::string, std::string>> values;
        CmdlineParser* cp_parser = CmdlineParser::get_instance();
        if (cp_parser) {
            std::string dest = parser_global_dest(param_name, step_name);
            std::string found = cp_parser->known_args[dest];
            values.push_back({_parse_or_no_value(found), ""});
        }
        values.push_back({getValueFromConfig(step_name, param_name), ""});
        if (!_config_path.empty()) {
            values.push_back({getValueFromConfig(_config_path["section"], _config_path["name"]),
                              "The use of the configuration [" + _config_path["section"] + "] " + _config_path["name"] +
                              " is deprecated. Please use [" + step_name + "] " + param_name});
        }
        values.push_back({_default, ""});
        return values;
    }
    bool has_step_value(std::string step_name, std::string param_name) {
        return get_value(step_name, param_name) != _no_value;
    }
    std::string getName() {
        return name;
    }
};

int Parameter::counter = 0;


std::chrono::system_clock::time_point UNIX_EPOCH = std::chrono::system_clock::from_time_t(0);


class _DateParameterBase {
protected:
    int interval;
    std::tm start;
    virtual std::string get_date_format() const = 0;  // Pure virtual function

public:
    _DateParameterBase(int interval = 1, std::tm start = {}) : interval(interval), start(start) {
        if (start.tm_year == 0 && start.tm_mon == 0 && start.tm_mday == 0) {
            this->start = {0, 0, 0, 1, 0, 70};  // Default to 1970-01-01
        }
    }

    std::tm parse(const std::string& s) {
        std::tm dt;
        std::istringstream ss(s);
        ss >> std::get_time(&dt, get_date_format().c_str());
        if (ss.fail()) {
            throw std::runtime_error("Failed to parse date");
        }
        return dt;
    }

    std::string serialize(const std::tm& dt) {
        std::ostringstream ss;
        ss << std::put_time(&dt, get_date_format().c_str());
        return ss.str();
    }
};
class DateParameter : public _DateParameterBase {
public:
    DateParameter(int interval = 1, std::tm start = {}) : _DateParameterBase(interval, start) {}

    std::string get_date_format() const override {
        return "%Y-%m-%d";  // Date format is YYYY-MM-DD
    }

    std::tm next_in_enumeration(const std::tm& value) {
        std::tm next_value = value;
        next_value.tm_mday += interval;  // Add interval to the day
        std::mktime(&next_value);  // Normalize the date
        return next_value;
    }

    std::tm normalize(std::tm value) {
        if (value.tm_year == 0 && value.tm_mon == 0 && value.tm_mday == 0) {
            return value;  // If value is None, return None
        }

        // Calculate the number of days between value and start
        std::chrono::system_clock::time_point tp_value = std::chrono::system_clock::from_time_t(std::mktime(&value));
        std::chrono::system_clock::time_point tp_start = std::chrono::system_clock::from_time_t(std::mktime(&start));
        auto duration = std::chrono::duration_cast<std::chrono::hours>(tp_value - tp_start).count() / 24;

        // Calculate the remainder of the division by interval
        int delta = duration % interval;

        // Subtract the remainder from the day of value
        value.tm_mday -= delta;
        std::mktime(&value);  // Normalize the date

        return value;
    }
};
class MonthParameter : public DateParameter {
public:
    MonthParameter(int interval = 1, std::tm start = {}) : DateParameter(interval, start) {}

    std::string get_date_format() const override {
        return "%Y-%m";  // Date format is YYYY-MM
    }

    std::tm add_months(const std::tm& date, int months) {
        std::tm result = date;
        result.tm_year += (date.tm_mon + months - 1) / 12;
        result.tm_mon = (date.tm_mon + months - 1) % 12 + 1;
        result.tm_mday = 1;
        std::mktime(&result);  // Normalize the date
        return result;
    }

    std::tm next_in_enumeration(const std::tm& value) override {
        return add_months(value, interval);
    }

    std::tm normalize(std::tm value) override {
        if (value.tm_year == 0 && value.tm_mon == 0 && value.tm_mday == 0) {
            return value;  // If value is None, return None
        }

        // Calculate the number of months between value and start
        int months_since_start = (value.tm_year - start.tm_year) * 12 + (value.tm_mon - start.tm_mon);

        // Calculate the remainder of the division by interval
        int delta = months_since_start % interval;

        // Subtract the remainder from the month of value
        return add_months(start, months_since_start - delta);
    }
};

class YearParameter : public DateParameter {
public:
    YearParameter(int interval = 1, std::tm start = {}) : DateParameter(interval, start) {}

    std::string get_date_format() const override {
        return "%Y";  // Date format is YYYY
    }

    std::tm add_years(const std::tm& date, int years) {
        std::tm result = date;
        result.tm_year += years;
        result.tm_mon = 1;
        result.tm_mday = 1;
        std::mktime(&result);  // Normalize the date
        return result;
    }

    std::tm next_in_enumeration(const std::tm& value) override {
        return add_years(value, interval);
    }

    std::tm normalize(std::tm value) override {
        if (value.tm_year == 0 && value.tm_mon == 0 && value.tm_mday == 0) {
            return value;  // If value is None, return None
        }

        // Calculate the number of years between value and start
        int years_since_start = value.tm_year - start.tm_year;

        // Calculate the remainder of the division by interval
        int delta = years_since_start % interval;

        // Subtract the remainder from the year of value
        return add_years(value, -delta);
    }
};


class _DatetimeParameterBase : public Parameter {
protected:
    int interval;
    std::chrono::system_clock::time_point start;
    virtual std::string get_date_format() const = 0;  // Pure virtual function
    virtual std::chrono::seconds get_timedelta() const = 0;  // Pure virtual function

public:
    _DatetimeParameterBase(int interval = 1, std::chrono::system_clock::time_point start = std::chrono::system_clock::from_time_t(0))
            : Parameter(), interval(interval), start(start) {}

    std::tm parse(const std::string& s) {
        std::tm dt;
        std::istringstream ss(s);
        ss >> std::get_time(&dt, get_date_format().c_str());
        if (ss.fail()) {
            throw std::runtime_error("Failed to parse datetime");
        }
        return dt;
    }

    std::string serialize(const std::tm& dt) {
        std::ostringstream ss;
        ss << std::put_time(&dt, get_date_format().c_str());
        return ss.str();
    }

    std::tm normalize(std::tm dt) {
        if (dt.tm_year == 0 && dt.tm_mon == 0 && dt.tm_mday == 0 && dt.tm_hour == 0 && dt.tm_min == 0 && dt.tm_sec == 0) {
            return dt;  // If dt is None, return None
        }

        // Convert dt and start to time_points
        std::chrono::system_clock::time_point tp_dt = std::chrono::system_clock::from_time_t(std::mktime(&dt));

        // Calculate the number of seconds between dt and start
        auto duration = std::chrono::duration_cast<std::chrono::seconds>(tp_dt - start);

        // Calculate the remainder of the division by interval
        auto delta = duration % (get_timedelta() * interval);

        // Subtract the remainder from dt
        tp_dt -= delta;

        // Convert tp_dt back to std::tm
        std::time_t tt_dt = std::chrono::system_clock::to_time_t(tp_dt);
        dt = *std::localtime(&tt_dt);

        return dt;
    }

    std::tm next_in_enumeration(std::tm value) {
        // Convert value to time_point
        std::chrono::system_clock::time_point tp_value = std::chrono::system_clock::from_time_t(std::mktime(&value));

        // Add interval * timedelta to value
        tp_value += get_timedelta() * interval;

        // Convert tp_value back to std::tm
        std::time_t tt_value = std::chrono::system_clock::to_time_t(tp_value);
        value = *std::localtime(&tt_value);

        return value;
    }
};

class DateHourParameter : public _DatetimeParameterBase {
public:
    DateHourParameter(int interval = 1, std::chrono::system_clock::time_point start = std::chrono::system_clock::from_time_t(0))
            : _DatetimeParameterBase(interval, start) {}

    std::string get_date_format() const override {
        return "%Y-%m-%dT%H";  // Datetime format is YYYY-MM-DDTHH
    }

    std::chrono::seconds get_timedelta() const override {
        return std::chrono::hours(1);  // One hour
    }
};

class DateMinuteParameter : public _DatetimeParameterBase {
public:
    DateMinuteParameter(int interval = 1, std::chrono::system_clock::time_point start = std::chrono::system_clock::from_time_t(0))
            : _DatetimeParameterBase(interval, start) {}

    std::string get_date_format() const override {
        return "%Y-%m-%dT%H%M";  // Datetime format is YYYY-MM-DDTHHMM
    }

    std::chrono::seconds get_timedelta() const override {
        return std::chrono::minutes(1);  // One minute
    }

    std::tm parse(const std::string& s) override {
        std::tm dt;
        std::istringstream ss(s);
        ss >> std::get_time(&dt, "%Y-%m-%dT%HH%M");
        if (ss.fail()) {
            ss.clear();
            ss.str(s);
            ss >> std::get_time(&dt, get_date_format().c_str());
            if (ss.fail()) {
                throw std::runtime_error("Failed to parse datetime");
            }
        } else {
            std::cerr << "Warning: Using \"H\" between hours and minutes is deprecated, omit it instead." << std::endl;
        }
        return dt;
    }
};

class DateSecondParameter : public _DatetimeParameterBase {
public:
    DateSecondParameter(int interval = 1, std::chrono::system_clock::time_point start = std::chrono::system_clock::from_time_t(0))
            : _DatetimeParameterBase(interval, start) {}

    std::string get_date_format() const override {
        return "%Y-%m-%dT%H%M%S";  // Datetime format is YYYY-MM-DDTHHMMSS
    }

    std::chrono::seconds get_timedelta() const override {
        return std::chrono::seconds(1);  // One second
    }
};

class IntParameter : public Parameter {
public:
    IntParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    int parse(const std::string& s) override {
        return std::stoi(s);
    }

    int next_in_enumeration(int value) {
        return value + 1;
    }
};

class FloatParameter : public Parameter {
public:
    FloatParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    float parse(const std::string& s) override {
        return std::stof(s);
    }
};

class BoolParameter : public Parameter {
public:
    static const std::string IMPLICIT_PARSING;
    static const std::string EXPLICIT_PARSING;

    std::string parsing;

    BoolParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC,
            std::string parsing = IMPLICIT_PARSING)
            : Parameter(name, defaultValue == "" ? "false" : defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility), parsing(parsing) {}

    bool parse(const std::string& s) override {
        std::string lower_s = s;
        std::transform(lower_s.begin(), lower_s.end(), lower_s.begin(), ::tolower);
        if (lower_s == "true") {
            return true;
        } else if (lower_s == "false") {
            return false;
        } else {
            throw std::invalid_argument("cannot interpret '" + s + "' as boolean");
        }
    }

    bool normalize(std::string value) override {
        try {
            return parse(value);
        } catch (std::invalid_argument&) {
            return false;  // Return false if parsing fails
        }
    }

    // The _parser_kwargs function is not applicable in C++ as it is specific to Python's argparse library
};

const std::string BoolParameter::IMPLICIT_PARSING = "implicit";
const std::string BoolParameter::EXPLICIT_PARSING = "explicit";






class DateIntervalParameter : public Parameter {
public:
    DateIntervalParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    // TODO: Implement parse function
    // This function should attempt to parse the input string into various date interval types.
    // If none of the parsing attempts are successful, it should throw an exception.
    // Note: C++ does not have built-in support for parsing date intervals in the ISO 8601 format.
    // You would need to implement your own parsing logic or use a third-party library that supports ISO 8601 date intervals.
};



class TimeDeltaParameter : public Parameter {
public:
    TimeDeltaParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    std::chrono::seconds parse(const std::string& s) override {
        try {
            return std::chrono::seconds(static_cast<int>(std::stof(s)));
        } catch (std::invalid_argument&) {
            // Ignore exception and continue with other parsing methods
        }

        std::regex iso8601_regex("P(([0-9]+)W)?(([0-9]+)D)?(T(([0-9]+)H)?(([0-9]+)M)?(([0-9]+)S)?)?");
        std::smatch match;
        if (std::regex_match(s, match, iso8601_regex)) {
            int weeks = match[2].length() > 0 ? std::stoi(match[2]) : 0;
            int days = match[4].length() > 0 ? std::stoi(match[4]) : 0;
            int hours = match[7].length() > 0 ? std::stoi(match[7]) : 0;
            int minutes = match[9].length() > 0 ? std::stoi(match[9]) : 0;
            int seconds = match[11].length() > 0 ? std::stoi(match[11]) : 0;
            return std::chrono::seconds((weeks * 7 * 24 * 60 * 60) + (days * 24 * 60 * 60) + (hours * 60 * 60) + (minutes * 60) + seconds);
        }

        std::regex simple_regex("(([0-9]+) ?w(eeks?)? ?)?(([0-9]+) ?d(ays?)? ?)?(([0-9]+) ?h(ours?)? ?)?(([0-9]+) ?m(inutes?)? ?)?(([0-9]+) ?s(econds?)? ?)?");
        if (std::regex_match(s, match, simple_regex)) {
            int weeks = match[2].length() > 0 ? std::stoi(match[2]) : 0;
            int days = match[5].length() > 0 ? std::stoi(match[5]) : 0;
            int hours = match[8].length() > 0 ? std::stoi(match[8]) : 0;
            int minutes = match[11].length() > 0 ? std::stoi(match[11]) : 0;
            int seconds = match[14].length() > 0 ? std::stoi(match[14]) : 0;
            return std::chrono::seconds((weeks * 7 * 24 * 60 * 60) + (days * 24 * 60 * 60) + (hours * 60 * 60) + (minutes * 60) + seconds);
        }

        throw std::invalid_argument("Invalid time delta - could not parse " + s);
    }

    std::string serialize(std::chrono::seconds x) override {
        int total_seconds = x.count();
        int weeks = total_seconds / (7 * 24 * 60 * 60);
        total_seconds %= 7 * 24 * 60 * 60;
        int days = total_seconds / (24 * 60 * 60);
        total_seconds %= 24 * 60 * 60;
        int hours = total_seconds / (60 * 60);
        total_seconds %= 60 * 60;
        int minutes = total_seconds / 60;
        total_seconds %= 60;
        int seconds = total_seconds;

        return std::to_string(weeks) + " w " + std::to_string(days) + " d " + std::to_string(hours) + " h " + std::to_string(minutes) + " m " + std::to_string(seconds) + " s";
    }
};

class Step;  // Forward declaration

class StepRegister {
public:
    static Step* get_step_cls(const std::string& name) {
        // TODO: Implement this function to return a new instance of the Step subclass associated with the given name
        // You would need to maintain a map of strings to Step subclasses, and create a new instance of the appropriate subclass here
        return nullptr;
    }
};

class Step {
public:
    static std::string get_step_family() {
        // TODO: Override this function in each Step subclass to return the appropriate family name
        return "";
    }
};

class StepParameter : public Parameter {
public:
    StepParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    Step* parse(const std::string& s) override {
        return StepRegister::get_step_cls(s);
    }

    std::string serialize(Step* cls) override {
        return cls->get_step_family();
    }
};



class Enum {
public:
    virtual std::string to_string() const = 0;  // Convert the enum value to a string
    virtual void from_string(const std::string& s) = 0;  // Convert a string to the enum value
};

class EnumListParameter : public Parameter {
private:
    Enum* enumInstance;

public:
    EnumListParameter(
            std::string name,
            Enum* enumInstance,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility), enumInstance(enumInstance) {}

    std::vector<Enum> parse(const std::string& s) override {
        std::vector<Enum> values;
        std::istringstream ss(s);
        std::string item;
        while (std::getline(ss, item, ',')) {
            Enum e = *enumInstance;
            e.from_string(item);
            values.push_back(e);
        }
        return values;
    }

    std::string serialize(const std::vector<Enum>& enum_values) override {
        std::ostringstream ss;
        for (size_t i = 0; i < enum_values.size(); ++i) {
            if (i != 0) {
                ss << ",";
            }
            ss << enum_values[i].to_string();
        }
        return ss.str();
    }
};



class DictParameter : public Parameter {
private:
    // TODO: Implement a Schema class or use a third-party library that supports JSON schema validation
    // Schema* schema;

public:
    DictParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
    // TODO: Add a schema argument to the constructor if you implement a Schema class
    // Schema* schema = nullptr)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {
        // this->schema = schema;
    }

    std::map<std::string, std::string> parse(const std::string& s) override {
        nlohmann::json j = nlohmann::json::parse(s);
        std::map<std::string, std::string> dict = j.get<std::map<std::string, std::string>>();
        // TODO: Validate the dict against the schema if you implement a Schema class
        // if (schema) {
        //     schema->validate(dict);
        // }
        return dict;
    }

    std::string serialize(const std::map<std::string, std::string>& dict) override {
        nlohmann::json j = dict;
        return j.dump();
    }
};

class ListParameter : public Parameter {
private:
    // TODO: Implement a Schema class or use a third-party library that supports JSON schema validation
    // Schema* schema;

public:
    ListParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
    // TODO: Add a schema argument to the constructor if you implement a Schema class
    // Schema* schema = nullptr)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {
        // this->schema = schema;
    }

    std::vector<std::string> parse(const std::string& s) override {
        nlohmann::json j = nlohmann::json::parse(s);
        std::vector<std::string> list = j.get<std::vector<std::string>>();
        // TODO: Validate the list against the schema if you implement a Schema class
        // if (schema) {
        //     schema->validate(list);
        // }
        return list;
    }

    std::string serialize(const std::vector<std::string>& list) override {
        nlohmann::json j = list;
        return j.dump();
    }
};



class TupleParameter : public ListParameter {
public:
    TupleParameter(
            std::string name,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : ListParameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility) {}

    std::vector<std::tuple<int, int>> parse(const std::string& s) override {
        nlohmann::json j = nlohmann::json::parse(s);
        std::vector<std::tuple<int, int>> tuples = j.get<std::vector<std::tuple<int, int>>>();
        return tuples;
    }

    std::string serialize(const std::vector<std::tuple<int, int>>& tuples) override {
        nlohmann::json j = tuples;
        return j.dump();
    }
};


template <typename T>
class NumericalParameter : public Parameter {
private:
    T minValue;
    T maxValue;
    std::function<bool(T, T)> leftOp;
    std::function<bool(T, T)> rightOp;

public:
    NumericalParameter(
            std::string name,
            T minValue,
            T maxValue,
            std::function<bool(T, T)> leftOp = std::less_equal<T>(),
            std::function<bool(T, T)> rightOp = std::less<T>(),
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility),
              minValue(minValue), maxValue(maxValue), leftOp(leftOp), rightOp(rightOp) {
        if (!description.empty()) {
            description += " ";
        }
        description += "Permitted values: " + std::to_string(minValue) + " to " + std::to_string(maxValue);
    }

    T parse(const std::string& s) override {
        T value = static_cast<T>(std::stod(s));
        if (leftOp(minValue, value) && rightOp(value, maxValue)) {
            return value;
        } else {
            throw std::invalid_argument(s + " is not in the set of permitted values: " + std::to_string(minValue) + " to " + std::to_string(maxValue));
        }
    }
};


template <typename T>
class ChoiceParameter : public Parameter {
private:
    std::set<T> choices;

public:
    ChoiceParameter(
            std::string name,
            std::set<T> choices,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility), choices(choices) {
        if (!description.empty()) {
            description += " ";
        }
        description += "Choices: {";
        for (const T& choice : choices) {
            description += std::to_string(choice) + ", ";
        }
        description = description.substr(0, description.length() - 2);  // Remove the trailing comma and space
        description += "}";
    }

    T parse(const std::string& s) override {
        return static_cast<T>(std::stod(s));  // Convert the string to a double, and then static_cast to the desired type T
    }

    T normalize(T value) override {
        if (choices.find(value) != choices.end()) {
            return value;
        } else {
            throw std::invalid_argument(std::to_string(value) + " is not a valid choice");
        }
    }
};


class PathParameter : public Parameter {
private:
    bool absolute;
    bool exists;

public:
    PathParameter(
            std::string name,
            bool absolute = false,
            bool exists = false,
            std::string defaultValue = "",
            bool isGlobal = false,
            bool significant = true,
            std::string description = "",
            std::map<std::string, std::string> configPath = {},
            bool positional = true,
            bool alwaysInHelp = false,
            std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : Parameter(name, defaultValue, isGlobal, significant, description, configPath, positional, alwaysInHelp, batchMethod, visibility),
              absolute(absolute), exists(exists) {}

    std::filesystem::path parse(const std::string& s) override {
        std::filesystem::path path(s);
        if (absolute) {
            path = std::filesystem::absolute(path);
        }
        if (exists && !std::filesystem::exists(path)) {
            throw std::invalid_argument("The path " + s + " does not exist.");
        }
        return path;
    }

    std::string serialize(const std::filesystem::path& path) override {
        return path.string();
    }
};