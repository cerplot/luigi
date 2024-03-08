

class TickProcessor {
private:
    std::unordered_map<uint16_t, std::vector<std::string>> stockToIndices;
    std::unordered_map<uint16_t, std::unordered_map<std::string, std::unique_ptr<Indicator>>> contractIndicatorsObjects;
    std::unordered_map<std::string, int> indicatorIndices;
    std::unordered_map<uint16_t, std::vector<std::vector<double>>> contractIndicators;
    std::unordered_map<std::string, Index> indices;

public:
    TickProcessor(const std::vector<std::string>& indicator_list) {
        // Initialize indicatorIndices
        for (int i = 0; i < indicator_list.size(); ++i) {
            indicatorIndices[indicator_list[i]] = i;
        }

        // Initialize contractIndicatorsObjects
        // Assuming that you have a list of contracts
        std::vector<uint16_t> contracts = { /* your contracts here */ };
        for (const auto& contract : contracts) {
            for (const auto& indicator_name : indicator_list) {
                contractIndicatorsObjects[contract][indicator_name] = IndicatorFactory::createIndicator(indicator_name);
            }
        }
    }

    void processTick(const Tick& tick) {
        if (stockToIndices.count(tick.sid) > 0) {
            auto processIndicator = [this, tick](const std::string& indicator_name) {
                auto& indicator = contractIndicatorsObjects[tick.sid][indicator_name];
                indicator->calcValue(tick);
                double latestValue = indicator->getLatestValue();

                // Find the index of the indicator
                int indicator_index = indicatorIndices[indicator_name];

                // Update contractIndicators with the latest value
                contractIndicators[tick.sid][indicator_index].emplace_back(latestValue);
            };
            std::vector<std::string> indicator_list = {"IndicatorType1", "IndicatorType2"};
            for (const auto& indicator_name : indicator_list) {
                processIndicator(indicator_name);
            }

            // Update index values
            for (const auto& indexName : stockToIndices[tick.sid]) {
                indices[indexName].update(tick);
            }
        }
    }
};
