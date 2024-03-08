
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

