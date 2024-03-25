#include "parm.h"

namespace te {

    Parm::Parm(
            std::string defaultValue,
            bool significant,
            std::string description,
            bool alwaysInHelp,
            ParameterVisibility visibility):
            defaultValue(defaultValue),
            significant(significant),
            visibility(visibility),
            description(description),
            alwaysInHelp(alwaysInHelp){
            order = counter++;
    }

    std::string Parm::parse(std::string x) {
        return x;  // default implementation
    }
    std::string Parm::serialize(std::string x) {
        return x;  // default implementation
    }
    std::string Parm::normalize(std::string x) {
        return x;  // default implementation
    }
    std::string Parm::getValueFromConfig(std::string section, std::string name) {
        conf = StepConfig::instance();
        try {
            value = conf.get(section, name);
        } catch (std::exception& e) {
            return _no_value;
        }
        return parse(value);
    }

    std::string Parm::getValue(std::string step_name, std::string param_name) {
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
        std::string Parm::parser_global_dest(const std::string& param_name, const std::string& step_name) {
            return step_name + "_" + param_name;
        }
        std::map<std::string, std::string> Parm::parser_kwargs(const std::string& param_name, const std::string& step_name = "") {
            std::map<std::string, std::string> kwargs;
            kwargs["action"] = "store";
            kwargs["dest"] = step_name.empty() ? param_name : parser_global_dest(param_name, step_name);
            return kwargs;
        }

        std::vector<std::pair<std::string, std::string>> Parm::valueIterator(std::string step_name, std::string param_name) {
            std::vector<std::pair<std::string, std::string>> values;
            CmdlineParser* cp_parser = CmdlineParser::instance();
            if (cp_parser) {
                std::string dest = parser_global_dest(param_name, step_name);
                std::string found = cp_parser->known_args[dest];
                values.push_back({_parse_or_no_value(found), ""});
            }
            values.push_back({getValueFromConfig(step_name, param_name), ""});
            values.push_back({_default, ""});
            return values;
        }
        bool Parm::has_step_value(std::string step_name, std::string param_name) {
            return get_value(step_name, param_name) != _no_value;
        }
        std::string Parm::getName() {
            return name;
        }
        std::string Parm::_parse_or_no_value(const std::string& x) {
            if (x.empty()) {
                return _no_value;
            } else {
                return parse(x);
            }
        }
    int Parm::counter = 0;

}
