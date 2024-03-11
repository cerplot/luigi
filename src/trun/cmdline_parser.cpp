#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <variant>

class CmdlineParser {
private:
    static std::optional<CmdlineParser> instance;
    std::map<std::string, std::variant<int, double, std::string>> known_args;

public:
    static CmdlineParser& get_instance() {
        if (!instance) {
            throw std::logic_error("Instance not created");
        }
        return *instance;
    }

    static void create_instance(const std::vector<std::string>& cmdline_args) {
        if (instance) {
            throw std::logic_error("Instance already created");
        }
        instance.emplace(cmdline_args);
    }

    CmdlineParser(const std::vector<std::string>& cmdline_args) {
        // Parse cmdline_args and populate known_args
        for (const auto& arg : cmdline_args) {
            // Parse argument and add to known_args
            // This is a placeholder and needs to be replaced with actual parsing logic
            known_args[arg] = arg;
        }
    }

    static boost::program_options::options_description build_parser(std::string root_step = "", bool help_all = false) {
        boost::program_options::options_description desc("Allowed options");

        // Unfortunately, we have to set it as optional to boost, so we can
        // parse out stuff like `--module` before we call for `--help`.
        desc.add_options()
                ("root_step", boost::program_options::value<std::string>(), "Step family to run. Is not optional.");

        for (auto& param : Register::get_all_params()) {
            std::string step_name = std::get<0>(param);
            bool is_without_section = std::get<1>(param);
            std::string param_name = std::get<2>(param);
            auto param_obj = std::get<3>(param);

            bool is_the_root_step = step_name == root_step;
            std::string help = (is_the_root_step || help_all || param_obj.always_in_help) ? param_obj.description : "";

            std::string flag_name_underscores = is_without_section ? param_name : step_name + "_" + param_name;
            std::string global_flag_name = "--" + flag_name_underscores;

            desc.add_options()
                    (global_flag_name.c_str(), boost::program_options::value<std::string>(), help.c_str());

            if (is_the_root_step) {
                std::string local_flag_name = "--" + param_name;
                desc.add_options()
                        (local_flag_name.c_str(), boost::program_options::value<std::string>(), help.c_str());
            }
        }

        return desc;
    }


    std::variant<int, double, std::string> get_arg(const std::string& arg_name) {
        if (known_args.find(arg_name) == known_args.end()) {
            throw std::invalid_argument("Unknown argument: " + arg_name);
        }
        return known_args[arg_name];
    }
};

std::optional<CmdlineParser> CmdlineParser::instance = std::nullopt;

int main(int argc, char* argv[]) {
    std::vector<std::string> cmdline_args(argv + 1, argv + argc);
    CmdlineParser::create_instance(cmdline_args);
    // Use CmdlineParser::get_instance().get_arg(arg_name) to access arguments
    return 0;
}