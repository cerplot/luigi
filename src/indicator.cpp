#include "indicator.h"

Indicator::Indicator() : latestValue(0.0) {}

double Indicator::getLatestValue() const {
    return latestValue;
}

void IndicatorType1::calcValue(const Tick& tick) {
    // Implementation remains the same
}

void IndicatorType2::calcValue(const Tick& tick) {
    // Implementation remains the same
}

void IndicatorFactory::registerIndicator(const std::string& name, CreateIndicatorFunc createFunc) {
    indicatorMap[name] = std::move(createFunc);
}

bool IndicatorFactory::isRegistered(const std::string& name) {
    return indicatorMap.find(name) != indicatorMap.end();
}

std::unique_ptr<Indicator> IndicatorFactory::createIndicator(const std::string& name) {
    auto it = indicatorMap.find(name);
    if (it == indicatorMap.end()) {
        throw std::runtime_error("Invalid indicator name: " + name);
    }
    return it->second();
}

void IndicatorFactory::initialize() {
    registerIndicator("IndicatorType1", []{ return std::make_unique<IndicatorType1>(); });
    registerIndicator("IndicatorType2", []{ return std::make_unique<IndicatorType2>(); });
    // Add more indicators here
}

std::vector<std::vector<double>> combine_indicators_for_all_stocks(const std::string& indicator1_name) {
    // Implementation remains the same
}