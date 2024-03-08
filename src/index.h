#pragma once
#include <vector>
#include "tick.h"

class Index {
private:
    struct StockData {
        double weight;
        double lastTradePrice;

        StockData(double weight = 0.0, double lastTradePrice = 0.0);

        void updateLastTradePrice(double price);
    };

    std::vector<StockData> stocks;
    double indexValue;

public:
    Index(size_t stockSize);

    void addStock(uint16_t stock, double weight);
    void update(const Tick& tick);
    double getValue() const;
};
