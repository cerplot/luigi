#include "gtest/gtest.h"
#include "logger.h"
#include <fstream>
#include <vector>
#include <algorithm>

class LoggerTest : public ::testing::Test {
protected:
    std::string logFileName = "app.log";

    void SetUp() override {
        // Delete the log file if it exists
        std::remove(logFileName.c_str());
    }

    void TearDown() override {
        // Delete the log file after the test
        std::remove(logFileName.c_str());
    }

    std::vector<std::string> readLogFile() {
        std::ifstream logFile(logFileName);
        std::vector<std::string> lines;
        std::string line;
        while (std::getline(logFile, line)) {
            lines.push_back(line);
        }
        return lines;
    }

    bool findInLogFile(const std::string& message) {
        auto lines = readLogFile();
        for (const auto& line : lines) {
            if (line.find(message) != std::string::npos) {
                return true;
            }
        }
        return false;
    }
};

TEST_F(LoggerTest, TestSingleton) {
    Logger* logger1 = Logger::getLogger();
    Logger* logger2 = Logger::getLogger();
    ASSERT_EQ(&logger1, &logger2);
}

TEST_F(LoggerTest, TestLogLevel) {
    Logger* logger = Logger::getLogger();
    logger->setLogLevel(LogLevel::DEBUG);
    logger->debug("Debug message");
    ASSERT_TRUE(findInLogFile("Debug message"));
    logger->setLogLevel(LogLevel::ERROR);
    logger->debug("Another debug message");
    ASSERT_FALSE(findInLogFile("Another debug message"));
}

TEST_F(LoggerTest, TestLogToConsole) {
    Logger* logger = Logger::getLogger();
    logger->setLogLevel(LogLevel::INFO);
    logger->setLogToConsole(true);
    logger->info("Info message");
    ASSERT_TRUE(findInLogFile("Info message"));
}

TEST_F(LoggerTest, TestInfo) {
    Logger * logger = Logger::getLogger();
    logger->info("Info message");
    ASSERT_TRUE(findInLogFile("Info message"));
}

TEST_F(LoggerTest, TestDebug) {
    Logger * logger = Logger::getLogger();
    logger->setLogLevel(LogLevel::DEBUG);
    logger->debug("Debug message");
    ASSERT_TRUE(findInLogFile("Debug message"));
}

TEST_F(LoggerTest, TestError) {
    Logger* logger = Logger::getLogger();
    logger->error("Error message");
    ASSERT_TRUE(findInLogFile("Error message"));
}

TEST_F(LoggerTest, TestLogBeforeSetLevel) {
    Logger * logger = Logger::getLogger();
    logger->info("Info message");
    ASSERT_FALSE(findInLogFile("Info message"));
}

TEST_F(LoggerTest, TestLogHigherLevel) {
    Logger* logger = Logger::getLogger();
    logger->debug("Debug message");
    ASSERT_FALSE(findInLogFile("Debug message"));
}

TEST_F(LoggerTest, TestLogFileNotOpen) {
    Logger* logger = Logger::getLogger();
    std::remove(logFileName.c_str());
    logger->info("Info message");
    ASSERT_FALSE(findInLogFile("Info message"));
}

TEST_F(LoggerTest, TestLogEmptyMessage) {
    Logger* logger = Logger::getLogger();
    logger->info("");
    ASSERT_FALSE(findInLogFile("INFO"));
}

TEST_F(LoggerTest, TestLogAfterSetLevel) {
    Logger* logger = Logger::getLogger();
    logger->info("Info message");
    ASSERT_TRUE(findInLogFile("Info message"));
    logger->setLogLevel(LogLevel::ERROR);
    logger->info("Another info message");
    ASSERT_FALSE(findInLogFile("Another info message"));
}