#include <mkl.h>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <cmath>

// Function to load data from CSV file
std::vector<std::vector<double>> loadData(const std::string& filename) {
    std::vector<std::vector<double>> data;
    std::ifstream file(filename);
    std::string line;
    while (std::getline(file, line)) {
        std::vector<double> row;
        std::stringstream ss(line);
        std::string value;
        while (std::getline(ss, value, ',')) {
            row.push_back(std::stod(value));
        }
        data.push_back(row);
    }
    return data;
}

// Function to standardize data
void standardizeData(std::vector<std::vector<double>>& data) {
    int rows = data.size();
    int cols = data[0].size();
    for (int j = 0; j < cols; ++j) {
        double sum = 0;
        for (int i = 0; i < rows; ++i) {
            sum += data[i][j];
        }
        double mean = sum / rows;
        double sq_sum = 0;
        for (int i = 0; i < rows; ++i) {
            sq_sum += (data[i][j] - mean) * (data[i][j] - mean);
        }
        double stdev = std::sqrt(sq_sum / rows);
        for (int i = 0; i < rows; ++i) {
            data[i][j] = (data[i][j] - mean) / stdev;
        }
    }
}

// Function to compute the covariance matrix
std::vector<double> computeCovariance(const std::vector<std::vector<double>>& data) {
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
    if (status != VSL_STATUS_OK) {
        // Handle error...
    }

    // Compute the covariance matrix
    std::vector<double> cov(p * p);
    status = vsldSSEditCovCor(task, &cov[0], VSL_SS_COV);
    if (status != VSL_STATUS_OK) {
        // Handle error...
    }
    status = vsldSSCompute(task, VSL_SS_COV, VSL_SS_METHOD_1PASS);
    if (status != VSL_STATUS_OK) {
        // Handle error...
    }

    // Delete the summary statistics task
    status = vsldSSDeleteTask(&task);
    if (status != VSL_STATUS_OK) {
        // Handle error...
    }

    return cov;
}

// Function to compute the eigenvalues and eigenvectors of a matrix
std::pair<std::vector<double>, std::vector<double>> computeEigen(const std::vector<double>& matrix, int p) {
    std::vector<double> w(p); // eigenvalues
    std::vector<double> z(p * p); // eigenvectors
    char jobz = 'V'; // compute eigenvalues and eigenvectors
    char uplo = 'U'; // upper triangle of matrix is stored
    MKL_INT lda = p;
    MKL_INT status = dsyev(&jobz, &uplo, &p, &matrix[0], &lda, &w[0], &z[0], &lda);
    if (status != 0) {
        // Handle error...
    }
    return {w, z};
}

// Function to perform Factor Analysis
std::vector<std::vector<double>> fa(const std::vector<std::vector<double>>& data, int n_factors) {
    int p = data[0].size(); // number of variables

    // Compute the covariance matrix
    std::vector<double> cov = computeCovariance(data);

    // Compute the eigenvalues and eigenvectors of the covariance matrix
    auto [w, z] = computeEigen(cov, p);

    // Select the n_factors largest eigenvalues and their corresponding eigenvectors
    std::vector<std::vector<double>> loadings(n_factors, std::vector<double>(p));
    for (int i = 0; i < n_factors; ++i) {
        for (int j = 0; j < p; ++j) {
            loadings[i][j] = z[(p - i - 1) * p + j];
        }
    }

    return loadings;
}

int main() {
    std::vector<std::vector<double>> data = loadData("historical_prices.csv");
    standardizeData(data);
    std::vector<std::vector<double>> loadings = fa(data, 10);
    // Continue with your code...
    return 0;
}
