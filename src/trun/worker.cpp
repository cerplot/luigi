
#include <thread>
#include <map>
#include <string>
#include <vector>
#include <functional>
#include <chrono>
#include <mutex>
#include <string>
#include "scheduler.h"

const double WAIT_INTERVAL_EPS = 0.00001;

bool is_external(const Step& step) {
    return step.run == nullptr;  // Assuming run is a function pointer
}

std::map<std::string, int> get_retry_policy_dict(const Step& step) {
    RetryPolicy retryPolicy(step.retry_count, step.disable_hard_timeout, step.disable_window);
    return retryPolicy.asDict();  // Assuming asDict is a method in RetryPolicy class
}

class StepException : public std::exception {
private:
    std::string message_;

public:
    explicit StepException(const std::string& message) : message_(message) {}

    const char* what() const noexcept override {
        return message_.c_str();
    }
};

struct GetWorkResponse {
    std::string step_id;
    int running_steps;
    int n_pending_steps;
    int n_unique_pending;
    int n_pending_last_scheduled;
    std::string worker_state;
};


class StepProcess {
private:
    Step step;
    std::string worker_id;
    std::queue<Result> result_queue;
    StatusReporter status_reporter;
    bool use_multiprocessing;
    int worker_timeout;
    int timeout_time;
    bool check_unfulfilled_deps;
    bool check_complete_on_run;
    std::map<std::string, bool> step_completion_cache;
    std::thread worker_thread;
    std::mutex mtx;

public:
    StepProcess(Step step, std::string worker_id, std::queue<Result> result_queue, StatusReporter status_reporter,
                bool use_multiprocessing, int worker_timeout, bool check_unfulfilled_deps,
                bool check_complete_on_run, std::map<std::string, bool> step_completion_cache)
            : step(step), worker_id(worker_id), result_queue(result_queue), status_reporter(status_reporter),
              use_multiprocessing(use_multiprocessing), worker_timeout(worker_timeout),
              check_unfulfilled_deps(check_unfulfilled_deps), check_complete_on_run(check_complete_on_run),
              step_completion_cache(step_completion_cache) {
        // Start the worker thread
        worker_thread = std::thread(&StepProcess::run, this);
    }

    std::optional<std::vector<Dependency>> StepProcess::_run_get_new_deps() {
        std::function<std::optional<DynamicRequirements>()> step_gen = step.run();

        DynamicRequirements requires;
        while (true) {
            requires = step_gen();
            if (!requires) {
                return std::nullopt;
            }

            if (!requires.complete(check_complete)) {
                std::vector<Dependency> new_deps;
                for (const auto& req : requires.flat_requirements) {
                    new_deps.push_back({req.step_module, req.step_family, req.to_str_params()});
                }
                return new_deps;
            }
        }
    }

    ~StepProcess() {
        // Join the worker thread on destruction
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }

    void terminate() {
        // Implement the logic of the terminate method here
    }
};


void StepProcess::run() {
    std::cout << "[pid " << getpid() << "] Worker " << worker_id << " running " << step << std::endl;

    if (use_multiprocessing) {
        // Need to have different random seeds if running in separate processes
        int processID = getpid();
        double currentTime = std::time(0);
        std::srand(processID * currentTime);
    }

    Status status = FAILED;
    std::string expl = "";
    std::vector<std::string> missing;
    std::vector<std::string> new_deps;

    try {
        // Verify that all the steps are fulfilled! For external steps we
        // don't care about unfulfilled dependencies, because we are just
        // checking completeness of self.step so outputs of dependencies are
        // irrelevant.
        if (check_unfulfilled_deps && !is_external(step)) {
            missing = {};
            for (auto dep : step.deps()) {
                if (!check_complete(dep)) {
                    std::vector<std::string> nonexistent_outputs = {}; // Fill this with your logic
                    if (!nonexistent_outputs.empty()) {
                        missing.push_back(dep.step_id + " (" + join(nonexistent_outputs, ", ") + ")");
                    } else {
                        missing.push_back(dep.step_id);
                    }
                }
            }
            if (!missing.empty()) {
                std::string deps = missing.size() == 1 ? "dependency" : "dependencies";
                throw std::runtime_error("Unfulfilled " + deps + " at run time: " + join(missing, ", "));
            }
        }
        step.trigger_event(Event::START, step);
        double t0 = std::time(0);
        status = UNKNOWN;

        if (is_external(step)) {
            // External step
            if (check_complete(step)) {
                status = DONE;
            } else {
                status = FAILED;
                expl = "Step is an external data dependency and data does not exist (yet?).";
            }
        } else {
            // Forward attributes
            this->forward_attributes();

            // Run and get new dependencies
            std::vector<std::string> new_deps = this->run_get_new_deps();

            if (new_deps.empty()) {
                if (!this->check_complete_on_run) {
                    // Update the cache
                    if (this->step_completion_cache != nullptr) {
                        (*this->step_completion_cache)[this->step.step_id] = true;
                    }
                    status = DONE;
                } else if (this->check_complete(this->step)) {
                    status = DONE;
                } else {
                    throw std::runtime_error("Step finished running, but complete() is still returning false.");
                }
            } else {
                status = PENDING;
            }
        }

        if (!new_deps.empty()) {
            std::cout << "[pid " << getpid() << "] Worker " << worker_id << " new requirements " << step << std::endl;
        } else if (status == DONE) {
            step.trigger_event(Event::PROCESSING_TIME, step, std::time(0) - t0);
            expl = step.on_success();
            std::cout << "[pid " << getpid() << "] Worker " << worker_id << " done " << step << std::endl;
            step.trigger_event(Event::SUCCESS, step);
        }
    } catch (std::exception& ex) {
        status = FAILED;
        expl = handle_run_exception(ex);
    }
    result_queue.push(std::make_tuple(step.step_id, status, expl, missing, new_deps));

}

std::string StepProcess::_handle_run_exception(std::exception& ex) {
    std::cerr << "[pid " << getpid() << "] Worker " << worker_id << " failed " << step << std::endl;
    step.trigger_event(Event::FAILURE, step, ex);
    return step.on_failure(ex);
}


class Scheduler; // Forward declaration

class StepStatusReporter {
public:
    StepStatusReporter(Scheduler* scheduler, std::string step_id, std::string worker_id, std::string scheduler_messages)
            : _scheduler(scheduler), _step_id(step_id), _worker_id(worker_id), scheduler_messages(scheduler_messages) {}

    void update_tracking_url(std::string tracking_url) {
        _scheduler->add_step(_step_id, _worker_id, "RUNNING", tracking_url);
    }

    void update_status_message(std::string message) {
        _scheduler->set_step_status_message(_step_id, message);
    }

    void update_progress_percentage(float percentage) {
        _scheduler->set_step_progress_percentage(_step_id, percentage);
    }

    void decrease_running_resources(int decrease_resources) {
        _scheduler->decrease_running_step_resources(_step_id, decrease_resources);
    }

private:
    Scheduler* _scheduler;
    std::string _step_id;
    std::string _worker_id;
    std::string scheduler_messages;
};


class SchedulerMessage {
public:
    SchedulerMessage(Scheduler* scheduler, std::string step_id, std::string message_id, std::string content, std::unordered_map<std::string, std::string> payload)
            : _scheduler(scheduler), _step_id(step_id), _message_id(message_id), content(content), payload(payload) {}

    std::string to_string() {
        return content;
    }

    bool operator==(const SchedulerMessage& other) {
        return content == other.content;
    }

    void respond(std::string response) {
        _scheduler->add_scheduler_message_response(_step_id, _message_id, response);
    }

private:
    Scheduler* _scheduler;
    std::string _step_id;
    std::string _message_id;
    std::string content;
    std::unordered_map<std::string, std::string> payload;
};

class SingleProcessPool {
public:
    template<typename Func, typename... Args>
    auto apply_async(Func&& func, Args&&... args) -> decltype(func(args...)) {
        return func(std::forward<Args>(args)...);
    }

    void close() {
        // No equivalent operation in C++
    }

    void join() {
        // No equivalent operation in C++
    }
};


class DequeQueue {
public:
    void put(int obj) {
        deque_.push_back(obj);
    }

    int get() {
        if (deque_.empty()) {
            throw std::out_of_range("Queue is empty");
        }
        int value = deque_.back();
        deque_.pop_back();
        return value;
    }

private:
    std::deque<int> deque_;
};

class AsyncCompletionException : public std::exception {
public:
    explicit AsyncCompletionException(const std::string& trace) : trace_(trace) {}

    const char* what() const noexcept override {
            return trace_.c_str();
    }

private:
    std::string trace_;
};


class TracebackWrapper {
public:
    explicit TracebackWrapper(const std::string& trace) : trace_(trace) {}

    std::string getTrace() const {
        return trace_;
    }

private:
    std::string trace_;
};


bool check_complete_cached(Step& step, std::unordered_map<std::string, bool>* completion_cache = nullptr) {
    std::string cache_key = step.step_id;

    // Check if cached and complete
    if (completion_cache != nullptr && (*completion_cache)[cache_key]) {
        return true;
    }

    // (Re-)check the status
    bool is_complete = step.complete();

    // Tell the cache when complete
    if (completion_cache != nullptr && is_complete) {
        (*completion_cache)[cache_key] = is_complete;
    }

    return is_complete;
}
void check_complete(Step& step, std::queue<std::pair<Step, bool>>& out_queue, std::unordered_map<std::string, bool>* completion_cache = nullptr) {
    std::cout << "Checking if " << step.step_id << " is complete" << std::endl;
    try {
        bool is_complete = check_complete_cached(step, completion_cache);
        out_queue.push({step, is_complete});
    } catch (std::exception& e) {
        TracebackWrapper traceback(e.what());
        // Assuming out_queue can hold a pair of Step and TracebackWrapper
        out_queue.push({step, traceback});
    }
}


class KeepAliveThread {
public:
    KeepAliveThread(Scheduler& scheduler, std::string worker_id, int ping_interval)
            : scheduler_(scheduler), worker_id_(worker_id), ping_interval_(ping_interval), should_stop_(false) {}

    void stop() {
        should_stop_ = true;
        if (thread_.joinable()) {
            thread_.join();
        }
    }

    void run() {
        thread_ = std::thread([this]() {
            while (!should_stop_) {
                std::this_thread::sleep_for(std::chrono::seconds(ping_interval_));
                if (should_stop_) {
                    std::cout << "Worker " << worker_id_ << " was stopped. Shutting down Keep-Alive thread\n";
                    break;
                }
                try {
                    std::string response = scheduler_.ping(worker_id_);
                    // Handle RPC messages
                    // ...
                } catch (...) {
                    std::cout << "Failed pinging scheduler\n";
                }
            }
        });
    }

private:
    Scheduler& scheduler_;
    std::string worker_id_;
    int ping_interval_;
    std::atomic<bool> should_stop_;
    std::thread thread_;
};


class RpcMessageCallback {
public:
    // Store the functions marked as RPC message callbacks
    static std::unordered_map<std::string, std::function<void()>> callbacks;

    // Function to mark a function as an RPC message callback
    static void mark(std::string name, std::function<void()> fn) {
        callbacks[name] = fn;
    }

    // Function to check if a function is an RPC message callback
    static bool isRpcMessageCallback(std::string name) {
        return callbacks.find(name) != callbacks.end();
    }
};

// Initialize the static member
std::unordered_map<std::string, std::function<void()>> RpcMessageCallback::callbacks;


Worker::Worker(Scheduler* scheduler = nullptr, std::string worker_id = "", int worker_processes = 1, bool assistant = false)
: worker_processes_(worker_processes),
id_(worker_id),
scheduler_(scheduler ? scheduler : new Scheduler()),
assistant_(assistant),
stop_requesting_work_(false),
add_succeeded_(true),
run_succeeded_(true) {
    // Generate worker info
    worker_info_ = generateWorkerInfo();

    // Config setup
    // You would need to create a WorkerConfig class to hold the configuration
    // config_ = WorkerConfig(kwargs...);

    // If worker_id is not provided, generate it
    if (worker_id_.empty()) {
        // worker_id_ = config_.id.empty() ? generateWorkerId(worker_info_) : config_.id;
    }

    // Assertions
    // assert(config_.wait_interval >= _WAIT_INTERVAL_EPS);
    // assert(config_.wait_jitter >= 0.0);

    // Initialize other member variables
    host_ = "localhost"; // Replace with actual host name retrieval
    first_step_ = "";
    idle_since_ = std::chrono::system_clock::now();

    // Initialize containers
    scheduled_steps_ = {};
    suspended_steps_ = {};
    batch_running_steps_ = {};
    batch_families_sent_ = {};
    unfulfilled_counts_ = {};
    step_result_queue_ = std::queue<int>();
    running_steps_ = {};
    step_completion_cache_ = {};
    add_step_history_ = {};
    get_work_response_history_ = {};
}

void Worker::addStep(std::map<std::string, std::string> kwargs) {
    std::string step_id = kwargs["step_id"];
    std::string status = kwargs["status"];
    bool runnable = std::stoi(kwargs["runnable"]);

    auto it = scheduled_steps_.find(step_id);
    if (it != scheduled_steps_.end()) {
        addStepHistory_.push_back(std::make_tuple(it->second, status, runnable));
        kwargs["owners"] = it->second.ownerList();
    }

    auto it2 = batch_running_steps_.find(step_id);
    if (it2 != batch_running_steps_.end()) {
        for (auto& batch_step : it2->second) {
            addStepHistory_.push_back(std::make_tuple(batch_step, status, true));
        }
        batch_running_steps_.erase(it2);
    }

    if (it != scheduled_steps_.end() && kwargs.find("params") != kwargs.end()) {
        kwargs["param_visibilities"] = it->second.getParamVisibilities();
    }

    scheduler_->addStep(kwargs);

    std::cout << "Informed scheduler that step " << step_id << " has status " << status << std::endl;
}

Worker* Worker::enter() {
    // Start the KeepAliveThread
    keepAliveThread = new KeepAliveThread(scheduler, id, config.pingInterval, handleRPCMessage);
    keepAliveThread->setDaemon(true);
    keepAliveThread->start();
    return this;
}

void Worker::exit() {
    // Stop the KeepAliveThread
    keepAliveThread->stop();
    keepAliveThread->join();
    delete keepAliveThread;

    // Terminate running steps
    for (auto& step : runningSteps) {
        if (step->isAlive()) {
            step->terminate();
        }
    }

    // Close the step result queue
    stepResultQueue.close();
}

std::vector<std::tuple<std::string, std::string>> Worker::generateWorkerInfo() {
    std::vector<std::tuple<std::string, std::string>> args;
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 9999999999);
    args.push_back(std::make_tuple("salt", std::to_string(dis(gen))));
    args.push_back(std::make_tuple("workers", std::to_string(workerProcesses)));

    try {
        char hostname[1024];
        gethostname(hostname, 1024);
        args.push_back(std::make_tuple("host", std::string(hostname)));
    } catch (...) {
        // pass
    }

    try {
        struct passwd *pw;
        uid_t uid;

        uid = geteuid();
        pw = getpwuid(uid);
        if (pw) {
            args.push_back(std::make_tuple("username", std::string(pw->pw_name)));
        }
    } catch (...) {
        // pass
    }

    try {
        args.push_back(std::make_tuple("pid", std::to_string(getpid())));
    } catch (...) {
        // pass
    }

    try {
        char* sudo_user = std::getenv("SUDO_USER");
        if (sudo_user) {
            args.push_back(std::make_tuple("sudo_user", std::string(sudo_user)));
        }
    } catch (...) {
        // pass
    }

    return args;
}

std::string Worker::generateWorkerId(const std::vector<std::pair<std::string, std::string>>& workerInfo) {
    std::string workerInfoStr;
    for (const auto& info : workerInfo) {
        if (!workerInfoStr.empty()) {
            workerInfoStr += ", ";
        }
        workerInfoStr += info.first + "=" + info.second;
    }
    return "Worker(" + workerInfoStr + ")";
}

void Worker::validateStep(Step* step) {
    if (step == nullptr) {
        throw std::runtime_error("Cannot schedule non-step");
    }

    if (!step->isInitialized()) {
        throw std::runtime_error("Step of class " + typeid(*step).name() + " not initialized. Did you override the constructor and forget to call the base class constructor?");
    }
}
void Worker::logCompleteError(std::string step, std::string tb) {
    std::string log_msg = "Will not run " + step + " or any dependencies due to error in complete() method:\n" + tb;
    std::cerr << log_msg << std::endl;
}
void Worker::logDependencyError(std::string step, std::string tb) {
    std::string log_msg = "Will not run " + step + " or any dependencies due to error in deps() method:\n" + tb;
    std::cerr << log_msg << std::endl;
}

void Worker::logUnexpectedError(std::string step) {
    std::cerr << "Trun unexpected framework error while scheduling " << step << std::endl;
}


void Worker::announceSchedulingFailure(Step* step, std::string expl) {
    try {
        this->scheduler->announceSchedulingFailure(
                this->id,
                step->toString(),
                step->getStepFamily(),
                step->toStrParams(true),
                expl,
                step->ownerList()
        );
    } catch (std::exception& e) {
        std::string formatted_traceback = e.what();
        this->emailUnexpectedError(step, formatted_traceback);
        throw;
    }
}

void Worker::emailCompleteError(Step* step, std::string formatted_traceback) {
    this->announceSchedulingFailure(step, formatted_traceback);
    if (this->config.send_failure_email) {
        std::string subject = "Trun: " + step->toString() + " failed scheduling. Host: " + this->host;
        std::string headline = "Will not run " + step->toString() + " or any dependencies due to error in complete() method";
        this->emailError(step, formatted_traceback, subject, headline);
    }
}

void Worker::emailDependencyError(Step* step, std::string formatted_traceback) {
    this->announceSchedulingFailure(step, formatted_traceback);
    if (this->config.send_failure_email) {
        std::string subject = "Trun: " + step->toString() + " failed scheduling. Host: " + this->host;
        std::string headline = "Will not run " + step->toString() + " or any dependencies due to error in deps() method";
        this->emailError(step, formatted_traceback, subject, headline);
    }
}

void Worker::emailUnexpectedError(Step* step, std::string formatted_traceback) {
    std::string subject = "Trun: Framework error while scheduling " + step->toString() + ". Host: " + this->host;
    std::string headline = "Trun framework error";
    this->emailError(step, formatted_traceback, subject, headline);
}

void Worker::emailStepFailure(Step* step, std::string formatted_traceback) {
    if (this->config.send_failure_email) {
        std::string subject = "Trun: " + step->toString() + " FAILED. Host: " + this->host;
        std::string headline = "A step failed when running. Most likely run() raised an exception.";
        this->emailError(step, formatted_traceback, subject, headline);
    }
}
void Worker::emailError(Step* step, std::string formatted_traceback, std::string subject, std::string headline) {
    std::string formatted_subject = format(subject, step->toString(), this->host);
    std::string formatted_headline = format(headline, step->toString(), this->host);
    std::string command = formatCommandLine(std::vector<std::string> argv);
    std::string message = Notifications::formatStepError(formatted_headline, step, command, formatted_traceback);
    Notifications::sendErrorEmail(formatted_subject, message, step->getOwnerEmail());
}

std::string Worker::format(const std::string& format, const std::string& step, const std::string& host) {
    std::stringstream ss;
    ss << format;
    ss << " Step: " << step;
    ss << " Host: " << host;
    return ss.str();
}

std::string Worker::formatCommandLine(std::vector<std::string> argv) {
    std::stringstream ss;
    for(const auto& arg : argv) {
        ss << arg << " ";
    }
    return ss.str();
}

void Worker::handleStepLoadError(std::exception& exception, std::vector<std::string> step_ids) {
    std::stringstream ss;
    for(const auto& id : step_ids) {
        ss << id << ",";
    }
    std::string msg = "Cannot find step(s) sent by scheduler: " + ss.str();
    std::cerr << msg << std::endl; // Logging the exception message

    std::string subject = "Trun: " + msg;
    std::string error_message = exception.what(); // Assuming notifications.wrap_traceback is equivalent to exception.what()

    for(const auto& step_id : step_ids) {
        this->addStep(
                this->id,
                step_id,
                FAILED,
                false,
                error_message
        );
    }
    Notifications::sendErrorEmail(subject, error_message); // Assuming Notifications::sendErrorEmail is equivalent to notifications.send_error_email
}

bool Worker::add(Step* step, bool multiprocess = false, int processes = 0) {
    if (firstStep.empty() && step->hasStepId()) {
        firstStep = step->getStepId();
    }
    addSucceeded = true;

    validateStep(step);
    stepQueue.push(std::make_pair(step, checkComplete(step)));

    try {
        while (!stepQueue.empty()) {
            auto current = stepQueue.front();
            stepQueue.pop();
            Step* item = current.first;
            bool isComplete = current.second;

            for (auto next : add(item, isComplete)) {
                if (seenSteps.find(next->getStepId()) == seenSteps.end()) {
                    validateStep(next);
                    seenSteps.insert(next->getStepId());
                    if (multiprocess) {
                        futures.push_back(std::async(std::launch::async, &Worker::checkComplete, this, next));
                    } else {
                        stepQueue.push(std::make_pair(next, checkComplete(next)));
                    }
                }
            }
        }

        if (multiprocess) {
            for (auto &future : futures) {
                future.get();
            }
        }
    } catch (std::exception& ex) {
        addSucceeded = false;
        logUnexpectedError(step);
        emailUnexpectedError(step, ex.what());
        throw;
    }

    return addSucceeded;
}

void Worker::addStepBatcher(Step* step) {
    std::string family = step->getStepFamily();
    if (batchFamiliesSent.find(family) == batchFamiliesSent.end()) {
        std::string stepClass = typeid(*step).name();
        std::vector<std::string> batchParamNames = step->batchParamNames();
        if (!batchParamNames.empty()) {
            scheduler.addStepBatcher(
                    id,
                    family,
                    batchParamNames,
                    step->getMaxBatchSize()
            );
        }
        batchFamiliesSent.insert(family);
    }
}

std::vector<Step*> Worker::add(Step* step, bool isComplete) {
    if (this->_config.step_limit != nullptr && this->_scheduled_steps.size() >= this->_config.step_limit) {
        // logger.warning('Will not run %s or any dependencies due to exceeded step-limit of %d', step, this->_config.step_limit);
        deps = nullptr;
        status = UNKNOWN;
        runnable = false;
    } else {
        std::string formatted_traceback = "";
        try {
            this->_check_complete_value(is_complete);
        } catch (AsyncCompletionException& ex) {
            formatted_traceback = ex.trace;
        } catch (...) {
            formatted_traceback = "Some exception occurred"; // replace with actual traceback
        }

        if (formatted_traceback != "") {
            this->add_succeeded = false;
            this->_log_complete_error(step, formatted_traceback);
            step->trigger_event(Event::DEPENDENCY_MISSING, step);
            this->_email_complete_error(step, formatted_traceback);
            deps = nullptr;
            status = UNKNOWN;
            runnable = false;
        } else if (is_complete) {
            deps = nullptr;
            status = DONE;
            runnable = false;
            step->trigger_event(Event::DEPENDENCY_PRESENT, step);
        } else if (_is_external(step)) {
            deps = nullptr;
            status = PENDING;
            runnable = this->_config.retry_external_steps;
            step->trigger_event(Event::DEPENDENCY_MISSING, step);
            // logger.warning('Data for %s does not exist (yet?). The step is an ' 'external data dependency, so it cannot be run from' ' this trun process.', step);
        } else {
            try {
                deps = step->deps();
                this->_add_step_batcher(step);
            } catch (std::exception& ex) {
                formatted_traceback = "Some exception occurred"; // replace with actual traceback
                this->add_succeeded = false;
                this->_log_dependency_error(step, formatted_traceback);
                step->trigger_event(Event::BROKEN_STEP, step, ex);
                this->_email_dependency_error(step, formatted_traceback);
                deps = nullptr;
                status = UNKNOWN;
                runnable = false;
            } else {
                status = PENDING;
                runnable = true;
            }
        }

        if (step->disabled) {
            status = DISABLED;
        }

        std::vector<Step*> deps = step->deps();
        if (!deps.empty()) {
            std::vector<Dependency*> additionalSteps;
            for (Step* d : deps) {
                validateDependency(d);
                step.triggerEvent(Event::DEPENDENCY_DISCOVERED, step, d);
                additionalSteps.push_back(d);
            }

            std::vector<std::string> transformedDeps;
            std::transform(deps.begin(), deps.end(), std::back_inserter(transformedDeps),
                           [](const Dependency& d) { return d.getStepId(); });
            deps = transformedDeps;
        }

        scheduledSteps[step->stepId] = step;
        addStep(worker, step_id, status, deps, runnable, priority, resources, params, family, module, batchable, retry_policy_dict, accepts_messages)
    }
}

void Worker::_validate_dependency(Dependency* dependency) {
    if (dynamic_cast<Target*>(dependency)) {
        throw std::runtime_error("requires() can not return Target objects. Wrap it in an ExternalStep class");
    } else if (!dynamic_cast<Step*>(dependency)) {
        throw std::runtime_error("requires() must return Step objects but " + typeid(dependency).name() + " is a " + typeid(*dependency).name());
    }
}

void Worker::_check_complete_value(bool is_complete) {
    if (is_complete != true && is_complete != false) {
        if (dynamic_cast<TracebackWrapper*>(is_complete)) {
            throw AsyncCompletionException(is_complete->trace);
        } else {
            throw std::runtime_error("Return value of Step::complete() must be boolean (was " + typeid(is_complete).name() + ")");
        }
    }
}
void Worker::_add_worker() {
    this->_worker_info.push_back(std::make_pair("first_step", this->_first_step));
    this->_scheduler.add_worker(this->_id, this->_worker_info);
}

void Worker::_log_remote_steps(GetWorkResponse get_work_response) {
    std::cout << "Done" << std::endl;
    std::cout << "There are no more steps to run at this time" << std::endl;
    if (!get_work_response.running_steps.empty()) {
        for (auto const& r : get_work_response.running_steps) {
            std::cout << r.step_id << " is currently run by worker " << r.worker << std::endl;
        }
    } else if (get_work_response.n_pending_steps > 0) {
        std::cout << "There are " << get_work_response.n_pending_steps << " pending steps possibly being run by other workers" << std::endl;
        if (get_work_response.n_unique_pending > 0) {
            std::cout << "There are " << get_work_response.n_unique_pending << " pending steps unique to this worker" << std::endl;
        }
        if (get_work_response.n_pending_last_scheduled > 0) {
            std::cout << "There are " << get_work_response.n_pending_last_scheduled << " pending steps last scheduled by this worker" << std::endl;
        }
    }
}

std::string Worker::_get_work_step_id(GetWorkResponse get_work_response) {
    if (get_work_response.count("step_id") > 0) {
        return get_work_response["step_id"];
    } else if (get_work_response.count("batch_id") > 0) {
        try {
            Step step = load_step(
                    get_work_response["step_module"],
                    get_work_response["step_family"],
                    get_work_response["step_params"]
            );
            this->_scheduler.add_step(
                    this->_id,
                    step.step_id,
                    get_work_response["step_module"],
                    get_work_response["step_family"],
                    step.to_str_params(),
                    "RUNNING",
                    get_work_response["batch_id"]
            );
            return step.step_id;
        } catch (std::exception& ex) {
            this->_handle_step_load_error(ex, get_work_response["batch_step_ids"]);
            this->run_succeeded = false;
            return "";
        }
    } else {
        return "";
    }
}

GetWorkResponse Worker::_get_work() {
    if (this->_stop_requesting_work) {
        return GetWorkResponse("", {}, 0, 0, 0, WORKER_STATE_DISABLED);
    }

    std::map<std::string, std::string> r;
    if (this->worker_processes > 0) {
        std::cout << "Asking scheduler for work..." << std::endl;
        r = this->_scheduler.get_work(this->_id, this->host, this->_assistant, this->_running_steps);
    } else {
        std::cout << "Checking if steps are still pending" << std::endl;
        r = this->_scheduler.count_pending(this->_id);
    }

    std::vector<std::string> running_steps = r["running_steps"];
    std::string step_id = this->_get_work_step_id(r);

    this->_get_work_response_history.push_back({step_id, running_steps});

    if (step_id != "" && this->_scheduled_steps.count(step_id) == 0) {
        std::cout << "Did not schedule " << step_id << ", will load it dynamically" << std::endl;
        try {
            this->_scheduled_steps[step_id] = load_step(r["step_module"], r["step_family"], r["step_params"]);
        } catch (StepClassException& ex) {
            this->_handle_step_load_error(ex, {step_id});
            this->run_succeeded = false;
            step_id = "";
        }
    }

    if (step_id != "" && r.count("batch_step_ids") > 0) {
        std::vector<std::string> batch_steps;
        for (const auto& batch_id : r["batch_step_ids"]) {
            if (this->_scheduled_steps.count(batch_id) > 0) {
                batch_steps.push_back(this->_scheduled_steps[batch_id]);
            }
        }
        this->_batch_running_steps[step_id] = batch_steps;
    }

    return GetWorkResponse(
            step_id,
            running_steps,
            r["n_pending_steps"],
            r["n_unique_pending"],
            r.count("n_pending_last_scheduled") > 0 ? r["n_pending_last_scheduled"] : 0,
            r.count("worker_state") > 0 ? r["worker_state"] : WORKER_STATE_ACTIVE
    );
}


void Worker::_run_step(std::string step_id) {
    if (this->_running_steps.count(step_id) > 0) {
        std::cout << "Got already running step id " << step_id << " from scheduler, taking a break" << std::endl;
        this->_sleeper.next();
        return;
    }

    Step step = this->_scheduled_steps[step_id];

    StepProcess step_process = this->_create_step_process(step);

    this->_running_steps[step_id] = step_process;

    if (step_process.use_multiprocessing) {
        fork_lock.lock();
        step_process.start();
        fork_lock.unlock();
    } else {
        // Run in the same process
        step_process.run();
    }
}

StepProcess Worker::_create_step_process(Step step) {
    std::queue<std::string> message_queue;
    if (step.accepts_messages) {
        // Initialize message_queue
    }

    StepStatusReporter reporter(this->_scheduler, step.step_id, this->_id, message_queue);
    bool use_multiprocessing = this->_config.force_multiprocessing || bool(this->worker_processes > 1);

    return ContextManagedStepProcess(
            this->_config.step_process_context,
            step, this->_id, this->_step_result_queue, reporter,
            use_multiprocessing,
            this->_config.timeout,
            this->_config.check_unfulfilled_deps,
            this->_config.check_complete_on_run,
            this->_step_completion_cache
    );
}

void Worker::_purge_children() {
    for (auto const& [step_id, p] : this->_running_steps) {
        std::string error_msg;
        if (!p->is_alive() && p->exitcode) {
            error_msg = "Step " + step_id + " died unexpectedly with exit code " + std::to_string(p->exitcode);
            p->step.trigger_event(Event::PROCESS_FAILURE, p->step, error_msg);
        } else if (p->timeout_time != nullptr && std::time(0) > std::stof(p->timeout_time) && p->is_alive()) {
            p->terminate();
            error_msg = "Step " + step_id + " timed out after " + std::to_string(p->worker_timeout) + " seconds and was terminated.";
            p->step.trigger_event(Event::TIMEOUT, p->step, error_msg);
        } else {
            continue;
        }

        std::cout << error_msg << std::endl;
        this->_step_result_queue.push({step_id, FAILED, error_msg, {}, {}});
    }
}

void Worker::_handle_next_step() {
    this->_idle_since = nullptr;
    while (true) {
        this->_purge_children();  // Deal with subprocess failures

        try {
            auto [step_id, status, expl, missing, new_requirements] = this->_step_result_queue.get(this->_config.wait_interval);
        } catch (Queue::Empty) {
            return;
        }

        Step step = this->_scheduled_steps[step_id];
        if (!step || this->_running_steps.count(step_id) == 0) {
            continue;
        }

        bool external_step_retryable = _is_external(step) && this->_config.retry_external_steps;
        if (status == FAILED && !external_step_retryable) {
            this->_email_step_failure(step, expl);
        }

        std::vector<std::string> new_deps;
        if (!new_requirements.empty()) {
            for (auto [module, name, params] : new_requirements) {
                Step t = load_step(module, name, params);
                this->add(t);
                new_deps.push_back(t.step_id);
            }
        }

        this->_add_step(this->_id,
                        step_id,
                        status,
                        json::dump(expl),
                        step.process_resources(),
                        nullptr,
                        step.to_str_params(),
                        step.step_family,
                        step.step_module,
                        new_deps,
                        this->_assistant,
                        _get_retry_policy_dict(step));

        this->_running_steps.erase(step_id);

        if (!missing.empty()) {
            bool reschedule = true;

            for (auto step_id : missing) {
                this->unfulfilled_counts[step_id] += 1;
                if (this->unfulfilled_counts[step_id] > this->_config.max_reschedules) {
                    reschedule = false;
                }
            }
            if (reschedule) {
                this->add(step);
            }
        }
        this->run_succeeded &= (status == DONE) || (!new_deps.empty());
        return;
    }
}
void Worker::_sleeper() {
    while (true) {
        double jitter = this->_config.wait_jitter;
        double wait_interval = this->_config.wait_interval + ((double) rand() / (RAND_MAX)) * jitter;
        std::cout << "Sleeping for " << wait_interval << " seconds" << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(int(wait_interval * 1000)));
    }
}

bool Worker::_keep_alive(GetWorkResponse get_work_response) {
    if (!this->_config.keep_alive) {
        return false;
    } else if (this->_assistant) {
        return true;
    } else if (this->_config.count_last_scheduled) {
        return get_work_response.n_pending_last_scheduled > 0;
    } else if (this->_config.count_uniques) {
        return get_work_response.n_unique_pending > 0;
    } else if (get_work_response.n_pending_steps == 0) {
        return false;
    } else if (!this->_config.max_keep_alive_idle_duration) {
        return true;
    } else if (!this->_idle_since) {
        return true;
    } else {
        auto now = std::chrono::system_clock::now();
        auto time_to_shutdown = this->_idle_since + std::chrono::seconds(this->_config.max_keep_alive_idle_duration) - now;
        std::cout << "[" << this->_id << "] " << std::chrono::duration_cast<std::chrono::seconds>(time_to_shutdown).count() << " until shutdown" << std::endl;
        return time_to_shutdown > std::chrono::seconds(0);
    }
}
void Worker::handle_interrupt(int signum) {
    // Stops the assistant from asking for more work on SIGUSR1
    if (signum == SIGUSR1) {
        this->_start_phasing_out();
    }
}

void Worker::_start_phasing_out() {
    // Go into a mode where we dont ask for more work and quit once existing steps are done.
    this->_config.keep_alive = false;
    this->_stop_requesting_work = true;
}

bool Worker::run() {
    std::cout << "Running Worker with " << worker_processes << " processes" << std::endl;

    auto sleeper = _sleeper();
    bool run_succeeded = true;

    _add_worker();

    while (true) {
        while (_running_steps.size() >= worker_processes > 0) {
            std::cout << _running_steps.size() << " running steps, waiting for next step to finish" << std::endl;
            _handle_next_step();
        }

        auto get_work_response = _get_work();

        if (get_work_response.worker_state == WORKER_STATE_DISABLED) {
            _start_phasing_out();
        }

        if (get_work_response.step_id.empty()) {
            if (!_stop_requesting_work) {
                _log_remote_steps(get_work_response);
            }
            if (_running_steps.empty()) {
                _idle_since = _idle_since.value_or(std::chrono::system_clock::now());
                if (_keep_alive(get_work_response)) {
                    sleeper.next();
                    continue;
                } else {
                    break;
                }
            } else {
                _handle_next_step();
                continue;
            }
        }

        // step_id is not None:
        std::cout << "Pending steps: " << get_work_response.n_pending_steps << std::endl;
        _run_step(get_work_response.step_id);
    }
    while (!_running_steps.empty()) {
        std::cout << "Shut down Worker, " << _running_steps.size() << " more steps to go" << std::endl;
        _handle_next_step();
    }
    return run_succeeded;
}


void Worker::_handle_rpc_message(std::map<std::string, std::any> message) {
    std::cout << "Worker " << this->_id << " got message " << message << std::endl;
    // the message is a map {'name': <function_name>, 'kwargs': <function_kwargs>}
    std::string name = std::any_cast<std::string>(message["name"]);
    std::map < std::string, std::any > kwargs = std::any_cast < std::map < std::string, std::any >> (message["kwargs"]);

    // find the function and check if it's callable and configured to work
    // as a message callback
    auto func = this->rpc_message_callbacks[name];
    std::string tpl = this->_id + " " + name;
    if (!func) {
        std::cerr << "Worker " << tpl << " has no function" << std::endl;
    } else if (!this->is_rpc_message_callback(name)) {
        std::cerr << "Worker " << tpl << " function is not available as rpc message callback" << std::endl;
    } else {
        std::cout << "Worker " << tpl << " successfully dispatched rpc message to function" << std::endl;
        func(kwargs);
    }
}

void Worker::set_worker_processes(int n) {
    // set the new value
    this->worker_processes = std::max(1, n);

    // tell the scheduler
    this->_scheduler.add_worker(this->_id, {{"workers", this->worker_processes}});
}

void Worker::dispatch_scheduler_message(std::string step_id, int message_id, std::string content, std::map<std::string, std::any> kwargs) {
    if (this->_running_steps.count(step_id) > 0) {
        auto step_process = this->_running_steps[step_id];
        if (step_process.status_reporter.scheduler_messages) {
            SchedulerMessage message(this->_scheduler, step_id, message_id, content, kwargs);
            step_process.status_reporter.scheduler_messages.push(message);
        }
    }
}
