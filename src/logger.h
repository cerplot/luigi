#pragma once
#include <string>
#include <mutex>
#include <fstream>
#include <chrono>

enum class LogLevel {
    INFO,
    DEBUG,
    ERROR
};

class Logger {
public:
    static Logger& getInstance();
    void setLogLevel(LogLevel level);
    void setLogToConsole(bool logToConsole);
    void info(const std::string& message);
    void debug(const std::string& message);
    void error(const std::string& message);

private:
    Logger();
    ~Logger();
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;
    void log(const std::string& level, const std::string& message);

    std::mutex mtx;
    std::mutex logLevelMutex;
    std::ofstream logFile;
    LogLevel logLevel;
    bool logToConsole;
};
