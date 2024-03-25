#pragma once

#include <string>
#include <map>
#include <vector>
#include <exception>

namespace te {

enum class ParameterVisibility {
    PUBLIC = 0, //default
    HIDDEN = 1,
    PRIVATE = 2
};

class Parm {
private:
    static int counter;
    std::string defaultValue;
    bool significant;
    ParameterVisibility visibility;
    std::string description;
    bool alwaysInHelp;
    int order;
    std::string _no_value;

public:
    Parm(
            std::string defaultValue = "",
            bool significant = true,
            std::string description = "",
            bool alwaysInHelp = false,
            ParameterVisibility visibility = ParameterVisibility::PUBLIC);

    virtual std::string parse(std::string x);
    virtual std::string serialize(std::string x);
    std::string normalize(std::string x);
    std::string getValueFromConfig(std::string section, std::string name);
    std::string getValue(std::string step_name, std::string param_name);
    static std::string parser_global_dest(const std::string& param_name, const std::string& step_name);
    static std::map<std::string, std::string> parser_kwargs(const std::string& param_name, const std::string& step_name = "");
    std::vector<std::pair<std::string, std::string>> valueIterator(std::string step_name, std::string param_name);
    bool has_step_value(std::string step_name, std::string param_name);
    std::string getName();
    std::string _parse_or_no_value(const std::string& x);
};

extern int Parm::counter;

}