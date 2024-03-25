#pragma once

#include <fstream>
#include <toml.h>
#include <unordered_map>
#include <stdexcept>
#include <memory>
#include <filesystem>
#include <set>
#include <mutex>

namespace te {

    class FileLoadException : public std::runtime_error {
    public:
        explicit FileLoadException(const std::string &filename)
                : std::runtime_error("Error loading config file " + filename) {}
    };

    class ConfigProcessingException : public std::runtime_error {
    public:
        explicit ConfigProcessingException(const std::string &filename)
                : std::runtime_error("Error processing config file " + filename) {}
    };

    class Config {
        Config() {}
        static Config* instance;
        std::mutex included_files_mutex;
        std::shared_ptr<toml::table> cmd_args_table;
    public:
        static Config& getConfig();
        Config(const Config&) = delete;
        Config& operator=(const Config&) = delete;
        std::shared_ptr<toml::table> load_toml_file(const std::filesystem::path &file_path);

        std::shared_ptr<toml::table>
        load_config_file(const std::filesystem::path &config_file_path, std::set<std::filesystem::path> &included_files,
                         const std::string &include_chain = "");

        void process_included_files(std::shared_ptr<toml::table> &config, toml::table &merged_data,
                                    std::unordered_map<std::string, std::filesystem::path> &file_paths_dict,
                                    std::set<std::filesystem::path> &included_files, const std::string &include_chain);

        std::shared_ptr<toml::table> validate_config_file(const std::filesystem::path &default_config_file_path,
                                                          const std::filesystem::path &config_file_path);

        std::shared_ptr<toml::table>
        load_config_file(const std::filesystem::path &config_file_path, const std::string &include_chain);

        void
        validate_table(const toml::table &default_config, const toml::table &config, const std::string &location = "");
        void process_cmd_args(int argc, char** argv);
        std::shared_ptr<toml::table> load_config_file(const std::filesystem::path &config_file_path);
        template<typename T>
        T get(const std::string& key);
    };
    Config* Config::instance = nullptr;
}
