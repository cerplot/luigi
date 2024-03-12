#include <toml++/toml.h>
#include <map>
#include <string>
#include <iostream>
#include <fstream>
#include <vector>


class StepConfig{
private:
    static StepConfig* _instance;
    static std::vector<std::string> _config_paths;
    std::map<std::string, std::map<std::string, toml::value>> data;

public:
    static StepConfig* instance() {
        if (_instance == nullptr) {
            _instance = new StepConfig();
            _instance->read(_config_paths);
        }
        return _instance;
    }

    static void add_config_path(const std::string& path) {
        _config_paths.push_back(path);
        instance()->read(_config_paths);
    }

    static void reload() {
        instance()->read(_config_paths);
    }
    void read(const std::vector<std::string>& config_paths) override {
        for (const auto& path : config_paths) {
            std::ifstream file(path);
            if (file.is_open()) {
                auto table = toml::parse(file);
                for (const auto& [key, value] : table) {
                    if (value.is_table()) {
                        for (const auto& [subkey, subvalue] : *value.as_table()) {
                            data[key][subkey] = subvalue;
                        }
                    }
                }
            }
        }
    }

    toml::value get(const std::string& section, const std::string& option, const toml::value& default_value = toml::value{}) {
        if (data.find(section) != data.end() && data[section].find(option) != data[section].end()){
            return data[section][option];
        }
        return default_value;
    }

    bool getboolean(const std::string& section, const std::string& option, bool default_value = false) {
        auto value = get(section, option, toml::value{default_value});
        return value.as_boolean();
    }

    int64_t getint(const std::string& section, const std::string& option, int64_t default_value = 0) {
        auto value = get(section, option, toml::value{default_value});
        return value.as_integer();
    }

    double getfloat(const std::string& section, const std::string& option, double default_value = 0.0) {
        auto value = get(section, option, toml::value{default_value});
        return value.as_floating_point();
    }

    std::map<std::string, int64_t> getintdict(const std::string& section) {
        std::map<std::string, int64_t> result;
        if (data.find(section) != data.end()) {
            for (const auto& [key, value] : data[section]) {
                if (value.is_integer()) {
                    result[key] = value.as_integer();
                }
            }
        }
        return result;
    }

    void set(const std::string& section, const std::string& option, const toml::value& value) {
        data[section][option] = value;
    }

    bool has_option(const std::string& section, const std::string& option) {
        return data.find(section) != data.end() && data[section].find(option) != data[section].end();
    }

    std::map<std::string, toml::value> operator[](const std::string& name) {
        return data[name];
    }
};

StepConfig* StepConfig::_instance = nullptr;
std::vector<std::string> StepConfig::_config_paths = {
        "/etc/trun/trun.toml", "trun.toml"};
