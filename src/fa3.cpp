#include <vector>
std::vector<double> computeCovariance(const std::vector<std::vector<double>>& data) {
    if (data.empty() || data[0].empty()) {
        // Handle error...
    }

    int n = data.size(); // number of observations
    int p = data[0].size(); // number of variables

    for (const auto& row : data) {
        if (row.size() != p) {
            // Handle error...
        }
    }

    std::vector<double> means(p, 0.0);
    std::vector<double> cov(p * p, 0.0);

    for (int i = 0; i < n; ++i) {
        std::vector<double> delta(p);
        for (int j = 0; j < p; ++j) {
            delta[j] = data[i][j] - means[j];
            means[j] += delta[j] / (i + 1);
        }
        if (i > 0) {
            for (int j = 0; j < p; ++j) {
                for (int k = 0; k <= j; ++k) {
                    cov[j * p + k] += delta[j] * delta[k] * (i - 1) / i;
                }
            }
        }
    }

    for (int j = 0; j < p; ++j) {
        for (int k = j + 1; k < p; ++k) {
            cov[j * p + k] = cov[k * p + j]; // make the covariance matrix symmetric
        }
    }

    return cov;
}
