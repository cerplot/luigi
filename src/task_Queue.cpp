
class TaskQueue {
private:
    std::queue<std::function<void()>> tasks;
    std::mutex tasksMutex;
    std::condition_variable tasksCondVar;
    bool stop = false;

public:
    void addTask(std::function<void()> task) {
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            if(stop)
                throw std::runtime_error("Enqueue on stopped TaskQueue");
            tasks.emplace(std::move(task));
        }
        tasksCondVar.notify_one();
    }

    std::function<void()> getTask() {
        std::unique_lock<std::mutex> lock(tasksMutex);
        tasksCondVar.wait(lock, [this]{ return stop || !tasks.empty(); });
        if (stop && tasks.empty())
            return nullptr;
        auto task = std::move(tasks.front());
        tasks.pop();
        return task;
    }

    void stopQueue() {
        {
            std::unique_lock<std::mutex> lock(tasksMutex);
            stop = true;
        }
        tasksCondVar.notify_all();
    }
};
