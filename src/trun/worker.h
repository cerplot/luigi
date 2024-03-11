#pragma once

#include <string>
#include <unordered_map>
#include <vector>
#include <queue>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <atomic>

class Scheduler; // Forward declaration of Scheduler class

class Worker {
public:
    Worker(Scheduler* scheduler = nullptr, std::string worker_id = "", int worker_processes = 1, bool assistant = false);

    // Declare other methods here based on the Python Worker class

private:
    int worker_processes_;
    std::unordered_map<std::string, int> worker_info_;
    // WorkerConfig config_; // You would need to create a WorkerConfig class to hold the configuration
    std::string id_;
    Scheduler* scheduler_;
    bool assistant_;
    std::atomic<bool> stop_requesting_work_;
    std::string host_;
    std::unordered_map<std::string, int> scheduled_steps_;
    std::unordered_map<std::string, int> suspended_steps_;
    std::unordered_map<std::string, int> batch_running_steps_;
    std::unordered_set<std::string> batch_families_sent_;
    std::string first_step_;
    bool add_succeeded_;
    bool run_succeeded_;
    std::unordered_map<std::string, int> unfulfilled_counts_;
    // std::queue<int> step_result_queue_; // You would need to implement a thread-safe queue
    std::unordered_map<std::string, int> running_steps_;
    std::chrono::system_clock::time_point idle_since_;
    std::unordered_map<std::string, bool> step_completion_cache_;
    std::vector<std::string> add_step_history_;
    std::vector<std::string> get_work_response_history_;
    std::mutex mtx_;
    std::condition_variable cv_;
    KeepAliveThread* keepAliveThread;
};