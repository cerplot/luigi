#include "gtest/gtest.h"
#include "config_parser.h"

class ConfigParserTest : public ::testing::Test {
protected:
    // You can add objects of the class you want to test here
    std::shared_ptr<toml::table> configTable;

    // This function runs before each test
    void SetUp() override {
        // Initialize your objects here
        configTable = parseConfigFile("config.toml");
    }

    // This function runs after each test
    void TearDown() override {
        // Clean up your objects here
        configTable.reset();
    }
};
TEST_F(ConfigParserTest, TestParseConfigFile) {
    // Check if the configTable is not null
    ASSERT_TRUE(configTable != nullptr);

    // Check if the configTable contains the expected keys
    ASSERT_TRUE(configTable->contains("str"));
    ASSERT_TRUE(configTable->contains("numbers"));
    ASSERT_TRUE(configTable->contains("vegetables"));
    ASSERT_TRUE(configTable->contains("minerals"));
    ASSERT_TRUE(configTable->contains("animals"));
}