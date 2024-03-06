#include <gtest/gtest.h>
#include "config.cpp" // Assuming the function is in this file

class ConfigTest : public ::testing::Test {
protected:
    // You can remove any or all of the following functions if they're not needed

    ConfigTest() {
        // You can do set-up work for each test here.
    }

    ~ConfigTest() override {
        // You can do clean-up work that doesn't throw exceptions here.
    }

    // If the constructor and destructor are not enough for setting up
    // and cleaning up each test, you can define the following methods:

    void SetUp() override {
        // Code here will be called immediately after the constructor (right
        // before each test).
    }

    void TearDown() override {
        // Code here will be called immediately after each test (right
        // before the destructor).
    }
};

TEST_F(ConfigTest, LoadsConfigFileCorrectly) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result is as expected
    // This will depend on the contents of your test config file
    ASSERT_EQ(result["some_key"]->as_string(), "expected_value");
}

TEST_F(ConfigTest, HandlesNonExistentFile) {
    // Arrange
    std::string config_file_path = "path/to/nonexistent/file.toml";

    // Act and Assert
    ASSERT_THROW(load_config_file(config_file_path), FileLoadException);
}

TEST_F(ConfigTest, IncludesFileUnderSpecificKey) {
    // Arrange
    std::string config_file_path = "config_with_key.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the data from the included file under the correct key
    ASSERT_EQ(result["included_key"]->as_string(), "expected_value");
}

TEST_F(ConfigTest, IncludesFileUnderRoot) {
    // Arrange
    std::string config_file_path = "config_with_root.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the data from the included file under the root of the configuration
    ASSERT_EQ(result["included_key"]->as_string(), "expected_value");
}

TEST_F(ConfigTest, HandlesIncludedNonExistentFile) {
    // Arrange
    std::string config_file_path = "config_with_nonexistent_file.toml";

    // Act and Assert
    ASSERT_THROW(load_config_file(config_file_path), FileLoadException);
}
TEST_F(ConfigTest, HandlesArrayValues) {
    // Arrange
    std::string config_file_path = "config_with_array.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the array values correctly
    std::vector<int> expected_array = {1, 2, 3};
    ASSERT_EQ(result["array_key"]->as_array(), expected_array);
}

TEST_F(ConfigTest, HandlesNestedTables) {
    // Arrange
    std::string config_file_path = "config_with_nested_table.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the nested table correctly
    ASSERT_EQ(result["table_key"]["nested_key"]->as_string(), "expected_value");
}
TEST_F(ConfigTest, HandlesBooleanValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_boolean.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the boolean value correctly
    ASSERT_EQ(result["boolean_key"]->as_boolean(), true);
}

TEST_F(ConfigTest, HandlesDateTimeValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_datetime.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the date-time value correctly
    ASSERT_EQ(result["datetime_key"]->as_datetime(), "1979-05-27T07:32:00-08:00");
}

TEST_F(ConfigTest, HandlesFloatingPointValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_float.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the floating-point value correctly
    ASSERT_EQ(result["float_key"]->as_float(), 3.14);
}

TEST_F(ConfigTest, HandlesStringValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_string.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the string value correctly
    ASSERT_EQ(result["string_key"]->as_string(), "expected_value");
}

TEST_F(ConfigTest, HandlesIntegerValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_integer.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the integer value correctly
    ASSERT_EQ(result["integer_key"]->as_integer(), 42);
}

TEST_F(ConfigTest, HandlesTableValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_table.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the table values correctly
    ASSERT_EQ(result["table_key"]["nested_key1"]->as_string(), "expected_value1");
    ASSERT_EQ(result["table_key"]["nested_key2"]->as_integer(), 123);
}

TEST_F(ConfigTest, HandlesNullValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_null.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the null value correctly
    ASSERT_EQ(result["null_key"]->as_null(), nullptr);
}

TEST_F(ConfigTest, HandlesEmptyStringValues) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_empty_string.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the empty string value correctly
    ASSERT_EQ(result["empty_string_key"]->as_string(), "");
}

TEST_F(ConfigTest, HandlesArrayOfStrings) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_array_of_strings.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the array of strings correctly
    std::vector<std::string> expected_array = {"string1", "string2", "string3"};
    ASSERT_EQ(result["array_string_key"]->as_array_of_strings(), expected_array);
}

TEST_F(ConfigTest, HandlesBooleanArray) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_boolean_array.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the boolean array correctly
    std::vector<bool> expected_array = {true, false, true};
    ASSERT_EQ(result["boolean_array_key"]->as_array_of_booleans(), expected_array);
}

TEST_F(ConfigTest, HandlesDateTimeArray) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_datetime_array.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the date-time array correctly
    std::vector<std::string> expected_array = {"1979-05-27T07:32:00-08:00", "1987-07-05T17:45:00-08:00"};
    ASSERT_EQ(result["datetime_array_key"]->as_array_of_datetimes(), expected_array);
}

TEST_F(ConfigTest, HandlesTableArray) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_table_array.toml";

    // Act
    auto result = load_config_file(config_file_path);
    /*
    # config_with_table_array.toml
    title = "TOML Example"

    [owner]
    name = "Tom Preston-Werner"
    dob = 1979-05-27T07:32:00-08:00

    table_array_key = [
      {key1 = "value1", key2 = "value2"},
      {key1 = "value3", key2 = "value4"}
    ]
    */

    // Assert
    // Check that the result includes the table array correctly
    // This will depend on the contents of your test config file
    // Replace with your actual assertion
    std::vector<std::map<std::string, toml::value>> expected_array = {
        {{"key1", "value1"}, {"key2", "value2"}},
        {{"key1", "value3"}, {"key2", "value4"}}
    };

}



TEST_F(ConfigTest, HandlesArrayOfIntegers) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_array_of_integers.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the array of integers correctly
    std::vector<int> expected_array = {1, 2, 3};
    ASSERT_EQ(result["array_integer_key"]->as_array_of_integers(), expected_array);
}

TEST_F(ConfigTest, HandlesFloatingPointArray) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_float_array.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the floating-point array correctly
    std::vector<float> expected_array = {1.1, 2.2, 3.3};
    ASSERT_EQ(result["float_array_key"]->as_array_of_floats(), expected_array);


}

TEST_F(ConfigTest, HandlesDeeplyNestedTable) {
    // Arrange
    std::string config_file_path = "path/to/your/test/config_with_deeply_nested_table.toml";

    // Act
    auto result = load_config_file(config_file_path);

    // Assert
    // Check that the result includes the deeply nested table correctly
    // This will depend on the contents of your test config file
    // Replace with your actual assertion
    /*
    title = "TOML Example"

[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00-08:00

[more_deeply_nested_table_key]
key1 = "value1"
key2 = "value2"
[more_deeply_nested_table_key.sub_table]
sub_key1 = "sub_value1"
sub_key2 = "sub_value2"
[more_deeply_nested_table_key.sub_table.sub_sub_table]
sub_sub_key1 = "sub_sub_value1"
sub_sub_key2 = "sub_sub_value2"
    */
    ASSERT_EQ(result["deeply_nested_table_key"]["key1"]->as_string(), "value1");
    ASSERT_EQ(result["deeply_nested_table_key"]["key2"]->as_string(), "value2");
    ASSERT_EQ(result["deeply_nested_table_key"]["sub_table"]["sub_key1"]->as_string(), "sub_value1");
    ASSERT_EQ(result["deeply_nested_table_key"]["sub_table"]["sub_key2"]->as_string(), "sub_value2");
    ASSERT_EQ(result["deeply_nested_table_key"]["sub_table"]["sub_sub_table"]["sub_sub_key1"]->as_string(), "sub_sub_value1");
    ASSERT_EQ(result["deeply_nested_table_key"]["sub_table"]["sub_sub_table"]["sub_sub_key2"]->as_string(), "sub_sub_value2");


}

