#include <iostream>
#include <vector>
#include <mkl.h>
#include <unordered_map>
#include <cmath>
std::pair<std::vector<double>, std::vector<double>> calculateTarget(const std::vector<double>& prices, double smoothingFactor, double delta) {
    std::vector<double> shortTermObjectiveSeries(prices.size(), 0.0);
    std::vector<double> longTermObjectiveSeries(prices.size(), 0.0);
    double smoothedChange = 0.0;
    double objective = 0.0;
    for (size_t i = prices.size() - 1; i < prices.size(); --i) {
        size_t j = std::min(i + static_cast<size_t>(delta), prices.size() - 1);
        shortTermObjectiveSeries[i] = prices[j] - prices[i];
        if (i + delta + 1 < prices.size()) {
            double priceChange = prices[i + static_cast<size_t>(delta) + 1] - prices[i + static_cast<size_t>(delta)];
            smoothedChange = smoothingFactor * priceChange + (1 - smoothingFactor) * smoothedChange;
            objective += smoothedChange;
            longTermObjectiveSeries[i] = objective;
        }
    }
    return {shortTermObjectiveSeries, longTermObjectiveSeries};
}


std::vector<double> calculateTarget(const std::vector<double>& prices, double smoothingFactor) {
    double smoothedChange = 0.0;
    double target = 0.0;
    std::vector<double> target_series(prices.size() - 1, 0.0);

    for (int i = prices.size() - 1; i > 0; --i) {
        double priceChange = prices[i] - prices[i - 1];
        smoothedChange = smoothingFactor * priceChange + (1 - smoothingFactor) * smoothedChange;
        target += smoothedChange;
        target_series[i - 1] = target;
    }
    return target_series;
}

std::unordered_map<std::string, double> calculateObjectives(const std::unordered_map<std::string, std::vector<double>>& stockPrices, double smoothingFactor) {
    std::unordered_map<std::string, double> objectives;

    for (const auto& [stock, prices] : stockPrices) {
        objectives[stock] = calculateTarget(prices, smoothingFactor);
    }

    return objectives;
}

class Solver {
    int Num;
    int n;
    int ns;
    double eps = 1e-10;
    std::vector<double> d;
    std::vector<int> m;
    std::vector<double> U;
    std::vector<double> eig_value;
    std::vector<double> eig_vector;

public:
    void dsyev(std::vector<double>& A) {
        MKL_INT info;
        char jobz = 'V'; // Compute eigenvalues and eigenvectors.
        char uplo = 'U'; // Upper triangle of A is stored.
        MKL_INT n = sqrt(A.size());
        MKL_INT lda = n;
        std::vector<double> w(n);
        info = LAPACKE_dsyev(LAPACK_ROW_MAJOR, jobz, uplo, n, A.data(), lda, w.data());

        if (info != 0) {
            eig_value = std::vector<double>(Num, 0.0);
            eig_vector = std::vector<double>(Num * Num, 0.0);
        } else {
            eig_value = w;
            eig_vector = A;
        }
    }

    void left_solver(std::vector<double>& A) {
        Num = sqrt(A.size());
        d.resize(Num);
        for (int i = 0; i < Num; i++) {
            d[i] = 1.0 / sqrt(A[i * Num + i]);
            if (A[i * Num + i] >= eps) {
                m.push_back(i);
            }
        }

        n = m.size();
        U.resize(n * n);
        for (int i = 0; i < n; i++) {
            for (int j = i; j < n; j++) {
                U[i * n + j] = d[m[i]] * A[m[i] * Num + m[j]] * d[m[j]];
            }
        }
        dsyev(U);
        int small = 0;
        double tol = 0.01;
        while (small < n && eig_value[small] < tol) {
            small++;
        }

        eig_value = std::vector<double>(eig_value.begin() + small, eig_value.end());
        eig_vector = std::vector<double>(eig_vector.begin() + small * n, eig_vector.end());
        ns = eig_value.size();
    }

    std::vector<double> solve(std::vector<double>& b) {
        if (ns == 0) {
            return std::vector<double>(Num, 0.0);
        }

        std::vector<double> temp(ns);
        for (int i = 0; i < ns; i++) {
            double sum = 0.0;
            for (int j = 0; j < n; j++) {
                sum += eig_vector[j * ns + i] * d[m[j]] * b[m[j]];
            }
            temp[i] = sum / eig_value[i];
        }

        std::vector<double> result(Num);
        for (int i = 0; i < n; i++) {
            double sum = 0.0;
            for (int j = 0; j < ns; j++) {
                sum += eig_vector[i * ns + j] * temp[j];
            }
            result[m[i]] = d[m[i]] * sum;
        }

        return result;
    }
};

class KalmanFilter {
private:
    double state_estimate_; // The current estimate of the state
    double estimate_uncertainty_; // The current uncertainty of the state estimate

public:
    // Initialize the filter with an initial state estimate and uncertainty
    KalmanFilter(double initial_state_estimate, double initial_estimate_uncertainty)
            : state_estimate_(initial_state_estimate), estimate_uncertainty_(initial_estimate_uncertainty) {}

    // Update the state estimate based on a new measurement
    void update(double measurement, double measurement_noise) {
        // Calculate the Kalman gain
        double kalman_gain = estimate_uncertainty_ / (estimate_uncertainty_ + measurement_noise);

        // Update the state estimate and uncertainty
        state_estimate_ = state_estimate_ + kalman_gain * (measurement - state_estimate_);
        estimate_uncertainty_ = (1 - kalman_gain) * estimate_uncertainty_;
    }

    // Predict the next state
    void predict(double control_input, double control_noise) {
        // Update the state estimate and uncertainty based on the control input
        state_estimate_ = state_estimate_ + control_input;
        estimate_uncertainty_ = estimate_uncertainty_ + control_noise;
    }

    // Get the current state estimate
    double getStateEstimate() const {
        return state_estimate_;
    }

    // Get the current estimate uncertainty
    double getEstimateUncertainty() const {
        return estimate_uncertainty_;
    }
};

#include <vector>

class OnlineWhiteningFilter {
private:
    std::vector<double> theta;
    std::vector<double> P;
    double lambda;

public:
    OnlineWhiteningFilter(int n, double lambda, double var) : lambda(lambda) {
        P = std::vector<double>(n, var);
        theta = std::vector<double>(n, 0);
    }

    double update(double x) {
        double P_x = P[0] * x;
        double g = 1.0 / (lambda + x * P_x);
        double y = theta[0] * x;
        double e = x - y;
        theta[0] += e * g * P_x;
        P[0] = (P[0] - g * P_x * P_x) / lambda;
        return y;
    }
};

#include <cmath>

class EWMSFilter {
private:
    double alpha;
    double mean;
    double variance;

public:
    EWMSFilter(double alpha) : alpha(alpha), mean(0), variance(0) {}

    double update(double x) {
        mean = alpha * x + (1 - alpha) * mean;
        double diff = x - mean;
        variance = alpha * (diff * diff) + (1 - alpha) * variance;
        return diff / std::sqrt(variance);
    }
};

#include <vector>

class AdaptiveLineEnhancer {
private:
    std::vector<double> weights;
    double mu;

public:
    AdaptiveLineEnhancer(int filterLength, double mu) : mu(mu) {
        weights = std::vector<double>(filterLength, 0);
    }

    double update(const std::vector<double>& input) {
        double output = 0;
        for (int i = 0; i < weights.size(); ++i) {
            output += weights[i] * input[i];
        }

        double error = input.back() - output;
        for (int i = 0; i < weights.size(); ++i) {
            weights[i] += 2 * mu * error * input[i];
        }

        return output;
    }
};

class WLS_Model{
    // Function to apply weights to a matrix and a vector
    void apply_weights(std::vector<double>& a, std::vector<double>& b, double weight) {
        for (double& val : a) {
            val *= weight;
        }
        for (double& val : b) {
            val *= weight;
        }
    }

    std::vector<double> generate_weights(int num_days, double lambda) {
        std::vector<double> weights(num_days);
        for (int day = 0; day < num_days; day++) {
            weights[day] = std::exp(-lambda * day);
        }
        return weights;
    }

    std::vector<double> generate_linear_weights(int num_days) {
        std::vector<double> weights(num_days);
        for (int day = 0; day < num_days; day++) {
            weights[day] = static_cast<double>(num_days - day) / num_days;
        }
        return weights;
    }

    // Function to solve the least squares problem using SVD
    int solve_least_squares(std::vector<double>& a, std::vector<double>& b, std::vector<double>& singular_values, double singular_value_threshold, MKL_INT m, MKL_INT n, MKL_INT nrhs, MKL_INT lda, MKL_INT ldb) {
        MKL_INT rank;
        double rcond = singular_value_threshold;
        return LAPACKE_dgelss(LAPACK_ROW_MAJOR, m, n, nrhs, a.data(), lda, b.data(), ldb, singular_values.data(), rcond, &rank);
    }

    int fit() {
        // Define the problem size and create the vectors
        MKL_INT m = 3, n = 2, nrhs = 1, lda = m, ldb = m, info;
        std::vector<std::vector<double>> a_days = {
                {1.0, 2.0, 3.0, 4.0, 5.0, 6.0},
                {7.0, 8.0, 9.0, 10.0, 11.0, 12.0}
        };
        std::vector<std::vector<double>> b_days = {
                {1.0, 2.0, 3.0},
                {4.0, 5.0, 6.0}
        };
        std::vector<double> weights = generate_weights(a_days.size(), 0.1);

        double singular_value_threshold = 1e-10;
        std::vector<double> singular_values(std::min(m, n));

        // Initialize combined A matrix and b vector
        std::vector<double> A_combined(n * n, 0.0);
        std::vector<double> b_combined(n, 0.0);

        // Initialize aTa and atb vectors outside the loop
        std::vector<double> aTa(n * n);
        std::vector<double> atb(n);

        // Loop over each day
        for (size_t day = 0; day < a_days.size(); day++) {
            std::vector<double> a = a_days[day];
            std::vector<double> b = b_days[day];
            double weight = sqrt(weights[day]);

            apply_weights(a, b, weight);

            // Reset aTa and atb vectors
            std::fill(aTa.begin(), aTa.end(), 0.0);
            std::fill(atb.begin(), atb.end(), 0.0);

            // Calculate aT*a and aT*b for the current day
            cblas_dgemm(CblasRowMajor, CblasTrans, CblasNoTrans, n, n, m, 1.0, a.data(), n, a.data(), n, 0.0, aTa.data(), n);
            cblas_dgemv(CblasRowMajor, CblasTrans, m, n, 1.0, a.data(), n, b.data(), 1, 0.0, atb.data(), 1);

            // Add aTa and atb to the combined A matrix and b vector
            cblas_daxpy(n * n, 1.0, aTa.data(), 1, A_combined.data(), 1);
            cblas_daxpy(n, 1.0, atb.data(), 1, b_combined.data(), 1);
        }

        // Solve the least squares problem using the combined A matrix and b vector
        info = solve_least_squares(A_combined, b_combined, singular_values, singular_value_threshold, n, n, nrhs, n, n);

        // Check for success
        if (info > 0) {
            std::cout << "The algorithm failed to compute a least squares solution.\n";
        } else {
            // Print the solution
            std::cout << "The solution is: ";
            for (int i = 0; i < n; i++) {
                std::cout << b_combined[i] << " ";
            }
            std::cout << "\n";
        }
        return 0;
    }

};

#include <vector>
#include <mkl.h>

class WeightedLeastSquaresSolver {
private:
    void apply_weights(std::vector<double>& X, std::vector<double>& y, double weight) {
        for (double& val : X) {
            val *= weight;
        }
        for (double& val : y) {
            val *= weight;
        }
    }

    std::vector<double> generate_weights(int num_days, double lambda) {
        std::vector<double> weights(num_days);
        for (int day = 0; day < num_days; day++) {
            weights[day] = std::exp(-lambda * day);
        }
        return weights;
    }

public:
    std::vector<double> solve(const std::vector<std::vector<double>>& X_days, const std::vector<std::vector<double>>& y_days, double lambda) {
        int num_days = X_days.size();
        int num_indicators = X_days[0].size();
        std::vector<double> weights = generate_weights(num_days, lambda);

        std::vector<double> X_combined(num_days * num_indicators);
        std::vector<double> y_combined(num_days);

        for (int day = 0; day < num_days; day++) {
            std::vector<double> X_d = X_days[day];
            std::vector<double> y_d = y_days[day];
            double weight = weights[day];

            apply_weights(X_d, y_d, weight);

            std::copy(X_d.begin(), X_d.end(), X_combined.begin() + day * num_indicators);
            y_combined[day] = y_d[0];
        }

        MKL_INT m = num_days;
        MKL_INT n = num_indicators;
        MKL_INT nrhs = 1;
        MKL_INT lda = n;
        MKL_INT ldb = m;
        MKL_INT info;

        std::vector<double> singular_values(std::min(m, n));
        double rcond = -1.0; // Use machine precision

        info = LAPACKE_dgelsd(LAPACK_ROW_MAJOR, m, n, nrhs, X_combined.data(), lda, y_combined.data(), ldb, singular_values.data(), rcond, nullptr);

        if (info > 0) {
            std::cout << "The algorithm computing SVD failed to converge.\n";
        }

        return y_combined;
    }
};