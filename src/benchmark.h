#pragma once
#include <chrono>
#include <fstream>
#include <string>

class Benchmark {
public:
    void start();
    void stopAndLog(const std::string& logFilePath);

private:
    std::chrono::high_resolution_clock::time_point start_time;
};