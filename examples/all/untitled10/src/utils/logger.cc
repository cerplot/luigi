#include "logger.h"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <chrono>
namespace te {

    Logger* Logger::getLogger() {
        if (logger_ == nullptr) {
            logger_ = new Logger();
        }
        return logger_;
    }

    void Logger::setLogLevel(LogLevel level) {
        std::lock_guard<std::mutex> lock(logLevelMutex);
        logLevel = level;
    }

    void Logger::setLogToConsole(bool logToConsole) {
        std::lock_guard<std::mutex> lock(mtx);
        this->logToConsole = logToConsole;
    }

    void Logger::info(const std::string& message) {
        if (logLevel <= LogLevel::INFO)
            log("INFO", message);
    }

    void Logger::debug(const std::string& message) {
        if (logLevel <= LogLevel::DEBUG)
            log("DEBUG", message);
    }

    void Logger::error(const std::string& message) {
        if (logLevel <= LogLevel::ERROR)
            log("ERROR", message);
    }

    Logger::Logger() : logFile("log.txt", std::ios_base::app) {
        if (!logFile.is_open()) {
            throw std::runtime_error("Logger: Unable to open log file");
        }
    }

    Logger::~Logger() {
        if (logFile.is_open()) {
            logFile.close();
        }
    }

    void Logger::log(const std::string& level, const std::string& message) {
        std::lock_guard<std::mutex> lock(mtx);
        auto now = std::chrono::system_clock::now();
        auto now_c = std::chrono::system_clock::to_time_t(now);
        std::stringstream ss;
        std::tm tm;
        localtime_s(&tm, &now_c);
        ss << std::put_time(&tm, "%F %T") << " " << level << ": " << message;
        std::string logMessage = ss.str();
        if (logToConsole) {
            std::cout << logMessage << std::endl;
        }
        logFile << logMessage << std::endl;
    }
}
