#include "application.h"
#include "logger.h"
#include "benchmark.h"
#include <iostream>
#include <exception>

Application::Application(int argc, char* argv[]) {
    cmd = CommandLineProcessor(argc, argv);
    sourcePath = cmd.getArgument("S");
    buildPath = cmd.getArgument("B");
    generator = cmd.getArgument("G");
    toolset = cmd.getArgument("T");
    initialCache = cmd.getArgument("C");
    configManager.loadConfiguration();
    readConfigFile(processor);

    if (cmd.getFlag("version")) {
        std::cout << "Application version: 1.0.0" << std::endl;
        exit(0);
    }
    cmd.buildProject();
}

Application::~Application() {
    if (eventLoopThread.joinable()) {
        eventLoopThread.join();
    }
}

void Application::run() {
    try {
        startEventLoop();
        processTicks();
        waitForTermination();
    } catch (const ApplicationException& e) {
        Logger::getInstance().error(e.what());
    }
}

void Application::parseArguments(int argc, char* argv[]) {
    numTicks = argc > 1 ? std::stoi(argv[1]) : 100;
}

void Application::startEventLoop() {
    eventLoopThread = std::thread([&] { processor.startEventLoop(); });
}

void Application::processTicks() {
    Benchmark benchmark;
    benchmark.start();

    try {
        feedProcessorWithTicks(processor, numTicks);
    } catch (const std::exception& e) {
        Logger::getInstance().error("Error: " + std::string(e.what()));
        exit(1);
    }

    benchmark.stopAndLog("benchmark.log");
}

void Application::waitForTermination() {
    while (!terminate_te) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    processor.stop = true;
}


int main(int argc, char* argv[]) {
    Application app(argc, argv);
    app.run();
    return 0;
}
