#include <algorithm>
#include <vector>
#include <map>
#include <optional>
#include <iostream>

std::vector<std::vector<std::optional<double>>> combineIndicatorsMap(
        const std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>>& indicators) {
    int numIndicators = indicators.size();
    std::map<uint32_t, std::vector<std::optional<double>>> combinedIndicators;

    for (int indicatorIndex = 0; indicatorIndex < numIndicators; ++indicatorIndex) {
        const auto& timestamps = indicators[indicatorIndex].first;
        const auto& values = indicators[indicatorIndex].second;

        if (timestamps.size() != values.size()) {
            throw std::invalid_argument("Timestamps and values vectors must have the same size.");
        }

        for (size_t i = 0; i < timestamps.size(); ++i) {
            uint32_t timestamp = timestamps[i];
            double value = values[i];
            // Ensure the vector is large enough
            if (combinedIndicators[timestamp].size() <= indicatorIndex) {
                combinedIndicators[timestamp].resize(indicatorIndex + 1);
            }
            combinedIndicators[timestamp][indicatorIndex] = value;
        }
    }

    std::vector<std::vector<std::optional<double>>> result;
    std::vector<std::optional<double>> lastSeen(numIndicators);

    for (const auto& [timestamp, values] : combinedIndicators) {
        std::vector<std::optional<double>> row(numIndicators);

        for (int i = 0; i < numIndicators; ++i) {
            if (i < values.size() && values[i].has_value()) {
                row[i] = values[i];
                lastSeen[i] = values[i];
            } else if (lastSeen[i].has_value()) {
                row[i] = lastSeen[i];
            }
        }
        result.push_back(row);
    }

    return result;
}


std::vector<std::vector<std::optional<double>>> combineIndicators(
        const std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>>& indicators) {
    int numIndicators = indicators.size();
    std::vector<uint32_t> allTimestamps;
    std::vector<std::vector<std::optional<double>>> combinedIndicators;

    // Collect all timestamps
    for (const auto& indicator : indicators) {
        const auto& timestamps = indicator.first;
        allTimestamps.insert(allTimestamps.end(), timestamps.begin(), timestamps.end());
    }

    // Remove duplicates and sort the timestamps
    std::sort(allTimestamps.begin(), allTimestamps.end());
    allTimestamps.erase(std::unique(allTimestamps.begin(), allTimestamps.end()), allTimestamps.end());

    // Initialize combinedIndicators with all timestamps
    for (const auto& timestamp : allTimestamps) {
        combinedIndicators.push_back(std::vector<std::optional<double>>(numIndicators));
    }

    // Iterate over each indicator
    for (int indicatorIndex = 0; indicatorIndex < numIndicators; ++indicatorIndex) {
        const auto& timestamps = indicators[indicatorIndex].first;
        const auto& values = indicators[indicatorIndex].second;

        // Iterate over the timestamps and values
        for (size_t i = 0; i < timestamps.size(); ++i) {
            uint32_t timestamp = timestamps[i];
            double value = values[i];

            // Find the index of the timestamp in combinedIndicators
            auto it = std::lower_bound(allTimestamps.begin(), allTimestamps.end(), timestamp);
            int index = std::distance(allTimestamps.begin(), it);

            // Add the value to the combinedIndicators vector
            combinedIndicators[index][indicatorIndex] = value;
        }
    }

    // Forward fill missing values
    std::vector<std::optional<double>> lastSeen(numIndicators);
    for (auto& values : combinedIndicators) {
        for (int i = 0; i < numIndicators; ++i) {
            if (values[i].has_value()) {
                lastSeen[i] = values[i];
            } else if (lastSeen[i].has_value()) {
                values[i] = lastSeen[i];
            }
        }
    }

    return combinedIndicators;
}

int main() {
    // Define the indicators
    std::vector<uint32_t> timestamps1 = {1, 2, 5, 10};
    std::vector<double> values1 = {10, 20, 30, 40};
    std::pair<std::vector<uint32_t>, std::vector<double>> indicator1 = {timestamps1, values1};

    std::vector<uint32_t> timestamps2 = {2, 3, 4};
    std::vector<double> values2 = {11, 21, 31};
    std::pair<std::vector<uint32_t>, std::vector<double>> indicator2 = {timestamps2, values2};

    std::vector<uint32_t> timestamps3 = {1, 3, 5, 6, 7, 8, 9};
    std::vector<double> values3 = {12, 32, 52, 62, 72, 82, 92};
    std::pair<std::vector<uint32_t>, std::vector<double>> indicator3 = {timestamps3, values3};

    // Combine the indicators into a vector
    std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {indicator1, indicator2, indicator3};

    // Call the combine_indicators function
    std::vector<std::vector<std::optional<double>>> combinedIndicators = combineIndicators(indicators);

    // Print the combined indicators
    for (const auto& row : combinedIndicators) {
        for (const auto& value : row) {
            if (value.has_value()) {
                std::cout << value.value() << " ";
            } else {
                std::cout << "null ";
            }
        }
        std::cout << std::endl;
    }

    return 0;
}
