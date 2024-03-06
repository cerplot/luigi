//
// Created by drahmedov on 3/5/2024.
//
#include <fstream>
#include <vector>
#include <string>

class DataAcquisition {
public:
    DataAcquisition(const std::string& filename) : filename(filename) {}
    ~DataAcquisition() {}

    // Method to fetch data
    std::vector<std::vector<double>> fetchData() {
        std::vector<std::vector<double>> data;
        std::ifstream file(filename);
        std::string line;

        while (std::getline(file, line)) {
            std::vector<double> row;
            std::string value;
            std::stringstream ss(line);

            while (std::getline(ss, value, ',')) {
                row.push_back(std::stod(value));
            }

            data.push_back(row);
        }

        return data;
    }

private:
    std::string filename;
};


class DataPreprocessing {
public:
    DataPreprocessing(/* args */);
    ~DataPreprocessing();

    // Methods to preprocess data
    void preprocessData();
};
class Strategy {
public:
    Strategy(/* args */);
    ~Strategy();

    // Methods to implement trading strategy
    void generateSignals();
};
class Backtester {
public:
    Backtester(/* args */);
    ~Backtester();

    // Methods to backtest the strategy
    void backtest();
};
class Execution {
public:
    Execution(/* args */);
    ~Execution();

    // Methods to execute trades
    void executeTrades();
};
int main() {
    // Create objects of the classes
    DataAcquisition dataAcquisition;
    DataPreprocessing dataPreprocessing;
    Strategy strategy;
    Backtester backtester;
    Execution execution;

    // Call the methods in the appropriate order
    dataAcquisition.fetchData();
    dataPreprocessing.preprocessData();
    strategy.generateSignals();
    backtester.backtest();
    execution.executeTrades();

    return 0;
}