#include <fstream>
#include <unordered_map>
#include <stdexcept>
#include <memory>
#include <filesystem>
#include <set>
#include "config_parser.h"

class FileLoadException : public std::runtime_error {
public:
    explicit FileLoadException(const std::string& msg)
            : std::runtime_error(msg) {}
};

class ConfigProcessingException : public std::runtime_error {
public:
    explicit ConfigProcessingException(const std::string& msg)
            : std::runtime_error(msg) {}
};


class ConfigParser {
public:
    ConfigParser(const std::filesystem::path& default_config_file_path)
            : default_config_file_path(default_config_file_path) {}

    std::shared_ptr<toml::table> parseConfigFile(const std::filesystem::path& file_path) {
        if (file_path.empty()) {
            throw FileLoadException("Invalid file path provided: " + file_path.string());
        }
        if (!std::filesystem::exists(file_path)) {
            throw FileLoadException("File does not exist at path: " + file_path.string());
        }
        if (!std::filesystem::is_regular_file(file_path)) {
            throw FileLoadException("File path does not point to a regular file: " + file_path.string());
        }
        std::ifstream file(file_path);
        if (!file.is_open()) {
            throw FileLoadException("Failed to open file at path: " + file_path.string());
        }
        try {
            return std::make_shared<toml::table>(toml::parse(file));
        } catch (const toml::parse_error& e) {
            throw FileLoadException("Failed to parse TOML file at path: " + file_path.string() + ". Error: " + e.what());
        }
    }

    std::shared_ptr<toml::table> loadConfigFile(const std::filesystem::path& config_file_path) {
        if (included_files.find(config_file_path) != included_files.end()) {
            throw std::runtime_error("Circular include detected: " + config_file_path.string() + ". Include chain: " + include_chain);
        }

        included_files.insert(config_file_path);

        auto config = parseConfigFile(config_file_path);
        if (!config || config->empty()) {
            throw ConfigProcessingException("'include' does not exist or is not a table in file: " + config_file_path.string());
        }
        auto node = config->get("include");
        if(node && node->is_table()) {
            auto include = *node->as_table();
            std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
            for (const auto& [key, value] : include) {
                std::filesystem::path relative_path = *value.value<std::string>();
                std::filesystem::path base_path = config_file_path;
                base_path.remove_filename();
                std::filesystem::path full_path = base_path / relative_path;
                file_paths_dict[key.data()] = full_path;
            }
            processIncludedFiles(*config, file_paths_dict, include_chain);
            config->erase("include");
        }
        // Remove the file from the included_files set after it has been processed
        included_files.erase(config_file_path);
        return config;
    }

    std::shared_ptr<toml::table> validateConfigFile(const std::filesystem::path& config_file_path) {
        std::set<std::filesystem::path> included_files;
        auto default_config = loadConfigFile(default_config_file_path);
        auto config = loadConfigFile(config_file_path);

        validateTable(*default_config, *config);

        return config;
    }

    void validateTable(const toml::table& default_config, const toml::table& config, const std::string& location = "") {
        for (const auto& [key, value] : config) {
            std::string new_location = location.empty() ? key.data() : location + "." + key.data();

            if (!default_config.contains(key)) {
                throw ConfigProcessingException("Key '" + new_location + "' not found in default config.");
            }

            const auto& default_value = default_config.at(key);

            if (value.is_table() != default_value.is_table() ||
                value.is_array() != default_value.is_array() ||
                value.is_string() != default_value.is_string() ||
                value.is_integer() != default_value.is_integer() ||
                value.is_floating_point() != default_value.is_floating_point() ||
                value.is_boolean() != default_value.is_boolean() ||
                value.is_date() != default_value.is_date() ||
                value.is_time() != default_value.is_time() ||
                value.is_date_time() != default_value.is_date_time()) {
                throw ConfigProcessingException("Type mismatch for key '" + new_location + "'.");
            }
            if (value.is_table()) {
                validateTable(*default_value.as_table(), *value.as_table(), new_location);
            }
        }
    }

private:
    std::filesystem::path default_config_file_path;
    std::set<std::filesystem::path> included_files;

    void processIncludedFiles(toml::table& merged_data, std::unordered_map<std::string, std::filesystem::path>& file_paths_dict, const std::string& include_chain) {
        for (const auto& [name, file_path] : file_paths_dict) {
            auto data = loadConfigFile(file_path);
            if (name == "_") {
                for (const auto& [key, value] : *data->as_table()) {
                    merged_data.insert_or_assign(key, value);
                }
            } else {
                merged_data.insert_or_assign(name, *data);
            }
        }
    }
};