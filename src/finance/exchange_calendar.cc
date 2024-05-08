#include <vector>
#include <chrono>
#include <iostream>
#include <algorithm>

enum DaysOfWeek {
    MONDAY,
    TUESDAY,
    WEDNESDAY,
    THURSDAY,
    FRIDAY,
    SATURDAY,
    SUNDAY
};


typedef std::chrono::system_clock::time_point Timestamp;

// Equivalent of Python's pd.DatetimeIndex
typedef std::vector<Timestamp> DatetimeIndex;

DatetimeIndex selection(DatetimeIndex arr, Timestamp start, Timestamp end) {
    DatetimeIndex result;
    std::copy_if(arr.begin(), arr.end(), std::back_inserter(result),
            [start, end](Timestamp t) { return start <= t && t < end; });
    return result;
}

class Deprecate {
public:
    Deprecate(std::string deprecated_release, std::string message = "")
            : deprecated_release("release " + deprecated_release), message(message) {}

    template <typename Func>
    auto operator()(Func f) {
        std::cout << "Warning: " << f << " was deprecated in " << deprecated_release
                  << " and will be removed in a future release. " << message << std::endl;
        return f;
    }

private:
    std::string deprecated_release;
    std::string message;
};
// number_of_days_to_fitt
// number_of_days_to_test