#pragma once

#include <string>
#include <thread>
#include "CommandLineProcessor.h"
#include "MarketDataProcessor.h"
#include "ConfigurationManager.h"

class Application {
public:
    Application(int argc, char* argv[]);
    ~Application();

    void run();

private:
    CommandLineProcessor cmd;
    MarketDataProcessor processor;
    ConfigurationManager configManager;
    std::string sourcePath;
    std::string buildPath;
    std::string generator;
    std::string toolset;
    std::string initialCache;
    int numTicks;
    std::thread eventLoopThread;

    void parseArguments(int argc, char* argv[]);
    void startEventLoop();
    void processTicks();
    void waitForTermination();
};