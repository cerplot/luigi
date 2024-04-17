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
    std::string name="price";
    Indicator(const std::string& date, const std::string& stock, double ema)
            : date(date), stock(stock), latestValue(0.0), ema(ema) {}
    virtual ~Indicator() = default;
    virtual void calcValue(const Tick& tick) = 0;
    virtual void calcValue(const Book& book) = 0;
    double getLatestValue() const;
    std::string full_name( ){
         + name ;
    }

protected:
    double latestValue;

    // param
    const std::string date;  //
    const std::string stock;
    const double ema;
    const int diff=1;
    // some more data members
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
    // []
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
