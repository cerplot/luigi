#include <sstream>
#include <iostream>
#include <fstream>
#include <mutex>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <atomic>
#include <csignal>
#include <stdexcept>
#include <algorithm>
#include <set>
#include "config_parser.h"
#include <toml.hpp>
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
#include <string>
#include <map>
#include <unistd.h>


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
private:
    struct StockData {
        double weight;
        double lastTradePrice;

        StockData(double weight = 0.0, double lastTradePrice = 0.0)
                : weight(weight), lastTradePrice(lastTradePrice) {}

        void updateLastTradePrice(double price) {
            lastTradePrice = price;
        }
    };

    std::vector<StockData> stocks;
    double indexValue = 0.0;

public:
    Index(size_t stockSize) : stocks(stockSize) {}

    void addStock(uint16_t stock, double weight) {
        stocks[stock] = StockData(weight);
    }

    void update(const Tick& tick) {
        indexValue += stocks[tick.sid].weight * (tick.tradePrice - stocks[tick.sid].lastTradePrice);
        stocks[tick.sid].updateLastTradePrice(tick.tradePrice);
    }

    double getValue() const {
        return indexValue;
    }

};

class Indicator {
public:
    // Constructor to initialize latestValue
    Indicator() : latestValue(0.0) {}

    // Virtual destructor
    virtual ~Indicator() = default;

    // Pure virtual function to calculate the value of the indicator
    // This function must be implemented by all derived classes
    virtual void calcValue(const Tick& tick) = 0;

    // Function to get the latest value of the indicator
    double getLatestValue() const {
        return latestValue;
    }

protected:
    // Latest value of the indicator
    double latestValue;
};


class IndicatorType1 : public Indicator {
public:
    std::deque<float> prices;
    int period = 10; // SMA period
    double sum = 0;

    void calcValue(const Tick& tick) override {
        if (tick.update.TradePrice) {
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

std::vector<std::vector<double>> combine_indicators_for_all_stocks(const std::string& indicator1_name) {
    // Create a map to store the combined indicators
    std::map<uint32_t, std::vector<std::optional<double>>> combinedIndicators;

    // Iterate over each stock
    for (const auto& [stock, indicators] : contractIndicatorsObjects) {
        // Get the UpdateTimeIndicator and Indicator1 for the stock
        const auto& updateTimeIndicator = indicators.at("UpdateTimeIndicator");
        const auto& indicator1 = indicators.at(indicator1_name);

        // Iterate over the UpdateTimeIndicator and Indicator1
        for (size_t i = 0; i < updateTimeIndicator->getLatestValue().size(); ++i) {
            // Get the update time and the value of Indicator1
            uint32_t updateTime = static_cast<uint32_t>(updateTimeIndicator->getLatestValue()[i]);
            double indicator1Value = indicator1->getLatestValue()[i];

            // Add the value of Indicator1 to the combinedIndicators map
            combinedIndicators[updateTime].push_back(indicator1Value);
        }
    }

    // Forward fill missing values
    std::optional<double> lastValue;
    for (auto& [updateTime, indicatorValues] : combinedIndicators) {
        for (auto& value : indicatorValues) {
            if (value.has_value()) {
                lastValue = value.value();
            } else if (lastValue.has_value()) {
                value = lastValue;
            }
        }
    }

    // Convert the map to a 2D array
    std::vector<std::vector<double>> combinedIndicatorsArray;
    for (const auto& [updateTime, indicatorValues] : combinedIndicators) {
        combinedIndicatorsArray.push_back(std::vector<double>(indicatorValues.begin(), indicatorValues.end()));
    }

    return combinedIndicatorsArray;
}

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
    using CreateIndicatorFunc = std::function<std::unique_ptr<Indicator>()>;

private:
    static std::unordered_map<std::string, CreateIndicatorFunc> indicatorMap;

public:
    static void registerIndicator(const std::string& name, CreateIndicatorFunc createFunc) {
        indicatorMap[name] = std::move(createFunc);
    }

    static bool isRegistered(const std::string& name) {
        return indicatorMap.find(name) != indicatorMap.end();
    }

    static std::unique_ptr<Indicator> createIndicator(const std::string& name) {
        auto it = indicatorMap.find(name);
        if (it == indicatorMap.end()) {
            throw std::runtime_error("Invalid indicator name: " + name);
        }
        return it->second();
    }

    [[maybe_unused]] static void initialize() {
        registerIndicator("IndicatorType1", []{ return std::make_unique<IndicatorType1>(); });
        registerIndicator("IndicatorType2", []{ return std::make_unique<IndicatorType2>(); });
        // Add more indicators here
    }
};
//
//// Initialize the static member outside of class
//std::unordered_map<std::string, IndicatorFactory::CreateIndicatorFunc> IndicatorFactory::indicatorMap = {};
//
//// Now the initialization should work
//[[maybe_unused]] IndicatorFactory::initialize();


// Initialize the static member
std::unordered_map<std::string, IndicatorFactory::CreateIndicatorFunc> IndicatorFactory::indicatorMap = {
        {"IndicatorType1", []{ return std::make_unique<IndicatorType1>(); }},
        {"IndicatorType2", []{ return std::make_unique<IndicatorType2>(); }}
        // Add more indicators here
};


class TaskQueue {
private:
    std::queue<std::function<void()>> tasks;
    std::mutex tasksMutex;
    std::condition_variable tasksCondVar;
    bool stop = false;

public:
    void addTask(std::function<void()> task) {
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            if(stop)
                throw std::runtime_error("Enqueue on stopped TaskQueue");
            tasks.emplace(std::move(task));
        }
        tasksCondVar.notify_one();
    }

    std::function<void()> getTask() {
        std::unique_lock<std::mutex> lock(tasksMutex);
        tasksCondVar.wait(lock, [this]{ return stop || !tasks.empty(); });
        if (stop && tasks.empty())
            return nullptr;
        auto task = std::move(tasks.front());
        tasks.pop();
        return task;
    }

    void stopQueue() {
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            stop = true;
        }
        tasksCondVar.notify_all();
    }
};

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
    TaskQueue taskQueue;
    TickProcessor tickProcessor;
    IndicatorManager indicatorManager;
    bool stop = false;
    bool parallel = false;
public:
    std::unordered_map<std::string, int> indicatorIndices;
    MarketDataProcessor(const std::vector<std::string>& indicator_list)
            : indicatorManager(indicator_list), tickProcessor(indicator_list) {}

    void addStockToIndex(uint16_t stock, const std::string& indexName) {
        stockToIndices[stock].emplace_back(indexName);
    }

    void initializeIndicators(const std::vector<uint16_t>& contracts) {
        indicatorManager.initializeIndicators(contracts);
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
        tickProcessor.processTick(tick);
    }

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

    void addTick(const Tick& tick) {
        auto task = [this, tick]{
            this->processTick(tick);
        };
        taskQueue.addTask(std::move(task));
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
std::atomic<bool> terminate_te(false);

// Signal handler
void signalHandler(int signum) {
    std::cout << "Interrupt signal (" << signum << ") received.\n";
    terminate_te = true;
}

class ConfigManager {
private:
    const std::filesystem::path defaultConfigFilePath = "default_config.toml"; // replace with your default config file path
    std::shared_ptr<toml::table> config;

public:
    ConfigManager(const std::filesystem::path& configFilePath) {
        config = validate_config_file(defaultConfigFilePath, configFilePath);
    }

    template<typename T>
    T get(const std::string& key) const {
        return config->at(key).value<T>();
    }

    bool contains(const std::string& key) const {
        return config->contains(key);
    }
};


void readConfigFile(MarketDataProcessor& processor) {
    // Parse the TOML file
    std::string stringPath = "config.toml";
    std::filesystem::path filePath = stringPath;
    std::filesystem::path defaultConfigFilePath = "default_config.toml"; // replace with your default config file path

    std::shared_ptr<toml::table> config = validate_config_file(defaultConfigFilePath, filePath);
    config->
    // Read the contracts and indicator list from the configuration file
    auto contracts = config->at("contracts").value<std::vector<uint16_t>>();
    std::vector<std::string> indicator_list = toml::get<std::vector<std::string>>(config->at("indicator_list"));

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

class SignalHandler {
public:
    static void registerSignalHandler() {
        signal(SIGINT, handle);
    }

private:
    static void handle(int signum) {
        std::cout << "Interrupt signal (" << signum << ") received.\n";
        terminate_te = true;
    }
};

class Benchmark {
public:
    void start() {
        start_time = std::chrono::high_resolution_clock::now();
    }

    void stopAndLog(const std::string& logFilePath) {
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
        std::ofstream logFile(logFilePath, std::ios_base::app);
        logFile << "Execution time: " << duration << " ms\n";
    }

private:
    std::chrono::high_resolution_clock::time_point start_time;
};

enum class LogLevel {
    INFO,
    DEBUG,
    ERROR
};

class Logger {
public:
    static Logger& getInstance() {
        static Logger instance;
        return instance;
    }
    void setLogLevel(LogLevel level) {
        std::lock_guard<std::mutex> lock(logLevelMutex);
        logLevel = level;
    }
    void setLogToConsole(bool logToConsole) {
        std::lock_guard<std::mutex> lock(mtx);
        this->logToConsole = logToConsole;
    }
    void info(const std::string& message) {
        if (logLevel <= LogLevel::INFO)
            log("INFO", message);
    }
    void debug(const std::string& message) {
        if (logLevel <= LogLevel::DEBUG)
            log("DEBUG", message);
    }

    void error(const std::string& message) {
        if (logLevel <= LogLevel::ERROR)
            log("ERROR", message);
    }

private:
    std::mutex mtx;
    std::mutex logLevelMutex;
    std::ofstream logFile;
    LogLevel logLevel = LogLevel::INFO;
    bool logToConsole = true;

    Logger() : logFile("app.log", std::ios_base::app) {
        if (!logFile.is_open()) {
            throw std::runtime_error("Logger: Unable to open log file");
        }
    }

    ~Logger() {
        if (logFile.is_open()) {
            logFile.close();
        }
    }

    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    void log(const std::string& level, const std::string& message) {
        std::lock_guard<std::mutex> lock(mtx);
        auto now = std::chrono::system_clock::now();
        auto now_c = std::chrono::system_clock::to_time_t(now);
        std::stringstream ss;
        ss << std::put_time(std::localtime(&now_c), "%F %T") << " " << level << ": " << message;
        std::string logMessage = ss.str();
        if (logToConsole) {
            std::cout << logMessage << std::endl;
        }
        logFile << logMessage << std::endl;
    }
};

class CommandLineProcessor {
public:
    CommandLineProcessor(int argc, char* argv[]) {
        parseArguments(argc, argv);
    }

    std::string getArgument(const std::string& name) const {
        auto it = arguments.find(name);
        if (it == arguments.end()) {
            if (name == "S" || name == "B") {
                char buffer[FILENAME_MAX];
                getcwd(buffer, FILENAME_MAX);
                std::string currentDirectory(buffer);
                return currentDirectory;
            }
            throw std::runtime_error("Argument not found: " + name + "\n" + usage());
        }
        return it->second;
    }

    bool getFlag(const std::string& name) const {
        return flags.count(name) > 0;
    }

private:
    std::map<std::string, std::string> arguments;
    std::set<std::string> flags;

    void buildProject() const {
        if (getFlag("--build")) {
            std::string buildCommand = "cmake --build " + getArgument("B");
            if (isRegistered("--target")) {
                buildCommand += " --target " + getArgument("--target");
            }
            std::system(buildCommand.c_str());
        }
    }

    void parseArguments(int argc, char* argv[]) {
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg[0] == '-') {
                arg = arg.substr(1);  // Remove the leading '-'
                if (arg == "D" && i + 1 < argc) {  // Check for '-D' flag
                    std::string var = argv[i + 1];
                    size_t pos = var.find('=');
                    if (pos != std::string::npos) {
                        std::string name = var.substr(0, pos);
                        std::string value = var.substr(pos + 1);
                        arguments[name] = value;
                        ++i;  // Skip the value
                    } else {
                        throw std::runtime_error("Invalid argument: " + arg + "\n" + usage());
                    }
                } else if (arg == "G" || arg == "T" || arg == "C" || arg == "E" || arg == "L" || arg == "P" || arg == "N" || arg == "--build") {
                    if (i + 1 < argc && argv[i + 1][0] != '-') {
                        std::string value = argv[i + 1];
                        arguments[arg] = value;
                        ++i;  // Skip the value
                    } else {
                        // If the argument does not have a value, treat it as a flag
                        flags.insert(arg);
                    }
                } else {
                    // If the argument does not have a value, treat it as a flag
                    flags.insert(arg);
                }
            } else {
                throw std::runtime_error("Invalid argument: " + arg + "\n" + usage());
            }
        }
    }

    std::string usage() const {
        return "Usage: program [-flag] [-argument [value]] ...";
    }
};


class Application {

public:
    Application(int argc, char* argv[]) {
        CommandLineProcessor cmd(argc, argv);
        sourcePath = cmd.getArgument("S");
        buildPath = cmd.getArgument("B");
        generator = cmd.getArgument("G");
        toolset = cmd.getArgument("T");
        initialCache = cmd.getArgument("C");
        ConfigurationManager configManager;
        configManager.loadConfiguration();
        readConfigFile(processor);

        if (cmd.getFlag("version")) {
            std::cout << "Application version: 1.0.0" << std::endl;
            exit(0);
        }
        cmd.buildProject();
    }

    ~Application() {
        if (eventLoopThread.joinable()) {
            eventLoopThread.join();
        }
    }

    void run() {
        try {
            startEventLoop();
            processTicks();
            waitForTermination();
        } catch (const ApplicationException& e) {
            Logger::logError(e.what());
        }
    }

private:
    MarketDataProcessor processor;
    int numTicks;
    std::thread eventLoopThread;

    void parseArguments(int argc, char* argv[]) {
        // Parse command line arguments here
        numTicks = argc > 1 ? std::stoi(argv[1]) : 100;
    }

    void startEventLoop() {
        eventLoopThread = std::thread([&] { processor.startEventLoop(); });
    }

    void processTicks() {
        // Start benchmark
        Benchmark benchmark;
        benchmark.start();

        try {
            feedProcessorWithTicks(processor, numTicks);
        } catch (const std::exception& e) {
            Logger::logError("Error: " + std::string(e.what()));
            exit(1);
        }

        // Stop benchmark and log result
        benchmark.stopAndLog("benchmark.log");
    }

    void waitForTermination() {
        while (!terminate_te) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        processor.stop = true;
    }
};

int main(int argc, char* argv[]) {
    Application app(argc, argv);
    app.run();
    return 0;
}
