#include <iostream>
#include <fstream>
#include <chrono>
#include <csignal>
#include <random>
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


struct StockData {
    double weight;
    double lastTradePrice;
};

class Index {
private:
    std::vector<StockData> stocks;
    double indexValue = 0.0;

public:
    void addStock(uint16_t stock, double weight) {
        if (stock >= stocks.size()) {
            stocks.resize(stock + 1);
        }
        stocks[stock].weight = weight;
    }

    void update(const Tick& tick) {
        if (tick.sid < stocks.size() && tick.update.TradePrice) {
            indexValue -= stocks[tick.sid].weight * stocks[tick.sid].lastTradePrice;
            indexValue += stocks[tick.sid].weight * tick.tradePrice;
            stocks[tick.sid].lastTradePrice = tick.tradePrice;
        }
    }

    double getValue() const {
        return indexValue;
    }

    const std::vector<StockData>& getStocks() const {
        return stocks;
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

#include <iostream>

// Function to initialize indicators
void initializeIndicators(MarketDataProcessor& processor) {
    std::vector<uint16_t> contracts = {1, 2, 3}; // Replace with your actual contract IDs
    std::vector<std::string> indicator_list = {"IndicatorType1", "IndicatorType2"};
    try {
        processor.initializeIndicators(contracts, indicator_list);
    } catch (const std::runtime_error& e) {
        std::cerr << "Failed to initialize indicators: " << e.what() << std::endl;
        exit(1);
    }
}

// Function to add stocks to index
void addStocksToIndex(MarketDataProcessor& processor) {
    try {
        processor.addStockToIndex(1, "Index1");
        processor.addStockToIndex(2, "Index2");
        processor.addStockToIndex(3, "Index3");
    } catch (const std::runtime_error& e) {
        std::cerr << "Failed to add stocks to index: " << e.what() << std::endl;
        exit(1);
    }
}

// Function to feed processor with ticks
void feedProcessorWithTicks(MarketDataProcessor& processor) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(50, 150);

    for (uint16_t i = 0; i < 100; ++i) {
        Tick tick;
        tick.sid = i % 3 + 1; // Cycle through the contract IDs
        tick.exch = Exchange::Exchange1;
        tick.timestamp = i;
        tick.bidPrice = i * 1.0f;
        tick.askPrice = i * 1.0f + 0.5f;
        tick.tradePrice = i * 1.0f + 0.25f;
        tick.bidSize = i;
        tick.askSize = i + 1;
        tick.tradeSize = i + 2;
        tick.update.BidPrice = 1;
        tick.update.AskPrice = 1;
        tick.update.TradePrice = 1;

        try {
            processor.addTick(tick);
        } catch (const std::runtime_error& e) {
            std::cerr << "Failed to add tick: " << e.what() << std::endl;
            exit(1);
        }

        // Sleep for a random time to simulate real-time data feed
        std::this_thread::sleep_for(std::chrono::milliseconds(dis(gen)));
    }
}

// Global variable to handle termination signal
std::atomic<bool> terminate(false);

// Signal handler
void signalHandler(int signum) {
    std::cout << "Interrupt signal (" << signum << ") received.\n";
    terminate = true;
}

// Function to read configuration file
void readConfigFile(MarketDataProcessor& processor) {
    // Parse the TOML file
    auto config = toml::parse_file("config.toml");

    // Read the contracts and indicator list from the configuration file
    std::vector<uint16_t> contracts = toml::find<std::vector<uint16_t>>(config, "contracts");
    std::vector<std::string> indicator_list = toml::find<std::vector<std::string>>(config, "indicator_list");

    // Initialize the indicators
    try {
        processor.initializeIndicators(contracts, indicator_list);
    } catch (const std::runtime_error& e) {
        std::cerr << "Failed to initialize indicators: " << e.what() << std::endl;
        exit(1);
    }

    // Read the stocks and indices from the configuration file
    auto stocks_to_indices = toml::find<std::unordered_map<uint16_t, std::vector<std::string>>>(config, "stocks_to_indices");

    // Add the stocks to the indices
    for (const auto& [stock, indices] : stocks_to_indices) {
        for (const auto& index : indices) {
            try {
                processor.addStockToIndex(stock, index);
            } catch (const std::runtime_error& e) {
                std::cerr << "Failed to add stock to index: " << e.what() << std::endl;
                exit(1);
            }
        }
    }
}


#define BENCHMARK_ENABLED // Comment this line to disable benchmarking

int main(int argc, char* argv[]) {
    // Register signal handler
    signal(SIGINT, signalHandler);

    MarketDataProcessor processor;

    // Read configuration file
    readConfigFile(processor);

    // Start the event loop in a separate thread
    std::thread eventLoopThread([&processor] { processor.startEventLoop(); });

    // Process ticks based on command line argument
    int numTicks = argc > 1 ? std::stoi(argv[1]) : 100;

#ifdef BENCHMARK_ENABLED
    // Start benchmark
    auto start = std::chrono::high_resolution_clock::now();
#endif

    feedProcessorWithTicks(processor, numTicks);

#ifdef BENCHMARK_ENABLED
    // End benchmark
    auto end = std::chrono::high_resolution_clock::now();

    // Calculate duration
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    // Log the benchmark result
    std::ofstream logFile("benchmark.log", std::ios_base::app);
    logFile << "Execution time: " << duration << " ms\n";
#endif

    // Wait for termination signal
    while (!terminate) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    // Stop the event loop
    processor.stop = true;
    eventLoopThread.join();

    return 0;
}
