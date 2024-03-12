#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <ctime>
#include <regex>

class DateInterval {
public:
    std::chrono::system_clock::time_point date_a;
    std::chrono::system_clock::time_point date_b;

    DateInterval(std::chrono::system_clock::time_point date_a, std::chrono::system_clock::time_point date_b)
            : date_a(date_a), date_b(date_b) {}

    virtual std::string to_string() = 0;  // Pure virtual function
};

class Date : public DateInterval {
public:
    Date(std::chrono::system_clock::time_point date_a)
            : DateInterval(date_a, date_a + std::chrono::hours(24)) {}

    std::string to_string() override {
        std::time_t date_a_t = std::chrono::system_clock::to_time_t(date_a);
        std::tm date_a_tm = *std::localtime(&date_a_t);
        char date_a_str[11];
        std::strftime(date_a_str, sizeof(date_a_str), "%Y-%m-%d", &date_a_tm);
        return std::string(date_a_str);
    }
};

class Week : public DateInterval {
public:
    Week(std::chrono::system_clock::time_point date_a)
            : DateInterval(date_a, date_a + std::chrono::hours(24*7)) {}

    std::string to_string() override {
        // Implement the conversion to string
    }
};

class Month : public DateInterval {
public:
    Month(std::chrono::system_clock::time_point date_a)
            : DateInterval(date_a, date_a + std::chrono::hours(24*30)) {}  // Approximation

    std::string to_string() override {
        // Implement the conversion to string
    }
};

class Year : public DateInterval {
public:
    Year(std::chrono::system_clock::time_point date_a)
            : DateInterval(date_a, date_a + std::chrono::hours(24*365)) {}  // Approximation

    std::string to_string() override {
        // Implement the conversion to string
    }
};

class Custom : public DateInterval {
public:
    Custom(std::chrono::system_clock::time_point date_a, std::chrono::system_clock::time_point date_b)
            : DateInterval(date_a, date_b) {}

    std::string to_string() override {
        // Implement the conversion to string
    }
};
