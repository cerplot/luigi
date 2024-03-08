#include <random>
#include <map>
#include <string>
#include <chrono>
#include <iostream>


class DataSource {
protected:
    std::string selectedStock;
public:
    explicit DataSource(const std::string& stock = "") : selectedStock(stock) {}
    virtual ~DataSource() = default;
    virtual Tick next() = 0; // This method should be implemented by all derived classes
};

class MockDataSource : public DataSource {
    std::mt19937 generator;
    std::uniform_int_distribution<uint16_t> sidDistribution;
    std::uniform_real_distribution<float> priceChangeDistribution;
    std::uniform_int_distribution<uint16_t> volumeDistribution;
    std::uniform_int_distribution<int> updateTypeDistribution;
    std::map<std::string, Tick> lastTicks;
    int numStocks;

public:
    using DataSource::DataSource;  // Inherit constructor

    MockDataSource(int numStocks)
            : generator(std::random_device{}()),
              sidDistribution(1, numStocks),
              priceChangeDistribution(-0.01f, 0.01f),
              volumeDistribution(1, 1000),
              updateTypeDistribution(0, 4),  // 0: bid size, 1: bid price, 2: ask size, 3: ask price
              numStocks(numStocks) {
        if (numStocks <= 0) {
            throw std::invalid_argument("numStocks must be a positive number");
        }
        if (numStocks > 65535) {
            throw std::invalid_argument("numStocks must not exceed 65535");
        }
    }

    Tick next() override {
        // Generate a tick for a random stock
        return generateTick();
    }

private:
    Tick generateTick() {
        Tick tick;
        tick.sid = sidDistribution(generator);  // Generate a random sid
        std::string stock = "stock_" + std::to_string(tick.sid);  // Create the stock name
        tick.exch = Exchange::XNSE;  // You can also randomize this if you want
        tick.timestamp = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count();

        // If we have a last tick for this stock, fluctuate the price from the last price
        // Otherwise, generate a completely random price
        if (lastTicks.count(stock) > 0) {
            float change = priceChangeDistribution(generator) * lastTicks[stock].tradePrice;
            tick.tradePrice = lastTicks[stock].tradePrice + change;
        } else {
            std::uniform_real_distribution<float> priceDistribution(1.0f, 100.0f);
            tick.tradePrice = priceDistribution(generator);
        }

        // Ensure bid price is less than trade price and ask price is more than trade price
        std::uniform_real_distribution<float> bidAskSpreadDistribution(0.01f, 0.05f);
        float bidAskSpread = bidAskSpreadDistribution(generator);
        tick.bidPrice = tick.tradePrice - bidAskSpread;
        tick.askPrice = tick.tradePrice + bidAskSpread;

        // Decide which type of update happens
        int updateType = updateTypeDistribution(generator);
        switch (updateType) {
            case 0:  // Update bid size
                tick.bidSize = volumeDistribution(generator);
                tick.update.BidSize = 1;
                break;
            case 1:  // Update bid price
                tick.update.BidPrice = 1;
                break;
            case 2:  // Update ask size
                tick.askSize = volumeDistribution(generator);
                tick.update.AskSize = 1;
                break;
            case 3:  // Update ask price
                tick.update.AskPrice = 1;
                break;
            case 4:  // Update trade price
                tick.update.TradePrice = 1;
                tick.tradeSize = volumeDistribution(generator);
                // If a trade happens at the ask price and trade size is larger than ask size,
                // increase the ask price and generate a new random ask size
                if (tick.tradePrice == tick.askPrice && tick.tradeSize > tick.askSize) {
                    tick.askPrice += priceChangeDistribution(generator);
                    tick.askSize = volumeDistribution(generator);
                }
                    // If a trade happens at the bid price and trade size is larger than bid size,
                    // decrease the bid price and generate a new random bid size
                else if (tick.tradePrice == tick.bidPrice && tick.tradeSize > tick.bidSize) {
                    tick.bidPrice -= priceChangeDistribution(generator);
                    tick.bidSize = volumeDistribution(generator);
                }

                // Set the trade price to the new ask price or bid price
                tick.tradePrice = (tick.tradePrice == tick.askPrice) ? tick.askPrice : tick.bidPrice;
                break;
        }

        // Store this tick as the last tick for this stock
        lastTicks[stock] = tick;

        return tick;
    }
};
std::string updateToString(const Tick::Update &update) {
    std::string result;
    if (update.BidPrice) {
        result += "BidPrice: " + std::to_string(update.BidPrice) + ", ";
    }
    if (update.BidSize) {
        result += "BidSize: " + std::to_string(update.BidSize) + ", ";
    }
    if (update.AskPrice) {
        result += "AskPrice: " + std::to_string(update.AskPrice) + ", ";
    }
    if (update.AskSize) {
        result += "AskSize: " + std::to_string(update.AskSize) + ", ";
    }
    if (update.TradePrice) {
        result += "TradePrice: " + std::to_string(update.TradePrice) + ", ";
    }
    if (update.TradeSize) {
        result += "TradeSize: " + std::to_string(update.TradeSize);
    }
    if (!result.empty() && result.back() == ',') {
        result.pop_back();  // Remove trailing comma
    }
    return result;
}

void printTickInfo(const Tick& tick) {
    std::cout << "Stock ID: " << tick.sid << "\n";
    std::cout << "Exchange: " << static_cast<int>(tick.exch) << "\n";
    std::cout << "Timestamp: " << tick.timestamp << "\n";
    std::cout << "Bid Price: " << tick.bidPrice << "\n";
    std::cout << "Ask Price: " << tick.askPrice << "\n";
    std::cout << "Trade Price: " << tick.tradePrice << "\n";
    std::cout << "Bid Size: " << tick.bidSize << "\n";
    std::cout << "Ask Size: " << tick.askSize << "\n";
    std::cout << "Trade Size: " << tick.tradeSize << "\n";
    std::cout << "Update: " << updateToString(tick.update) << "\n";
    std::cout << "------------------------\n";
}

int _main() {
    // Create a MockDataSource for 100 stocks
    MockDataSource dataSource(100);

    // Generate and print 5 ticks
    for (int i = 0; i < 50; ++i) {
        Tick tick = dataSource.next();
        std::cout << "Tick " << i+1 << ":\n";
        printTickInfo(tick);
    }
    return 0;
}