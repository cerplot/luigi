#include "index.h"

Index::StockData::StockData(double weight, double lastTradePrice)
        : weight(weight), lastTradePrice(lastTradePrice) {}

void Index::StockData::updateLastTradePrice(double price) {
    lastTradePrice = price;
}

Index::Index(size_t stockSize) : stocks(stockSize), indexValue(0.0) {}

void Index::addStock(uint16_t stock, double weight) {
    stocks[stock] = StockData(weight);
}

void Index::update(const Tick& tick) {
    indexValue += stocks[tick.sid].weight * (tick.tradePrice - stocks[tick.sid].lastTradePrice);
    stocks[tick.sid].updateLastTradePrice(tick.tradePrice);
}

double Index::getValue() const {
    return indexValue;
}