#include <execution>
#include <iostream>
#include <algorithm>
#include <vector>
#include <map>
#include <optional>


std::vector<std::vector<std::optional<double>>> combineIndicators(
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
    std::vector<std::optional<double>> lastSeen(numIndicators, 0.0); // Initialize with 0.0
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
    return result; // should be sorted by timestamp
}


std::vector<std::vector<double>> combineIndicatorsGrid(
        const std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>>& indicators,
        uint32_t gridStart, uint32_t gridEnd, uint32_t gridInterval) {
    int numIndicators = indicators.size();
    int gridSize = (gridEnd - gridStart) / gridInterval + 1;

    std::vector<std::vector<double>> result(numIndicators, std::vector<double>(gridSize, 0.0));

    std::for_each(std::execution::par, indicators.begin(), indicators.end(), [&](const auto& indicator) {
        int indicatorIndex = &indicator - &indicators[0];
        const auto& timestamps = indicator.first;
        const auto& values = indicator.second;
        auto valueIt = values.begin();
        auto timeIt = timestamps.begin();
        double lastValue = 0.0;
        for (int i = 0; i < gridSize; ++i) {
            uint32_t t = gridStart + i * gridInterval;
            while (timeIt != timestamps.end() && *timeIt <= t) {
                lastValue = *valueIt;
                ++timeIt;
                ++valueIt;
            }
            result[indicatorIndex][i] = lastValue;
        }
    });
    return result;
}


int main() {
    std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators = {
            {{1, 3}, {2.2, 3.3}}, // Indicator stock 1
            {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator stock  2
            {{1, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator stock 3
    };
    /// 1, 2, 3,  4,  5

    auto result = combineIndicators(indicators);
    for (const auto& row : result) {
        for (const auto& value : row) {
            if (value.has_value()) {
                std::cout << value.value() << " ";
            } else {
                std::cout << "N/A ";
            }
        }
        std::cout << std::endl;
    }

    std::vector<std::pair<std::vector<uint32_t>, std::vector<double>>> indicators2 = {
            {{1, 2, 3}, {1.1, 2.2, 3.3}}, // Indicator 1
            {{2, 3, 4}, {2.2, 3.3, 4.4}}, // Indicator 2
            {{3, 4, 5}, {3.3, 4.4, 5.5}}  // Indicator 3
    };

    uint32_t gridStart = 1;
    uint32_t gridEnd = 15;
    uint32_t gridInterval = 1;

    auto result2 = combineIndicatorsGrid(indicators, gridStart, gridEnd, gridInterval);
    for (const auto& row : result2) {
        for (const auto& value : row) {
            std::cout << value << " ";
        }
        std::cout << std::endl;
    }
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
