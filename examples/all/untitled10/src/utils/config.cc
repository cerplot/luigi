#include <fstream>
#include <toml.h>
#include <unordered_map>
#include <stdexcept>
#include <memory>
#include <filesystem>
#include <set>

#include "config.h"

namespace te {

    Config& Config::getConfig() {
        static Config instance;
        return instance;
    }

    std::shared_ptr<toml::table> Config::load_toml_file(const std::filesystem::path &file_path) {
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
            auto table = std::make_shared<toml::table>(toml::parse(file));
            file.close(); // Explicitly close the file after parsing
            return table;
        } catch (const toml::parse_error &e) {
            file.close(); // Make sure to close the file even if an exception occurs
            throw FileLoadException(
                    "Failed to parse TOML file at path: " + file_path.string() + ". Error: " + e.what());
        }
    }

    void Config::process_included_files(std::shared_ptr<toml::table> &config, toml::table &merged_data,
                                        std::unordered_map<std::string, std::filesystem::path> &file_paths_dict,
                                        std::set<std::filesystem::path> &included_files,
                                        const std::string &include_chain) {
        for (const auto &[name, file_path]: file_paths_dict) {

            auto data = load_config_file(file_path, included_files, include_chain + " -> " + file_path.string());
            if (name == "_") {
                for (const auto &[key, value]: *data->as_table()) {
                    merged_data.insert_or_assign(key, value);
                }
            } else {
                merged_data.insert_or_assign(name, *data);
            }
        }
    }

    std::shared_ptr<toml::table> Config::load_config_file(
            const std::filesystem::path &config_file_path, std::set<std::filesystem::path> &included_files,
            const std::string &include_chain) {
        toml::table merged_data;
        try {
            std::unique_lock<std::mutex> lock(included_files_mutex);
            if (included_files.find(config_file_path) != included_files.end()) {
                throw std::runtime_error(
                        "Circular include detected: " + config_file_path.string() + ". Include chain: " +
                        include_chain);
            }
            included_files.insert(config_file_path);
            lock.unlock(); // Unlock the mutex

            auto config = load_toml_file(config_file_path);
            if (config && !config->empty()) { // Check that the shared_ptr is not null and the table is not empty.
                merged_data = *config->as_table();
                auto node = config->get("include");
                if (node && node->is_table()) {
                    auto include = *node->as_table();
                    std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
                    for (const auto &[key, value]: include) {
                        std::filesystem::path relative_path = *value.value<std::string>();
                        std::filesystem::path base_path = config_file_path;
                        base_path.remove_filename();
                        std::filesystem::path full_path = base_path / relative_path;
                        file_paths_dict[key.data()] = full_path;
                    }
                    process_included_files(config, merged_data, file_paths_dict, included_files, include_chain);
                    config->erase("include");
                } // No else clause to throw an exception if 'include' does not exist or is not a table

            } else {
                throw ConfigProcessingException("Config is null or empty for file: " + config_file_path.string());
            }

            // Remove the file from the included_files set after it has been processed
            lock.lock();
            included_files.erase(config_file_path);
            lock.unlock();

        }
        catch (const toml::parse_error &e) {
            throw ConfigProcessingException(config_file_path.string());
        }
        catch (const std::runtime_error &e) {
            throw ConfigProcessingException(e.what());
        }

        return std::make_shared<toml::table>(merged_data);
    }

    std::shared_ptr<toml::table>
    Config::load_config_file(const std::filesystem::path &config_file_path, const std::string &include_chain) {
        std::set<std::filesystem::path> included_files;
        return load_config_file(config_file_path, included_files, include_chain);
    }

    std::shared_ptr<toml::table> Config::validate_config_file(const std::filesystem::path &default_config_file_path,
                                                              const std::filesystem::path &config_file_path) {
        std::set<std::filesystem::path> included_files;
        auto default_config = load_config_file(default_config_file_path, included_files);
        auto config = load_config_file(config_file_path, included_files);

        validate_table(*default_config, *config);

        return config;
    }

    void
    Config::validate_table(const toml::table &default_config, const toml::table &config, const std::string &location) {
        for (const auto &[key, value]: config) {
            std::string new_location = location.empty() ? key.data() : location + "." + key.data();

            if (!default_config.contains(key)) {
                throw ConfigProcessingException("Key '" + new_location + "' not found in default config.");
            }

            const auto &default_value = default_config.at(key);

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
                validate_table(*default_value.as_table(), *value.as_table(), new_location);
            }
        }
    }
    std::shared_ptr<toml::table> Config::load_config_file(const std::filesystem::path &config_file_path) {
        std::set<std::filesystem::path> included_files;
        std::string include_chain;
        return load_config_file(config_file_path, included_files, include_chain);
    }

}