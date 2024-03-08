#include "benchmark.h"
#include <fstream>

void Benchmark::start() {
    start_time = std::chrono::high_resolution_clock::now();
}

void Benchmark::stopAndLog(const std::string& logFilePath) {
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    std::ofstream logFile(logFilePath, std::ios_base::app);
    logFile << "Execution time: " << duration << " ms\n";
}