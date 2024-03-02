#include <iostream>
#include <fstream>
#include <toml++/toml.h>
#include <unordered_map>
#include <string>
#include <stdexcept>
#include <memory>
#include <filesystem>
#include <set>

class FileLoadException : public std::runtime_error {
public:
    explicit FileLoadException(const std::string& filename)
        : std::runtime_error("Error loading config file " + filename) {}
};

class ConfigProcessingException : public std::runtime_error {
public:
    explicit ConfigProcessingException(const std::string& filename)
        : std::runtime_error("Error processing config file " + filename) {}
};

std::shared_ptr<toml::table> load_toml_file(const std::filesystem::path& file_path) {
    if (!std::filesystem::exists(file_path)) {
        throw FileLoadException("File does not exist: " + file_path.string());
    }
    std::ifstream file(file_path);
    if (!file.is_open()) {
        throw FileLoadException("Failed to open file: " + file_path.string());
    }
    try {
        return std::make_shared<toml::table>(toml::parse(file));
    } catch (const toml::parse_error& e) {
        throw FileLoadException("Failed to parse TOML file: " + file_path.string() + ". Error: " + e.what());
    }
}

std::unordered_map<std::string, std::shared_ptr<toml::table>> load_config_file(const std::filesystem::path& config_file_path, std::set<std::string>& included_files) {
    std::unordered_map<std::string, std::shared_ptr<toml::table>> merged_data;
    try {
        if (included_files.find(config_file_path) != included_files.end()) {
            throw std::runtime_error("Circular include detected: " + config_file_path);
        }
        included_files.insert(config_file_path);

         auto config = load_toml_file(config_file_path);

        auto include = *config->get("include").as_table();
        std::unordered_map<std::string, std::string> file_paths_dict;
        for (const auto& [key, value] : include) {
            std::filesystem::path relative_path = *value.as_string();
            std::filesystem::path base_path = config_file_path;
            base_path.remove_filename();
            std::filesystem::path full_path = base_path / relative_path;
            file_paths_dict[key] = full_path.string();
        }

        for (const auto& [name, file_path] : file_paths_dict) {
            auto data = load_config_file(file_path, included_files);
            if (name == "_") {
                for (const auto& [key, value] : *data->as_table()) {
                    merged_data[key] = value;
                }
            } else {
                merged_data[name] = data;
            }
        }

        config->erase("include");
    }
    catch (const toml::parse_error& e) {
        throw ConfigProcessingException(config_file_path);
    }

    return merged_data;
}

void validate_table(const toml::table& default_table, const toml::table& table, const std::string& path = "") {
    for (const auto& [key, value] : table) {
        std::string full_key = path.empty() ? key : path + "." + key;
        if (!default_table.contains(key)) {
            throw std::runtime_error("Invalid key '" + full_key + "'");
        }
        if (value.type() != default_table.get(key)->type()) {
            throw std::runtime_error("Invalid type for key '" + full_key + "'");
        }
        if (value.is_table()) {
            validate_table(*default_table.get(key)->as_table(), *value.as_table(), full_key);
        }
    }
}

std::shared_ptr<toml::table> validate_config_file(const std::filesystem::path& default_config_file_path, const std::filesystem::path& config_file_path) {
    std::set<std::string> included_files;
    auto default_config = load_config_file(default_config_file_path, included_files);
    auto config = load_config_file(config_file_path, included_files);

    validate_table(*default_config, *config);

    return config;
}

int main() {
    try {
        auto config = validate_config_file(
            std::filesystem::path("path/to/default_config.toml"),
            std::filesystem::path("path/to/config.toml"));
        // Use the config as needed
    } catch (const std::runtime_error& e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }
    return 0;
}