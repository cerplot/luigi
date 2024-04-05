#pragma once
#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
#include "tick.h"

class Indicator {
public:
    Indicator();
    virtual ~Indicator() = default;
    virtual void calcValue(const Tick& tick) = 0;
    double getLatestValue() const;

protected:
    double latestValue;
};

class IndicatorType1 : public Indicator {
public:
    void calcValue(const Tick& tick) override;

private:
    std::deque<float> prices;
    int period;
    double sum;
};

class IndicatorType2 : public Indicator {
public:
    void calcValue(const Tick& tick) override;

private:
    double ema;
    int period;
    bool initialized;
};

class IndicatorFactory {
public:
    using CreateIndicatorFunc = std::function<std::unique_ptr<Indicator>()>;

    static void registerIndicator(const std::string& name, CreateIndicatorFunc createFunc);
    static bool isRegistered(const std::string& name);
    static std::unique_ptr<Indicator> createIndicator(const std::string& name);
    static void initialize();

private:
    static std::unordered_map<std::string, CreateIndicatorFunc> indicatorMap;
};

std::vector<std::vector<double>> combine_indicators_for_all_stocks(
        const std::string& indicator1_name);
