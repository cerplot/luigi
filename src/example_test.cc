//
// Here's a basic example of how you might structure your test:
//
TEST(CombineIndicatorsGridTest, BasicTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}
TEST(CombineIndicatorsGridTest, DifferentNumberOfElementsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2}, {1.1, 2.2}}, // Indicator 1 with 2 elements
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2 with 3 elements
        {{3, 4, 5, 6}, {3.3, 4.4, 5.5, 6.6}}  // Indicator 3 with 4 elements
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}
TEST(CombineIndicatorsGridTest, GridEndLessThanMaxTimeTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 3, 5}, {1.1, 3.3, 5.5}}, // Indicator 1
        {{2, 4, 6}, {2.2, 4.4, 6.6}}, // Indicator 2
        {{3, 5, 7}, {3.3, 5.5, 7.7}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 5; // Less than the maximum timestamp (7)
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, GridStartLargerThanMinTimeTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 3, 5}, {1.1, 3.3, 5.5}}, // Indicator 1
        {{2, 4, 6}, {2.2, 4.4, 6.6}}, // Indicator 2
        {{3, 5, 7}, {3.3, 5.5, 7.7}}  // Indicator 3
};

uint32_t gridStart = 2; // Larger than the minimum timestamp (1)
uint32_t gridEnd = 7;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, GridStartLargerThanMinAndGridEndLargerThanMaxTimeTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 3, 5, 7}, {1.1, 3.3, 5.5, 7.7}}, // Indicator 1 with 4 elements
        {{2, 4, 6, 8, 10}, {2.2, 4.4, 6.6, 8.8, 10.1}}, // Indicator 2 with 5 elements
        {{3, 5, 7, 9, 11, 13}, {3.3, 5.5, 7.7, 9.9, 11.1, 13.1}},  // Indicator 3 with 6 elements
        {{4, 6, 8, 10, 12, 14, 16}, {4.4, 6.6, 8.8, 10.1, 12.1, 14.1, 16.1}}  // Indicator 4 with 7 elements
};

uint32_t gridStart = 5; // Larger than the minimum timestamp (1)
uint32_t gridEnd = 20; // Larger than the maximum timestamp (16)
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

#include <gtest/gtest.h>
#include "example.h" // Assuming the combineIndicatorsGrid function is declared in this header file

TEST(CombineIndicatorsGridTest, IndicatorOutsideGridRangeTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{20, 21, 22}, {20.2, 21.2, 22.2}}  // Indicator 3, completely outside the grid range
};

uint32_t gridStart = 5; // Larger than the maximum timestamp of Indicator 1 and 2
uint32_t gridEnd = 15; // Less than the minimum timestamp of Indicator 3
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, EmptyIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, SingleElementInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}} // Only one indicator
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, ZeroGridIntervalTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 0; // Zero grid interval

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, GridStartEqualToGridEndTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 5;
uint32_t gridEnd = 5; // Grid start is equal to grid end
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, GridStartGreaterThanGridEndTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 15;
uint32_t gridEnd = 5; // Grid start is greater than grid end
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}


TEST(CombineIndicatorsGridTest, SameTimestampsInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 1, 1}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{1, 1, 1}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{1, 1, 1}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, SameValuesInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 1.1, 1.1}}, // Indicator 1
        {{2, 3, 4}, {1.1, 1.1, 1.1}}, // Indicator 2
        {{3, 4, 5}, {1.1, 1.1, 1.1}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, TimestampsNotInAscendingOrderTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{3, 2, 1}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{4, 3, 2}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{5, 4, 3}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, NegativeTimestampsInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{-1, -2, -3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{-2, -3, -4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{-3, -4, -5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, NegativeValuesInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {-1.1, -2.2, -3.3}}, // Indicator 1
        {{2, 3, 4}, {-2.2, -3.3, -4.4}}, // Indicator 2
        {{3, 4, 5}, {-3.3, -4.4, -5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, ZeroTimestampsInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{0, 0, 0}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{0, 0, 0}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{0, 0, 0}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, ZeroValuesInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {0.0, 0.0, 0.0}}, // Indicator 1
        {{2, 3, 4}, {0.0, 0.0, 0.0}}, // Indicator 2
        {{3, 4, 5}, {0.0, 0.0, 0.0}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, ZeroGridStartEndAndIntervalTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 0;
uint32_t gridEnd = 0;
uint32_t gridInterval = 0;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, EmptyVectorsInIndicatorsTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{}, {}}, // Indicator 1 with empty vectors
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}


TEST(CombineIndicatorsGridTest, GridIntervalLargerThanGridRangeTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 5;
uint32_t gridInterval = 10; // Grid interval is larger than the difference between grid start and grid end

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, TimestampsNotInGridTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{6, 7, 8}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{7, 8, 9}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{8, 9, 10}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 5;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, TimestampsEqualToGridStartEndTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 15, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{2, 15, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{1, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, TimestampsEqualToGridIntervalTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
        {{1, 2, 3}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{1, 2, 3}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1; // Equal to the timestamps

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}

TEST(CombineIndicatorsGridTest, EqualTimestampsInSameIndicatorTest) {
std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
        {{1, 1, 1}, {1.1, 2.2, 3.3}}, // Indicator 1 with equal timestamps
        {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
        {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
};

uint32_t gridStart = 1;
uint32_t gridEnd = 15;
uint32_t gridInterval = 1;

auto result = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);

// Define your expected result
std::vector<std::vector<double>> expected = {
        // Fill this with the expected result
};

// Check if the result matches the expected
ASSERT_EQ(result, expected);
}
