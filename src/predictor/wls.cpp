#include <iostream>
#include <vector>
#include <mkl.h>
#include <unordered_map>
#include <cmath>

std::pair<std::vector<double>, std::vector<double>> calculateTarget(
        const std::vector<double>& prices, double smoothingFactor, double delta) {
    std::vector<double> shortTermObjectiveSeries(prices.size(), 0.0);
    std::vector<double> longTermObjectiveSeries(prices.size(), 0.0);
    double smoothedChange = 0.0;
    double objective = 0.0;
    for (int i = static_cast<int>(prices.size()) - 1; i >= 0; --i) {
        int j = std::min(i + static_cast<int>(delta), static_cast<int>(prices.size()) - 1);
        shortTermObjectiveSeries[i] = prices[j] - prices[i];
        if (i + delta + 1 < prices.size()) {
            double priceChange = prices[i + static_cast<int>(delta) + 1] - prices[i + static_cast<int>(delta)];
            smoothedChange = smoothingFactor * priceChange + (1 - smoothingFactor) * smoothedChange;
            objective += smoothedChange;
            longTermObjectiveSeries[i] = objective;
        }
    }
    return {shortTermObjectiveSeries, longTermObjectiveSeries};
}

class Solver {
private:
    int Num;
    double eps = 1e-10;
    std::vector<double> d;
    std::vector<int> m;
    std::vector<double> U;
    std::vector<double> eig_value;
    std::vector<double> eig_vector;

    void computeEigenvaluesAndVectors(std::vector<double>& A) {
        MKL_INT info;
        char jobz = 'V'; // Compute eigenvalues and eigenvectors.
        char uplo = 'U'; // Upper triangle of A is stored.
        MKL_INT n = sqrt(A.size());
        MKL_INT lda = n;
        std::vector<double> w(n);
        info = LAPACKE_dsyev(LAPACK_ROW_MAJOR, jobz, uplo, n, A.data(), lda, w.data());

        if (info != 0) {
            throw std::runtime_error("Failed to compute eigenvalues and eigenvectors");
        } else {
            eig_value = w;
            eig_vector = A;
        }
    }

public:
    void left_solver(std::vector<double>& A) {
        if (A.size() == 0 || sqrt(A.size()) * sqrt(A.size()) != A.size()) {
            throw std::invalid_argument("Input matrix A must be square");
        }

        Num = sqrt(A.size());
        d.resize(Num);
        for (int i = 0; i < Num; i++) {
            d[i] = 1.0 / sqrt(A[i * Num + i]);
            if (A[i * Num + i] >= eps) {
                m.push_back(i);
            }
        }

        int n = m.size();
        U.resize(n * n);
        for (int i = 0; i < n; i++) {
            for (int j = i; j < n; j++) {
                U[i * n + j] = d[m[i]] * A[m[i] * Num + m[j]] * d[m[j]];
            }
        }
        computeEigenvaluesAndVectors(U);
        int small = 0;
        double tol = 0.01;
        while (small < n && eig_value[small] < tol) {
            small++;
        }

        eig_value = std::vector<double>(eig_value.begin() + small, eig_value.end());
        eig_vector = std::vector<double>(eig_vector.begin() + small * n, eig_vector.end());
    }

    std::vector<double> solve(std::vector<double>& b) {
        if (b.size() != Num) {
            throw std::invalid_argument("Size of vector b must be equal to the size of matrix A");
        }

        int ns = eig_value.size();
        if (ns == 0) {
            return std::vector<double>(Num, 0.0);
        }

        std::vector<double> temp(ns);
        for (int i = 0; i < ns; i++) {
            double sum = 0.0;
            for (int j = 0; j < m.size(); j++) {
                sum += eig_vector[j * ns + i] * d[m[j]] * b[m[j]];
            }
            temp[i] = sum / eig_value[i];
        }

        std::vector<double> result(Num);
        for (int i = 0; i < m.size(); i++) {
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
        cblas_dscal(a.size(), weight, a.data(), 1);
        cblas_dscal(b.size(), weight, b.data(), 1);
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