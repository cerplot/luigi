#include <gtest/gtest.h>
#include <filesystem>
#include "config.h"

namespace te {

    class ConfigTest : public ::testing::Test {
    protected:
        ConfigTest() {
            // Create a temporary directory for the tests
            std::filesystem::create_directory("test_directory");
        }

        ~ConfigTest() override {
            // Remove the temporary directory after the tests are done
            std::filesystem::remove_all("test_directory");
        }

        // If the constructor and destructor are not enough for setting up
        // and cleaning up each test, you can define the following methods:

        void SetUp() override {
            // Create a temporary TOML file for the tests
            std::ofstream file("test.toml");
            file << "title = \"Test TOML File\"\n";
            file.close();
        }

        void TearDown() override {
            // Delete the temporary TOML file after the test
            std::filesystem::remove("test.toml");
        }

        // Class members declared here can be used by all tests in the test suite for ConfigTest.
    };


    TEST_F(ConfigTest, LoadTomlFile) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "test.toml"; // replace with a valid test file path

        // Test that the function does not throw an exception when given a valid file path
        EXPECT_NO_THROW(config.load_toml_file(file_path));

        // Test that the function throws an exception when given an invalid file path
        std::filesystem::path invalid_file_path = "invalid.toml";
        EXPECT_THROW(config.load_toml_file(invalid_file_path), FileLoadException);
    }

    TEST_F(ConfigTest, ProcessIncludedFiles) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "test.toml"; // replace with a valid test file path

        // Load a configuration file that includes other files
        auto config_table = config.load_config_file(file_path);

        // Create a copy of the original table to compare with the processed table
        auto original_table = std::make_shared<toml::table>(*config_table);

        // Process the included files
        toml::table merged_data;
        std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
        std::set<std::filesystem::path> included_files;
        std::string include_chain;
        config.process_included_files(config_table, merged_data, file_paths_dict, included_files, include_chain);

        // Check that the processed table is not the same as the original table
        EXPECT_NE(*config_table, *original_table);

        // Add more checks here to verify that the processed table is as expected
    }
    TEST_F(ConfigTest, ValidateConfigFile) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml"; // replace with a valid default config file path
        std::filesystem::path valid_file_path = "valid.toml"; // replace with a valid config file path
        std::filesystem::path invalid_file_path = "invalid.toml"; // replace with an invalid config file path

        // Test that the function does not throw an exception when given a valid config file path
        EXPECT_NO_THROW(config.validate_config_file(default_file_path, valid_file_path));

        // Test that the function throws an exception when given an invalid config file path
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, LoadTomlFile_NonExistentFile) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "non_existent.toml";
        EXPECT_THROW(config.load_toml_file(file_path), FileLoadException);
    }

    TEST_F(ConfigTest, LoadTomlFile_EmptyFile) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "empty.toml";
        EXPECT_THROW(config.load_toml_file(file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ProcessIncludedFiles_CircularIncludes) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "circular.toml";
        auto config_table = config.load_config_file(file_path);
        toml::table merged_data;
        std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
        std::set<std::filesystem::path> included_files;
        std::string include_chain;
        EXPECT_THROW(config.process_included_files(config_table, merged_data, file_paths_dict, included_files, include_chain), std::runtime_error);
    }

    TEST_F(ConfigTest, ValidateConfigFile_NonExistentDefaultFile) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "non_existent.toml";
        std::filesystem::path valid_file_path = "valid.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, valid_file_path), FileLoadException);
    }

    TEST_F(ConfigTest, ValidateTable_ExtraKeys) {
        Config& config = Config::getConfig();
        toml::table valid_table;
        valid_table.insert_or_assign("title", "Test TOML File");
        valid_table.insert_or_assign("extra_key", "Extra Value");
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        EXPECT_THROW(config.validate_table(default_table, valid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_NonTomlFile) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "not_toml.txt";
        EXPECT_THROW(config.load_toml_file(file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ProcessIncludedFiles_SelfInclude) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "self_include.toml";
        auto config_table = config.load_config_file(file_path);
        toml::table merged_data;
        std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
        std::set<std::filesystem::path> included_files;
        std::string include_chain;
        EXPECT_THROW(config.process_included_files(config_table, merged_data, file_paths_dict, included_files, include_chain), std::runtime_error);
    }

    TEST_F(ConfigTest, ValidateConfigFile_DifferentKeyType) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "different_key_type.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_DifferentKeyType) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        invalid_table.insert_or_assign("title", 123);
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_IncorrectTomlSyntax) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "incorrect_syntax.toml";
        EXPECT_THROW(config.load_toml_file(file_path), toml::parse_error);
    }

    TEST_F(ConfigTest, ProcessIncludedFiles_NonExistentInclude) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "non_existent_include.toml";
        auto config_table = config.load_config_file(file_path);
        toml::table merged_data;
        std::unordered_map<std::string, std::filesystem::path> file_paths_dict;
        std::set<std::filesystem::path> included_files;
        std::string include_chain;
        EXPECT_THROW(config.process_included_files(config_table, merged_data, file_paths_dict, included_files, include_chain), FileLoadException);
    }

    TEST_F(ConfigTest, ValidateConfigFile_KeyNotFound) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "key_not_found.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_KeyNotFound) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        invalid_table.insert_or_assign("not_found", "Not Found");
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_InvalidTomlType) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "invalid_toml_type.toml";
        EXPECT_THROW(config.load_toml_file(file_path), toml::parse_error);
    }

    TEST_F(ConfigTest, ValidateConfigFile_InvalidTomlType) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "invalid_toml_type.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_InvalidTomlType) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        invalid_table.insert_or_assign("title", std::vector<int>{1, 2, 3}); // toml::value does not support std::vector
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_UnexpectedTomlType) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "unexpected_toml_type.toml";
        EXPECT_THROW(config.load_toml_file(file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateConfigFile_UnexpectedTomlType) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "unexpected_toml_type.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_UnexpectedTomlType) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        invalid_table.insert_or_assign("title", std::vector<int>{1, 2, 3}); // toml::value supports std::vector but it's not expected by your application
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_NestedTable) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "nested_table.toml";
        EXPECT_NO_THROW(config.load_toml_file(file_path));
    }

    TEST_F(ConfigTest, ValidateConfigFile_NestedTable) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path valid_file_path = "nested_table.toml";
        EXPECT_NO_THROW(config.validate_config_file(default_file_path, valid_file_path));
    }

    TEST_F(ConfigTest, ValidateTable_NestedTable) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table nested_table;
        nested_table.insert_or_assign("nested_key", "Nested Value");
        default_table.insert_or_assign("nested_table", nested_table);
        toml::table valid_table;
        valid_table.insert_or_assign("title", "Test TOML File");
        toml::table valid_nested_table;
        valid_nested_table.insert_or_assign("nested_key", "Test Nested Value");
        valid_table.insert_or_assign("nested_table", valid_nested_table);
        EXPECT_NO_THROW(config.validate_table(default_table, valid_table));
    }

    TEST_F(ConfigTest, LoadTomlFile_NonExistentIncludeInTable) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "non_existent_include_in_table.toml";
        EXPECT_THROW(config.load_toml_file(file_path), FileLoadException);
    }

    TEST_F(ConfigTest, ValidateConfigFile_NonExistentIncludeInTable) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "non_existent_include_in_table.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_NonExistentIncludeInTable) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        toml::table include_table;
        include_table.insert_or_assign("include", "non_existent.toml");
        invalid_table.insert_or_assign("title", include_table);
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }

    TEST_F(ConfigTest, LoadTomlFile_IncorrectTomlSyntaxInInclude) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "incorrect_toml_syntax_in_include.toml";
        EXPECT_THROW(config.load_toml_file(file_path), toml::parse_error);
    }

    TEST_F(ConfigTest, ValidateConfigFile_IncorrectTomlSyntaxInInclude) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "incorrect_toml_syntax_in_include.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_IncorrectTomlSyntaxInInclude) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        toml::table include_table;
        include_table.insert_or_assign("include", "incorrect_syntax.toml");
        invalid_table.insert_or_assign("title", include_table);
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_CircularIncludeInTable) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "circular_include_in_table.toml";
        EXPECT_THROW(config.load_toml_file(file_path), std::runtime_error);
    }

    TEST_F(ConfigTest, ValidateConfigFile_CircularIncludeInTable) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "circular_include_in_table.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_CircularIncludeInTable) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        toml::table include_table;
        include_table.insert_or_assign("include", "circular_include.toml");
        invalid_table.insert_or_assign("title", include_table);
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }
    TEST_F(ConfigTest, LoadTomlFile_IncludeKeyNotInDefault) {
        Config& config = Config::getConfig();
        std::filesystem::path file_path = "include_key_not_in_default.toml";
        EXPECT_THROW(config.load_toml_file(file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateConfigFile_IncludeKeyNotInDefault) {
        Config& config = Config::getConfig();
        std::filesystem::path default_file_path = "default.toml";
        std::filesystem::path invalid_file_path = "include_key_not_in_default.toml";
        EXPECT_THROW(config.validate_config_file(default_file_path, invalid_file_path), ConfigProcessingException);
    }

    TEST_F(ConfigTest, ValidateTable_IncludeKeyNotInDefault) {
        Config& config = Config::getConfig();
        toml::table default_table;
        default_table.insert_or_assign("title", "Default Title");
        toml::table invalid_table;
        toml::table include_table;
        include_table.insert_or_assign("include", "key_not_in_default.toml");
        invalid_table.insert_or_assign("title", include_table);
        EXPECT_THROW(config.validate_table(default_table, invalid_table), ConfigProcessingException);
    }

}  // namespace te