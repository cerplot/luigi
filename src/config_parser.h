#ifndef UNTITLED7_CONFIG_H
#define UNTITLED7_CONFIG_H
#include <filesystem>
#include <set>
#include <memory>
#include <unordered_map>
#include <toml.hpp>

std::shared_ptr<toml::table> parseConfigFile(const std::filesystem::path& file_path);
std::shared_ptr<toml::table> loadConfigFile(const std::filesystem::path& config_file_path, std::set<std::filesystem::path>& included_files, const std::string& include_chain = "");
void processIncludedFiles(toml::table& merged_data, std::unordered_map<std::string, std::filesystem::path>& file_paths_dict, std::set<std::filesystem::path>& included_files, const std::string& include_chain);
std::shared_ptr<toml::table> validate_config_file(const std::filesystem::path& default_config_file_path, const std::filesystem::path& config_file_path);
void validateTable(const toml::table& default_config, const toml::table& config, const std::string& location = "");

#endif //UNTITLED7_CONFIG_H