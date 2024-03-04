#include <thread>
#include <vector>
#include <queue>
#include <functional>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <set>
#include <unordered_map>
#include <fstream>
#include <string>
#include <deque>
#include <optional>


enum class Exchange : uint8_t {
    Exchange1 = 0,
    Exchange2,
    Exchange3,
    // Add more exchanges as needed
    ExchangeCount // Keep this last
};

struct Tick {
    struct Update {
        uint8_t BidPrice : 1;
        uint8_t BidSize : 1;
        uint8_t AskPrice : 1;
        uint8_t AskSize : 1;
        uint8_t TradePrice : 1;
        uint8_t TradeSize : 1;
        Update() : BidPrice(0), BidSize(0), AskPrice(0), AskSize(0), TradePrice(0), TradeSize(0) {}
    } update;

    uint16_t sid;
    Exchange exch;
    uint32_t timestamp;

    float bidPrice;
    float askPrice;
    float tradePrice;
    uint16_t bidSize;
    uint16_t askSize;
    uint16_t tradeSize;
};

class Index {
public:
    std::unordered_map<uint16_t, double> stockWeights;
    double indexValue = 0.0;

    void addStock(uint16_t stock, double weight) {
        stockWeights[stock] = weight;
    }

    void calculateValue(const std::unordered_map<uint16_t, Tick>& latestTicks) {
        indexValue = 0.0;
        for (const auto& [stock, weight] : stockWeights) {
            if (latestTicks.count(stock) > 0 && latestTicks.at(stock).update.TradePrice) {
                indexValue += weight * latestTicks.at(stock).tradePrice;
            }
        }
    }

    double getValue() const {
        return indexValue;
    }
};

class Indicator {
public:
    virtual ~Indicator() = default;
    virtual void calcValue(const Tick& tick) = 0;

    double getLatestValue() const {
        return latestValue;
    }

protected:
    double latestValue;
};


class IndicatorType1 : public Indicator {
public:
    std::deque<float> prices;
    int period = 10; // SMA period
    double sum = 0;

    void calcValue(const Tick& tick) override {
        if (tick.tradePrice > 0) {
            if (prices.size() == period) {
                sum -= prices.front();
                prices.pop_front();
            }
            prices.push_back(tick.tradePrice);
            sum += tick.tradePrice;
            latestValue = sum / prices.size();
        } else {
            // Handle the case where tradePrice is not available
            // For example, you could log a warning message or set latestValue to a default value
            latestValue = 0; // or any other default value
        }
    }
};


class IndicatorType2 : public Indicator {
public:
    double ema = 0;
    int period = 10; // EMA period
    bool initialized = false;

    void calcValue(const Tick& tick) override {
        if (tick.update.TradePrice) {
            if (!initialized) {
                ema = tick.tradePrice;
                initialized = true;
            } else {
                double alpha = 2.0 / (period + 1);
                ema = tick.tradePrice * alpha + ema * (1 - alpha);
            }
            latestValue = ema;
        } else {
            // Handle the case where tradePrice is not available
            // For example, you could log a warning message or set latestValue to a default value
            latestValue = 0; // or any other default value
        }
    }
};

class IndicatorFactory {
public:
    static std::unique_ptr<Indicator> createIndicator(const std::string& indicator_name) {
        if (indicator_name == "IndicatorType1") {
            return std::make_unique<IndicatorType1>();
        } else if (indicator_name == "IndicatorType2") {
            return std::make_unique<IndicatorType2>();
        }
        // Add more else if statements for other indicator types
        throw std::runtime_error("Invalid indicator name: " + indicator_name);
    }
};

class MarketDataProcessor {
    std::unordered_map<uint16_t, std::vector<std::string>> stockToIndices;
    std::queue<Tick> tickQueue;
    std::mutex tickMutex;
    std::condition_variable tickCondVar;
    std::unordered_map<uint16_t, std::vector<std::vector<double>>> contractIndicators;
    std::unordered_map<uint16_t, std::unordered_map<std::string, std::unique_ptr<Indicator>>> contractIndicatorsObjects;
    std::vector<std::string> indicator_list; // This should be populated with the names of the indicators you want to use
    std::unordered_map<std::string, Index> indices;
    std::unordered_map<uint16_t, Tick> latestTicks;
    std::vector<std::thread> workerThreads;
    std::queue<std::function<void()>> tasks;
    std::mutex tasksMutex;
    std::condition_variable tasksCondVar;
    bool stop = false;
    bool parallel = false; // Add this line

public:
    std::unordered_map<std::string, int> indicatorIndices;
    void addStockToIndex(uint16_t stock, const std::string& indexName) {
        stockToIndices[stock].emplace_back(indexName);
    }

    void initializeIndicators(const std::vector<uint16_t>& contracts, const std::vector<std::string>& indicator_list) {
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
    void setParallel(bool parallel) {
        this->parallel = parallel;
    }
    void startEventLoop() {
        if (parallel) {
            parallelEventLoop();
        } else {
            eventLoop();
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

            if (parallel) {
                for (const auto& indicator_name : indicator_list) {
                    tasks.emplace([=] { processIndicator(indicator_name); });
                }
            } else {
                for (const auto& indicator_name : indicator_list) {
                    processIndicator(indicator_name);
                }
            }

            // Update index values
            latestTicks[tick.sid] = tick;
            for (const auto& indexName : stockToIndices[tick.sid]) {
                indices[indexName].calculateValue(latestTicks);
            }
        }
    }
    /* Work stealing
     *
     * #include <tbb/parallel_invoke.h>
#include <tbb/task_scheduler_init.h>

void processTick(const Tick& tick) {
    auto processIndicator = [this, tick](const std::string& indicator_name) {
        auto& indicator = contractIndicatorsObjects[tick.contract][indicator_name];
        indicator->calcValue(tick);
        double latestValue = indicator->getLatestValue();

        // Find the index of the indicator
        int indicator_index = indicatorIndices[indicator_name];

        // Update contractIndicators with the latest value
        contractIndicators[tick.contract][indicator_index].emplace_back(latestValue);
    };

    std::vector<std::function<void()>> tasks;
    for (const auto& indicator_name : indicator_list) {
        tasks.push_back([=] { processIndicator(indicator_name); });
    }

    tbb::parallel_invoke(tasks.begin(), tasks.end());

    // Update index values
    if (stockToIndices.count(tick.contract) > 0) {
        latestTicks[tick.contract] = tick;
        for (const auto& indexName : stockToIndices[tick.contract]) {
            indices[indexName].calculateValue(latestTicks);
        }
    }
}
     */

    void eventLoop() {
        while (true) {
            Tick tick;
            {
                std::unique_lock<std::mutex> lock(tickMutex);
                tickCondVar.wait(lock, [this]{ return !tickQueue.empty(); });

                // Remove one tick from the queue
                tick = tickQueue.front();
                tickQueue.pop();
            }

            // Process the tick
            processTick(tick);
        }
    }

    void parallelEventLoop() {
        while (true) {
            std::vector<Tick> batch;
            {
                std::unique_lock<std::mutex> lock(tickMutex);
                tickCondVar.wait(lock, [this]{ return !tickQueue.empty(); });

                // Adjust batch_size based on the number of available ticks and worker threads
                int min_batch_size = 1; // Set your minimum batch size here
                int batch_size = std::max(min_batch_size, static_cast<int>(tickQueue.size() / workerThreads.size()));

                // Remove up to batch_size ticks from the queue
                for (int i = 0; i < batch_size && !tickQueue.empty(); ++i) {
                    batch.push_back(tickQueue.front());
                    tickQueue.pop();
                }
            }
            // Process the batch of ticks
            for (const Tick& tick : batch) {
                processTick(tick);
            }
        }
    }
    MarketDataProcessor() {
        // Initialize worker threads
        int numThreads = std::thread::hardware_concurrency();
        for (int i = 0; i < numThreads; ++i) {
            workerThreads.emplace_back([this] {
                while (true) {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lock(this->tasksMutex);
                        this->tasksCondVar.wait(lock, [this] {
                            return this->stop || !this->tasks.empty();
                        });
                        if (this->stop && this->tasks.empty())
                            return;
                        task = std::move(this->tasks.front());
                        this->tasks.pop();
                    }
                    task();
                }
            });
        }
    }
    ~MarketDataProcessor() {
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            stop = true;
        }
        tasksCondVar.notify_all();
        // Join worker threads
        for (std::thread &worker : workerThreads) {
            worker.join();
        }
    }


    void addTick(const Tick& tick) {
        auto task = [this, tick]{
            this->processTick(tick);
        };
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            // Don't allow enqueueing after stopping the pool
            if(stop)
                throw std::runtime_error("Enqueue on stopped ThreadPool");
            tasks.emplace(std::move(task));
        }
        tasksCondVar.notify_one();
    }
};
