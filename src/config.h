#pragma once

#include <fstream>
#include <toml.h>
#include <unordered_map>
#include <stdexcept>
#include <memory>
#include <filesystem>
#include <set>

class FileLoadException : public std::runtime_error {
public:
    explicit FileLoadException(const std::string& filename);
};

class ConfigProcessingException : public std::runtime_error {
public:
    explicit ConfigProcessingException(const std::string& filename);
};

std::shared_ptr<toml::table> load_toml_file(const std::filesystem::path& file_path);

void process_included_files(std::shared_ptr<toml::table>& config, toml::table& merged_data, std::unordered_map<std::string, std::filesystem::path>& file_paths_dict, std::set<std::filesystem::path>& included_files, const std::string& include_chain);

std::shared_ptr<toml::table> load_config_file(const std::filesystem::path& config_file_path, std::set<std::filesystem::path>& included_files, const std::string& include_chain = "");

void validate_table(const toml::table& default_config, const toml::table& config, const std::string& location = "");

std::shared_ptr<toml::table> validate_config_file(const std::filesystem::path& default_config_file_path, const std::filesystem::path& config_file_path);