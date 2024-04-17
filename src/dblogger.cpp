#include <sqlite3.h>
#include <string>
#include <iostream>
#include <vector>
#include <atomic>
#include <thread>
#include <unistd.h>
#include <sys/syscall.h>

template<typename T, typename... A>
inline auto createAndStartThread(int core_id, const std::string &name, T &&func, A &&... args) noexcept {
    std::atomic<bool> running(false), failed(false);
    auto thread_body = [&] {
        if (core_id >= 0 && !setThreadCore(core_id)) {
            std::cerr << "Failed to set core affinity for " << name << " " << pthread_self() << " to " << core_id << std::endl;
            failed = true;
            return;
        }
        std::cout << "Set core affinity for " << name << " " << pthread_self() << " to " << core_id << std::endl;
        running = true;
        std::forward<T>(func)((std::forward<A>(args))...);
    };
    auto t = new std::thread(thread_body);
    while (!running && !failed) {
        using namespace std::literals::chrono_literals;
        std::this_thread::sleep_for(1s);
    }
    if (failed) {
        t->join();
        delete t;
        t = nullptr;
    }
    return t;
}

template<typename T>
class LFQueue final {
public:
    LFQueue(std::size_t num_elems) : store_(num_elems, T()) {}

    auto getNextToWriteTo() noexcept {
        return &store_[next_write_index_];
    }

    auto updateWriteIndex() noexcept {
        next_write_index_ = (next_write_index_ + 1) % store_.size();
        num_elements_++;
    }

    auto getNextToRead() const noexcept -> const T * {
        return (size() ? &store_[next_read_index_] : nullptr);
    }

    auto updateReadIndex() noexcept {
        next_read_index_ = (next_read_index_ + 1) % store_.size();
        ASSERT(num_elements_ != 0, "Read an invalid element in:" + std::to_string(pthread_self()));
        num_elements_--;
    }

    auto size() const noexcept {
        return num_elements_.load();
    }

    LFQueue() = delete;
    LFQueue(const LFQueue &) = delete;
    LFQueue(const LFQueue &&) = delete;
    LFQueue &operator=(const LFQueue &) = delete;
    LFQueue &operator=(const LFQueue &&) = delete;

private:
    std::vector<T> store_;
    std::atomic<size_t> next_write_index_ = {0};
    std::atomic<size_t> next_read_index_ = {0};
    std::atomic<size_t> num_elements_ = {0};
};

class Logger {
public:
    Logger() {
        sqlite3_open("log.db", &db);
        sqlite3_prepare_v2(db, "INSERT INTO log (message) VALUES (?);", -1, &stmt, NULL);
    }

    ~Logger() {
        sqlite3_finalize(stmt);
        sqlite3_close(db);
    }

    template<typename T, typename... A>
    void logDb(const char *s, const T &value, A... args) noexcept {
        while (*s) {
            if (*s == '%') {
                if (*(s + 1) == '%') {
                    ++s;
                } else {
                    pushValue(value);
                    logDb(s + 1, args...);
                    return;
                }
            }
            pushValue(*s++);
        }
    }

    void logDb(const char *s) noexcept {
        while (*s) {
            if (*s == '%') {
                if (*(s + 1) == '%') {
                    ++s;
                } else {
                    return;
                }
            }
            pushValue(*s++);
        }
    }

    void pushValue(const std::string &value) {
        sqlite3_bind_text(stmt, 1, value.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_step(stmt);
        sqlite3_clear_bindings(stmt);
        sqlite3_reset(stmt);
    }

    void pushValue(int value) {
        std::string str_value = std::to_string(value);
        pushValue(str_value);
    }

    void pushValue(double value) {
        std::string str_value = std::to_string(value);
        pushValue(str_value);
    }

    void pushValue(char value) {
        std::string str_value(1, value);
        pushValue(str_value);
    }

private:
    sqlite3 *db;
    sqlite3_stmt *stmt;
};
