#include <string>
#include <map>
#include <functional>
#include <stdexcept>
#include <algorithm>

class NoValue {};

enum class ParameterVisibility {
    PUBLIC = 0,
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
    std::map<std::string, std::string> configPath;
    int order;

public:
    Parameter(std::string name, std::string defaultValue = "", bool isGlobal = false, bool significant = true, std::string description = "",
              std::map<std::string, std::string> configPath = {}, bool positional = true, bool alwaysInHelp = false,
              std::function<std::string(std::vector<std::string>)> batchMethod = nullptr,
              ParameterVisibility visibility = ParameterVisibility::PUBLIC)
            : defaultValue(defaultValue), significant(significant), positional(positional), visibility(visibility),
              description(description), alwaysInHelp(alwaysInHelp), configPath(configPath), batchMethod(batchMethod) {
        if (isGlobal) {
            positional = false;
        }
        order = counter++;
    }

    std::string parse(std::string x) {
        return x;  // default implementation
    }

    std::string serialize(std::string x) {
        return x;  // default implementation
    }

    std::string normalize(std::string x) {
        return x;  // default implementation
    }

    std::string get_value_from_config(std::string section, std::string name) {
        if (_config.find(section) != _config.end() && _config[section].find(name) != _config[section].end()) {
            return _config[section][name];
        }
        return _no_value;
    }

    std::string get_value(std::string step_name, std::string param_name) {
        for (auto const& [value, warn] : value_iterator(step_name, param_name)) {
            if (value != _no_value) {
                if (!warn.empty()) {
                    std::cerr << "DeprecationWarning: " << warn << std::endl;
                }
                return value;
            }
        }
        return _no_value;
    }


    std::vector<std::pair<std::string, std::string>> value_iterator(std::string step_name, std::string param_name) {
        std::vector<std::pair<std::string, std::string>> values;
        CmdlineParser* cp_parser = CmdlineParser::get_instance();
        if (cp_parser) {
            std::string dest = parser_global_dest(param_name, step_name);
            std::string found = cp_parser->known_args[dest];
            values.push_back({_parse_or_no_value(found), ""});
        }
        values.push_back({get_value_from_config(step_name, param_name), ""});
        if (!_config_path.empty()) {
            values.push_back({get_value_from_config(_config_path["section"], _config_path["name"]),
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



template <typename T>
class OptionalParameterMixin : public Parameter {
public:
    std::string serialize(T x) override {
        if (x == "") {
            return "";
        } else {
            return Parameter::serialize(x);
        }
    }

    T parse(std::string x) override {
        if (x != typeid(std::string).name()) {
            return x;
        } else if (!x.empty()) {
            return Parameter::parse(x);
        } else {
            return "";
        }
    }

    T normalize(T x) override {
        if (x == "") {
            return "";
        }
        return Parameter::normalize(x);
    }

    void warn_on_wrong_param_type(std::string param_name, T param_value) {
        if (typeid(param_value).name() != typeid(T).name() && param_value != "") {
            std::string param_type = typeid(T).name();
            std::cout << "OptionalParameterTypeWarning: " << typeid(this).name() << " \"" << param_name << "\" with value \"" << param_value << "\" is not of type \"" << param_type << "\" or None." << std::endl;
        }
    }
};

class OptionalParameter : public OptionalParameterMixin<std::string> {
};

class OptionalStrParameter : public OptionalParameterMixin<std::string> {
};
