#include "logger.h"

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
