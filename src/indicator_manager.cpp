
class IndicatorManager {
private:
    std::unordered_map<uint16_t, std::unordered_map<std::string, std::unique_ptr<Indicator>>> contractIndicatorsObjects;
    std::unordered_map<std::string, int> indicatorIndices;
    std::unordered_map<uint16_t, std::vector<std::vector<double>>> contractIndicators;
    std::vector<std::string> indicator_list;

public:
    IndicatorManager(const std::vector<std::string>& indicator_list) : indicator_list(indicator_list) {
        // Initialize indicatorIndices and contractIndicatorsObjects
    }

    void initializeIndicators(const std::vector<uint16_t>& contracts) {
        static const std::set<std::string> supported_indicators = {"IndicatorType1", "IndicatorType2"};
        for (int i = 0; i < indicator_list.size(); ++i) {
            if (supported_indicators.find(indicator_list[i]) == supported_indicators.end()) {
                throw std::runtime_error("Unsupported indicator " + indicator_list[i] + " cannot be initialized.");
            }
            indicatorIndices[indicator_list[i]] = i;
        }

        for (const auto& contract : contracts) {
            for (const auto& indicator_name : indicator_list) {
                if (supported_indicators.find(indicator_name) != supported_indicators.end()) {
                    contractIndicatorsObjects[contract][indicator_name] = IndicatorFactory::createIndicator(indicator_name);
                } else {
                    throw std::runtime_error("Unsupported indicator " + indicator_name + " cannot be initialized for contract " + std::to_string(contract) + ".");
                }
            }
        }
    }

    std::unique_ptr<Indicator> createIndicator(const std::string& name) {
        return IndicatorFactory::createIndicator(name);
    }

    void processIndicator(const Tick& tick, const std::string& indicator_name) {
        auto& indicator = contractIndicatorsObjects[tick.sid][indicator_name];
        indicator->calcValue(tick);
        double latestValue = indicator->getLatestValue();

        // Find the index of the indicator
        int indicator_index = indicatorIndices[indicator_name];

        // Update contractIndicators with the latest value
        contractIndicators[tick.sid][indicator_index].emplace_back(latestValue);
    }
};
