#include <mkl.h>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <cmath>

// Function to load data from CSV file
std::vector<std::vector<float>> loadData(const std::string& filename) {
    std::vector<std::vector<float>> data;
    std::ifstream file(filename);
    std::string line;
    while (std::getline(file, line)) {
        std::vector<float> row;
        std::stringstream ss(line);
        std::string value;
        while (std::getline(ss, value, ',')) {
            row.push_back(std::stof(value));
        }
        data.push_back(row);
    }
    return data;
}

// Function to standardize data
void standardizeData(std::vector<std::vector<float>>& data) {
    int rows = data.size();
    int cols = data[0].size();
    for (int j = 0; j < cols; ++j) {
        float sum = 0;
        for (int i = 0; i < rows; ++i) {
            sum += data[i][j];
        }
        float mean = sum / rows;
        float sq_sum = 0;
        for (int i = 0; i < rows; ++i) {
            sq_sum += (data[i][j] - mean) * (data[i][j] - mean);
        }
        float stdev = std::sqrt(sq_sum / rows);
        for (int i = 0; i < rows; ++i) {
            data[i][j] = (data[i][j] - mean) / stdev;
        }
    }
}

// Function to perform Factor Analysis
std::vector<std::vector<double>> fa(const std::vector<std::vector<double>>& data, int n_factors) {
    int n = data.size(); // number of observations
    int p = data[0].size(); // number of variables

    // Convert the data to a 1D array in column-major order
    std::vector<double> data_1d(n * p);
    for (int j = 0; j < p; ++j) {
        for (int i = 0; i < n; ++i) {
            data_1d[j * n + i] = data[i][j];
        }
    }

    // Create a summary statistics task
    VSLSSTaskPtr task;
    MKL_INT status = vsldSSNewTask(&task, &n, &p, &data_1d[0], VSL_SS_COV);

    // Compute the covariance matrix
    std::vector<double> cov(p * p);
    status = vsldSSEditCovCor(task, &cov[0], VSL_SS_COV);
    status = vsldSSCompute(task, VSL_SS_COV, VSL_SS_METHOD_1PASS);

    // Compute the eigenvalues and eigenvectors of the covariance matrix
    std::vector<double> w(p); // eigenvalues
    std::vector<double> z(p * p); // eigenvectors
    char jobz = 'V'; // compute eigenvalues and eigenvectors
    char uplo = 'U'; // upper triangle of cov is stored
    MKL_INT lda = p;
    status = dsyev(&jobz, &uplo, &p, &cov[0], &lda, &w[0], &z[0], &lda);

    // Select the n_factors largest eigenvalues and their corresponding eigenvectors
    std::vector<std::vector<double>> loadings(n_factors, std::vector<double>(p));
    for (int i = 0; i < n_factors; ++i) {
        for (int j = 0; j < p; ++j) {
            loadings[i][j] = z[(p - i - 1) * p + j];
        }
    }

    // Delete the summary statistics task
    status = vsldSSDeleteTask(&task);

    return loadings;
}

int main() {
    std::vector<std::vector<float>> data = loadData("historical_prices.csv");
    standardizeData(data);
    std::vector<std::vector<double>> loadings = fa(data, 10);
    // Continue with your code...
    return 0;
}
