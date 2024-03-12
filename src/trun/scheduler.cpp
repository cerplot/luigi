#include <map>
#include <string>
#include <vector>
#include <regex>
#include "scheduler.h"

const std::string UPSTREAM_RUNNING = "UPSTREAM_RUNNING";
const std::string UPSTREAM_MISSING_INPUT = "UPSTREAM_MISSING_INPUT";
const std::string UPSTREAM_FAILED = "UPSTREAM_FAILED";
const std::string UPSTREAM_DISABLED = "UPSTREAM_DISABLED";

const std::vector<std::string> UPSTREAM_SEVERITY_ORDER = {
        "",
        UPSTREAM_RUNNING,
        UPSTREAM_MISSING_INPUT,
        UPSTREAM_FAILED,
        UPSTREAM_DISABLED,
};

const std::string FAILED = "FAILED";
const std::string RUNNING = "RUNNING";
const std::string BATCH_RUNNING = "BATCH_RUNNING";
const std::string PENDING = "PENDING";
const std::string DISABLED = "DISABLED";

const std::map<std::string, std::string> STATUS_TO_UPSTREAM_MAP = {
        {FAILED, UPSTREAM_FAILED},
        {RUNNING, UPSTREAM_RUNNING},
        {BATCH_RUNNING, UPSTREAM_RUNNING},
        {PENDING, UPSTREAM_MISSING_INPUT},
        {DISABLED, UPSTREAM_DISABLED},
};

const std::string WORKER_STATE_DISABLED = "disabled";
const std::string WORKER_STATE_ACTIVE = "active";

const std::regex STEP_FAMILY_RE("([^(_]+)[(_]");

std::map<std::string, std::string> RPC_METHODS;

std::vector<std::string> _retry_policy_fields = {
        "retry_count",
        "disable_hard_timeout",
        "disable_window",
};


RetryPolicy _get_empty_retry_policy() {
    return RetryPolicy{0, false, false};
}

std::map<std::string, std::function<void()>> RPC_METHODS;

template<typename Func>
Func rpc_method(std::map<std::string, std::string> request_args, Func fn) {
    // Get the function name
    std::string fn_name = typeid(fn).name();

    // Create a new function that wraps the original function
    auto rpc_func = [this, fn, request_args, fn_name](std::map<std::string, std::string> args) {
        // Check if all required arguments are present
        for (const auto& arg : args) {
            if (request_args.find(arg.first) == request_args.end()) {
                throw std::invalid_argument(fn_name + " takes certain arguments that are not given");
            }
        }

        // Make a request to the API endpoint
        return this->_request("/api/" + fn_name, args, request_args);
    };

    // Add the new function to the RPC_METHODS map
    RPC_METHODS[fn_name] = rpc_func;

    // Return the original function
    return fn;
}

std::string _request(std::string endpoint, std::map<std::string, std::string> args, std::map<std::string, std::string> request_args) {
    // Implement the request to the API endpoint
    // This is just a placeholder implementation
    return "Request made to " + endpoint;
}


class scheduler {
public:
    float retry_delay = 900.0;
    float remove_delay = 600.0;
    float worker_disconnect_delay = 60.0;
    std::string state_path = "/var/lib/trun-server/state.pickle";

    bool batch_emails = false;

    int disable_window = 3600;
    int retry_count = 999999999;
    int disable_hard_timeout = 999999999;
    int disable_persist = 86400;
    int max_shown_steps = 100000;
    int max_graph_nodes = 100000;

    bool record_step_history = false;

    bool prune_on_get_work = false;

    bool pause_enabled = true;

    bool send_messages = true;

    std::string metrics_collector = "default";
    std::string metrics_custom_import = "";

    int stable_done_cooldown_secs = 10;

    RetryPolicy _get_retry_policy() {
        return RetryPolicy(retry_count, disable_hard_timeout, disable_window);
    }
};

template<typename T>
T _get_default(T x, T default_value) {
    if (x != nullptr) {
        return x;
    } else {
        return default_value;
    }
}

template<typename T>
class OrderedSet {
public:
    void add(const T& key) {
        if (map.find(key) == map.end()) {
            auto it = list.insert(list.end(), key);
            map[key] = it;
        }
    }

    void discard(const T& key) {
        auto map_it = map.find(key);
        if (map_it != map.end()) {
            list.erase(map_it->second);
            map.erase(map_it);
        }
    }

    bool contains(const T& key) {
        return map.find(key) != map.end();
    }

    T peek(bool last = true) {
        if (list.empty()) {
            throw std::out_of_range("set is empty");
        }
        return last ? list.back() : list.front();
    }

    T pop(bool last = true) {
        T key = peek(last);
        discard(key);
        return key;
    }

    size_t size() const {
        return map.size();
    }

    bool operator==(const OrderedSet<T>& other) const {
        return list == other.list;
    }

    bool operator!=(const OrderedSet<T>& other) const {
        return list != other.list;
    }

private:
    std::unordered_map<T, typename std::list<T>::iterator> map;
    std::list<T> list;
};



enum class ParameterVisibility {
    PUBLIC,
    HIDDEN
};

class Step {
public:
    std::string id;
    std::set<int> stakeholders;
    OrderedSet<int> workers;
    std::set<std::string> deps;
    std::string status;
    time_t time;
    time_t updated;
    time_t retry;
    time_t remove;
    int worker_running;
    time_t time_running;
    std::string expl;
    int priority;
    std::map<std::string, int> resources;
    std::string family;
    std::string module;
    std::map<std::string, ParameterVisibility> param_visibilities;
    std::map<std::string, std::string> params;
    std::map<std::string, std::string> public_params;
    std::map<std::string, std::string> hidden_params;
    bool accepts_messages;
    std::string retry_policy;
    std::deque<time_t> failures;
    time_t first_failure_time;
    std::string tracking_url;
    std::string status_message;
    std::string progress_percentage;
    std::map<std::string, std::string> scheduler_message_responses;
    time_t scheduler_disable_time;
    bool runnable;
    bool batchable;
    std::string batch_id;

    Step(std::string step_id, std::string status, std::set<std::string> deps, std::map<std::string, int> resources = {}, int priority = 0, std::string family = "", std::string module = "",
         std::map<std::string, std::string> params = {}, std::map<std::string, ParameterVisibility> param_visibilities = {}, bool accepts_messages = false, std::string tracking_url = "", std::string status_message = "",
         std::string progress_percentage = "", std::string retry_policy = "notoptional") {
        this->id = step_id;
        this->deps = deps;
        this->status = status;
        this->time = std::time(0);
        this->updated = this->time;
        this->priority = priority;
        this->resources = resources;
        this->family = family;
        this->module = module;
        this->param_visibilities = param_visibilities;
        this->set_params(params);
        this->accepts_messages = accepts_messages;
        this->retry_policy = retry_policy;
        this->tracking_url = tracking_url;
        this->status_message = status_message;
        this->progress_percentage = progress_percentage;
    }

    void set_params(std::map<std::string, std::string> params) {
        this->params = params;
        for (auto const& [key, value] : this->params) {
            if (this->param_visibilities[key] == ParameterVisibility::PUBLIC) {
                this->public_params[key] = value;
            } else {
                this->hidden_params[key] = value;
            }
        }
    }

    bool is_batchable() {
        return this->batchable;
    }

    void add_failure() {
        this->failures.push_back(std::time(0));
        if (this->first_failure_time == 0) {
            this->first_failure_time = this->failures.back();
        }
    }

    int num_failures() {
        time_t min_time = std::time(0) - std::stoi(this->retry_policy);
        while (!this->failures.empty() && this->failures.front() < min_time) {
            this->failures.pop_front();
        }
        return this->failures.size();
    }

    bool has_excessive_failures() {
        if (this->first_failure_time != 0 && std::time(0) >= this->first_failure_time + std::stoi(this->retry_policy)) {
            return true;
        }
        if (this->num_failures() >= std::stoi(this->retry_policy)) {
            return true;
        }
        return false;
    }

    void clear_failures() {
        this->failures.clear();
        this->first_failure_time = 0;
    }
};
bool Step::batchable() {
    // Implement logic to check if the step is batchable
    // For example, return true if there are any batched parameters
    return !batch_param_names().empty();
}
int Step::retry_count() {
    // Implement logic to get retry count
    // For example, return a member variable that stores the retry count
    return this->retry_count;
}
int Step::disable_hard_timeout() {
    // Implement logic to get disable_hard_timeout
    // For example, return a member variable that stores the disable_hard_timeout
    return this->disable_hard_timeout;
}
int Step::disable_window() {
    // Implement logic to get disable_window
    // For example, return a member variable that stores the disable_window
    return this->disable_window;
}
int Step::disable_window_seconds() {
    // Implement logic to get disable_window
    // For example, return a member variable that stores the disable_window
    std::cout << "Use of `disable_window_seconds` has been deprecated, use `disable_window` instead" << std::endl;
    return this->disable_window;
}
std::vector<std::string> Step::owner_email() {
    // Implement logic to get owner_email
    // For example, return a member variable that stores the owner_email
    return this->owner_email;
}
std::vector<std::string> Step::_owner_list() {
    // Implement logic to get owner_email
    // For example, return a member variable that stores the owner_email
    std::vector<std::string> owner_list;
    if (this->owner_email.empty()) {
        return owner_list;
    } else {
        std::stringstream ss(this->owner_email);
        std::string token;
        while (std::getline(ss, token, ',')) {
            owner_list.push_back(token);
        }
        return owner_list;
    }
}
bool Step::use_cmdline_section() {
    // Implement logic to get use_cmdline_section
    // For example, return a member variable that stores the use_cmdline_section
    return this->use_cmdline_section;
}
static std::map<std::string, std::set<std::function<void()>>> Step::_event_callbacks;

static std::function<void()> Step::event_handler(std::string event, std::function<void()> callback) {
    _event_callbacks[event].insert(callback);
    return callback;
}

std::map<std::string, std::set<std::function<void()>>> Step::_event_callbacks;
void Step::trigger_event(std::string event) {
    // Check if there are any callbacks for the given event
    if (_event_callbacks.find(event) != _event_callbacks.end()) {
        // Get the set of callbacks for the event
        std::set<std::function<void()>> callbacks = _event_callbacks[event];
        // Call each callback
        for (const auto& callback : callbacks) {
            try {
                // Call the callback
                callback();
            } catch (const std::exception& e) {
                // Log the exception
                std::cerr << "Error in event callback for " << event << ": " << e.what() << std::endl;
            }
        }
    }
}
bool Step::accepts_messages() {
    // Implement logic to get accepts_messages
    // For example, return a member variable that stores the accepts_messages
    return this->accepts_messages;
}

std::string Step::step_module() {
    // Implement logic to get step_module
    // For example, return a member variable that stores the step_module
    return this->step_module;
}
class Step {
public:
    static std::string step_namespace;
    static const std::string not_user_specified;
    static const std::string namespace_at_class_time;
    static const std::string SAME_AS_CPP_NAMESPACE;

    static std::string get_step_namespace() {
        if (step_namespace != not_user_specified) {
            return step_namespace;
        } else if (namespace_at_class_time == SAME_AS_CPP_NAMESPACE) {
            return "Step"; // Replace "Step" with the actual namespace of the Step class
        }
        return namespace_at_class_time;
    }
};

// Initialize static members
std::string Step::step_namespace = "";
const std::string Step::not_user_specified = "";
const std::string Step::namespace_at_class_time = "";
const std::string Step::SAME_AS_CPP_NAMESPACE = "";

std::string Step::step_family() {
    // Implement logic to get step_family
    // For example, return a member variable that stores the step_family
    return this->step_family;
}

class Step {
public:
    static std::string step_namespace;
    static std::string class_name;

    static std::string get_step_family() {
        if (step_namespace.empty()) {
            return class_name;
        } else {
            return step_namespace + "." + class_name;
        }
    }
};

// Initialize static members
std::string Step::step_namespace = "";
std::string Step::class_name = "Step"; // Replace "Step" with the actual class name



class Step {
public:
    static std::vector<std::pair<std::string, Parameter>> get_params() {
        std::vector<std::pair<std::string, Parameter>> params;

        // Get all member variables of the Step class
        // This is just a placeholder implementation, you need to replace it with the actual logic
        std::vector<std::string> member_variables = {"param1", "param2", "param3"};

        for (const auto& param_name : member_variables) {
            // Get the Parameter object corresponding to param_name
            // This is just a placeholder implementation, you need to replace it with the actual logic
            Parameter param_obj;

            params.push_back(std::make_pair(param_name, param_obj));
        }

        // Sort the parameters based on the _counter member of the Parameter class
        std::sort(params.begin(), params.end(), [](const std::pair<std::string, Parameter>& a, const std::pair<std::string, Parameter>& b) {
            return a.second._counter < b.second._counter;
        });

        return params;
    }
};
class Step {
public:
    static std::vector<std::pair<std::string, Parameter>> get_params() {
        // ... existing implementation ...
    }

    static std::vector<std::string> batch_param_names() {
        std::vector<std::string> batchable_param_names;
        std::vector<std::pair<std::string, Parameter>> params = get_params();

        for (const auto& param : params) {
            if (param.second.is_batchable()) { // Assuming Parameter class has a method is_batchable()
                batchable_param_names.push_back(param.first);
            }
        }

        return batchable_param_names;
    }
};

class Step {
public:
    static std::vector<std::pair<std::string, Parameter>> get_params() {
        // ... existing implementation ...
    }

    static std::vector<std::string> get_param_names(bool include_significant = false) {
        std::vector<std::string> param_names;
        std::vector<std::pair<std::string, Parameter>> params = get_params();

        for (const auto& param : params) {
            if (include_significant || param.second.is_significant()) { // Assuming Parameter class has a method is_significant()
                param_names.push_back(param.first);
            }
        }

        return param_names;
    }
};
class Step {
public:
    static std::vector<std::pair<std::string, Parameter>> get_params() {
        // ... existing implementation ...
    }

    static std::string get_step_family() {
        // ... existing implementation ...
    }

    static std::vector<std::pair<std::string, std::string>> get_param_values(std::vector<std::pair<std::string, Parameter>> params, std::vector<std::string> args, std::map<std::string, std::string> kwargs) {
        std::map<std::string, std::string> result;
        std::map<std::string, Parameter> params_dict;

        for (const auto& param : params) {
            params_dict[param.first] = param.second;
        }

        std::string step_family = get_step_family();

        // Fill in the positional arguments
        std::vector<std::pair<std::string, Parameter>> positional_params;
        for (const auto& param : params) {
            if (param.second.is_positional()) { // Assuming Parameter class has a method is_positional()
                positional_params.push_back(param);
            }
        }

        for (size_t i = 0; i < args.size(); ++i) {
            if (i >= positional_params.size()) {
                throw std::invalid_argument("Too many parameters given");
            }
            std::string param_name = positional_params[i].first;
            Parameter param_obj = positional_params[i].second;
            result[param_name] = param_obj.normalize(args[i]); // Assuming Parameter class has a method normalize()
        }

        // Then the keyword arguments
        for (const auto& kwarg : kwargs) {
            std::string param_name = kwarg.first;
            if (result.find(param_name) != result.end()) {
                throw std::invalid_argument("Duplicate parameter " + param_name);
            }
            if (params_dict.find(param_name) == params_dict.end()) {
                throw std::invalid_argument("Unknown parameter " + param_name);
            }
            result[param_name] = params_dict[param_name].normalize(kwarg.second); // Assuming Parameter class has a method normalize()
        }

        // Then use the defaults for anything not filled in
        for (const auto& param : params) {
            std::string param_name = param.first;
            Parameter param_obj = param.second;
            if (result.find(param_name) == result.end()) {
                if (!param_obj.has_step_value(step_family, param_name)) { // Assuming Parameter class has a method has_step_value()
                    throw std::invalid_argument("Missing parameter " + param_name);
                }
                result[param_name] = param_obj.step_value(step_family, param_name); // Assuming Parameter class has a method step_value()
            }
        }

        // Sort it by the correct order and make a list
        std::vector<std::pair<std::string, std::string>> sorted_result;
        for (const auto& param : params) {
            sorted_result.push_back(std::make_pair(param.first, result[param.first]));
        }

        return sorted_result;
    }


    std::map<std::string, std::string> param_kwargs;
    std::string step_id;
    size_t __hash;

Step::Step(std::vector<std::string> args, std::map<std::string, std::string> kwargs) {
        std::vector<std::pair<std::string, Parameter>> params = get_params();
        std::vector<std::pair<std::string, std::string>> param_values = get_param_values(params, args, kwargs);

        // Set all values on class instance
        for (const auto& param_value : param_values) {
            std::string key = param_value.first;
            std::string value = param_value.second;
            // Assuming you have a method set_attribute to set the attribute
            this->set_attribute(key, value);
        }

        // Register kwargs as an attribute on the class. Might be useful
        this->param_kwargs = std::map<std::string, std::string>(param_values.begin(), param_values.end());

        this->_warn_on_wrong_param_types(); // Assuming you have a method _warn_on_wrong_param_types to warn on wrong parameter types
        this->step_id = step_id_str(this->get_step_family(), this->to_str_params(true, true)); // Assuming you have methods step_id_str and to_str_params to get the step id and to convert parameters to string
        this->__hash = std::hash<std::string>{}(this->step_id);

        this->set_tracking_url = nullptr;
        this->set_status_message = nullptr;
        this->set_progress_percentage = nullptr;
    }

    // ... other methods ...

    std::map<std::string, std::string> param_kwargs;


    std::vector<std::string> Step::param_args() {
        std::cout << "Use of param_args has been deprecated." << std::endl;
        std::vector<std::string> args;
        std::vector<std::pair<std::string, Parameter>> params = get_params();

        for (const auto& param : params) {
            args.push_back(param_kwargs[param.first]);
        }

        return args;
    }

    std::string step_id;

    // ... other methods ...

    bool Step::initialized() {
        return !step_id.empty();
    }

    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    // ... other methods ...

    void Step::_warn_on_wrong_param_types() {
        for (const auto& param : param_kwargs) {
            std::string param_name = param.first;
            std::string param_value = param.second;
            if (params.find(param_name) != params.end()) {
                params[param_name]._warn_on_wrong_param_type(param_name, param_value); // Assuming Parameter class has a method _warn_on_wrong_param_type()
            }
        }
    }


    static Step Step::from_str_params(std::map<std::string, std::string> params_str) {
        std::map<std::string, std::string> kwargs;
        std::vector<std::pair<std::string, Parameter>> params = get_params();

        for (const auto& param : params) {
            std::string param_name = param.first;
            Parameter param_obj = param.second;
            if (params_str.find(param_name) != params_str.end()) {
                std::string param_str = params_str[param_name];
                if (param_obj.is_list(param_str)) { // Assuming Parameter class has a method is_list()
                    kwargs[param_name] = param_obj.parse_list(param_str); // Assuming Parameter class has a method parse_list()
                } else {
                    kwargs[param_name] = param_obj.parse(param_str); // Assuming Parameter class has a method parse()
                }
            }
        }

        return Step(kwargs); // Assuming Step class has a constructor that takes a std::map<std::string, std::string>
    }


    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    // ... other methods ...

    std::map<std::string, std::string> Step::to_str_params(bool only_significant = false, bool only_public = false) {
        std::map<std::string, std::string> params_str;
        std::map<std::string, Parameter> params_map = get_params();

        for (const auto& param : param_kwargs) {
            std::string param_name = param.first;
            std::string param_value = param.second;
            if (params_map.find(param_name) != params_map.end()) {
                Parameter param_obj = params_map[param_name];
                if ((!only_significant || param_obj.is_significant()) // Assuming Parameter class has a method is_significant()
                    && (!only_public || param_obj.visibility == ParameterVisibility::PUBLIC)
                    && param_obj.visibility != ParameterVisibility::PRIVATE) {
                    params_str[param_name] = param_obj.serialize(param_value); // Assuming Parameter class has a method serialize()
                }
            }
        }

        return params_str;
    }


    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    std::map<std::string, std::string> Step::_get_param_visibilities() {
        std::map<std::string, std::string> param_visibilities;
        std::map<std::string, Parameter> params_map = get_params();

        for (const auto& param : param_kwargs) {
            std::string param_name = param.first;
            if (params_map.find(param_name) != params_map.end()) {
                Parameter param_obj = params_map[param_name];
                if (param_obj.visibility != ParameterVisibility::PRIVATE) {
                    param_visibilities[param_name] = param_obj.serialize_visibility(); // Assuming Parameter class has a method serialize_visibility()
                }
            }
        }

        return param_visibilities;
    }


    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    template <typename T = Step>
    T Step::clone(std::map<std::string, std::string> kwargs = {}) {
        std::map<std::string, std::string> new_k;
        std::vector<std::pair<std::string, Parameter>> params = T::get_params();

        for (const auto& param : params) {
            std::string param_name = param.first;
            if (kwargs.find(param_name) != kwargs.end()) {
                new_k[param_name] = kwargs[param_name];
            } else if (param_kwargs.find(param_name) != param_kwargs.end()) {
                new_k[param_name] = param_kwargs[param_name];
            }
        }

        return T(new_k); // Assuming T class has a constructor that takes a std::map<std::string, std::string>
    }


struct StepHash {
    std::size_t operator()(const Step &step) const {
        return std::hash < std::string > {}(step.step_id);
    }
};

    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    // ... other methods ...

    friend std::ostream& operator<<(std::ostream& os, const Step& step) {
        std::vector<std::pair<std::string, Parameter>> params = step.get_params();
        std::vector<std::pair<std::string, std::string>> param_values = step.get_param_values(params, {}, step.param_kwargs);

        // Build up step id
        std::vector<std::string> repr_parts;
        std::map<std::string, Parameter> param_objs = std::map<std::string, Parameter>(params.begin(), params.end());
        for (const auto& param_value : param_values) {
            std::string param_name = param_value.first;
            std::string param_value_str = param_value.second;
            if (param_objs[param_name].is_significant()) { // Assuming Parameter class has a method is_significant()
                repr_parts.push_back(param_name + "=" + param_objs[param_name].serialize(param_value_str)); // Assuming Parameter class has a method serialize()
            }
        }

        std::string step_str = step.get_step_family() + "(" + join(repr_parts, ", ") + ")"; // Assuming you have a function join() to join a vector of strings

        os << step_str;
        return os;
    }
    std::string step_id;

    bool operator==(const Step& other) const {
        return typeid(*this) == typeid(other) && this->step_id == other.step_id;
    }

    bool Step::complete() {
        std::vector<Output> outputs = flatten(this->output()); // Assuming you have a method flatten() to flatten the output and a method output() to get the output
        if (outputs.empty()) {
            std::cerr << "Warning: Step " << *this << " without outputs has no custom complete() method" << std::endl;
            return false;
        }

        return std::all_of(outputs.begin(), outputs.end(), [](const Output& output) {
            return output.exists(); // Assuming Output class has a method exists() to check if the output exists
        });
    }

    static std::vector<std::pair<std::string, std::string>> Step::bulk_complete(const std::vector<std::pair<std::string, std::string>>& parameter_tuples) {
        std::vector<std::pair<std::string, std::string>> completed_steps;

        for (const auto& parameter_tuple : parameter_tuples) {
            Step step(parameter_tuple); // Assuming Step class has a constructor that takes a std::pair<std::string, std::string>
            if (step.complete()) { // Assuming Step class has a method complete() to check if the step is complete
                completed_steps.push_back(parameter_tuple);
            }
        }

        return completed_steps;
    }


    std::vector<Target> Step::output() const {
        // The output of the Step determines if the Step needs to be run--the step
        // is considered finished iff the outputs all exist. Subclasses should
        // override this method to return a single Target or a list of
        // Target instances.

        // Implementation note
        // If running multiple workers, the output must be a resource that is accessible
        // by all workers, such as a DFS or database. Otherwise, workers might compute
        // the same output since they don't see the work done by other workers.

        // This is a default implementation that returns an empty vector.
        // Replace it with your actual implementation.
        return std::vector<Target>();
    }

    std::vector<Step> Step::requires() const {
        // The Steps that this Step depends on.
        // A Step will only run if all of the Steps that it requires are completed.
        // If your Step does not require any other Steps, then you don't need to
        // override this method. Otherwise, a subclass can override this method
        // to return a single Step, a list of Step instances, or a dict whose
        // values are Step instances.

        // This is a default implementation that returns an empty vector.
        // Replace it with your actual implementation.
        return std::vector<Step>();
    }

    std::vector<Step> Step::_requires() const {
        // Override in "template" steps which themselves are supposed to be
        // subclassed and thus have their requires() overridden (name preserved to
        // provide consistent end-user experience), yet need to introduce
        // (non-input) dependencies.

        // Must return an iterable which among others contains the _requires() of
        // the superclass.

        // This is a base implementation that returns the result of the requires() method
        // after flattening it. Replace it with your actual implementation.
        return flatten(this->requires()); // Assuming you have a method flatten() to flatten the requires
    }

    std::map<std::string, int> Step::process_resources() const {
        // Override in "template" steps which provide common resource functionality
        // but allow subclasses to specify additional resources while preserving
        // the name for consistent end-user experience.

        // This is a default implementation that returns the resources.
        // Replace it with your actual implementation.
        return this->resources;
    }


std::vector<Target> Step::input() const {
        // Returns the outputs of the Steps returned by requires()

        // This is a default implementation that returns the outputs of the required Steps.
        // Replace it with your actual implementation.
        return getpaths(this->requires()); // Assuming you have a method getpaths() to get the paths of the required Steps
    }

    std::vector<Step> Step::deps() const {
        // Internal method used by the scheduler.
        // Returns the flattened list of requires.
        // used by scheduler

        // This is a default implementation that returns the flattened result of the _requires() method.
        // Replace it with your actual implementation.
        return flatten(this->_requires()); // Assuming you have a method flatten() to flatten the _requires
    }
    virtual void Step::run() {
        // The step run method, to be overridden in a subclass.

        // This is a default implementation that does nothing.
        // Replace it with your actual implementation.
    }

    virtual std::string Step::on_failure(const std::exception& e) {
        // Override for custom error handling.
        // This method gets called if an exception is raised in run().
        // The returned value of this method is json encoded and sent to the scheduler
        // as the `expl` argument. Its string representation will be used as the
        // body of the error email sent out if any.

        // Default behavior is to return a string representation of the stack trace.

        std::stringstream ss;
        ss << "Runtime error:\n" << e.what();
        return ss.str();
    }

    virtual std::string Step::on_success() {
        // Override for doing custom completion handling for a larger class of steps
        // This method gets called when run() completes without raising any exceptions.
        // The returned value is json encoded and sent to the scheduler as the `expl` argument.
        // Default behavior is to send an None value

        // This is a default implementation that does nothing.
        // Replace it with your actual implementation.
        return "";
    }


#include <set>
#include <map>
#include <string>
#include <ctime>
#include <vector>

class Worker {
public:
    std::string id;
    std::map<std::string, std::string> reference;
    time_t last_active;
    time_t last_get_work;
    time_t started;
    std::set<Step*> steps;
    std::map<std::string, std::string> info;
    bool disabled;
    std::vector<std::map<std::string, std::string>> rpc_messages;

    Worker(std::string worker_id, time_t last_active = std::time(0)) {
        this->id = worker_id;
        this->last_active = last_active;
        this->started = std::time(0);
        this->disabled = false;
    }

    void add_info(std::map<std::string, std::string> info) {
        this->info.insert(info.begin(), info.end());
    }

    void update(std::map<std::string, std::string> worker_reference, bool get_work = false) {
        if (!worker_reference.empty()) {
            this->reference = worker_reference;
        }
        this->last_active = std::time(0);
        if (get_work) {
            this->last_get_work = std::time(0);
        }
    }

    bool prune(float worker_disconnect_delay) {
        if (this->last_active + worker_disconnect_delay < std::time(0)) {
            return true;
        }
        return false;
    }

    bool is_trivial_worker() {
        for (auto& step : this->steps) {
            if (!step->resources.empty()) {
                return false;
            }
        }
        return true;
    }

    bool assistant() {
        return this->info["assistant"] == "true";
    }

    bool enabled() {
        return !this->disabled;
    }

    std::string state() {
        return this->enabled() ? "active" : "disabled";
    }

    void add_rpc_message(std::string name, std::map<std::string, std::string> kwargs) {
        this->rpc_messages.push_back({{"name", name}, {"kwargs", kwargs}});
    }

    std::vector<std::map<std::string, std::string>> fetch_rpc_messages() {
        std::vector<std::map<std::string, std::string>> messages = this->rpc_messages;
        this->rpc_messages.clear();
        return messages;
    }
};


#include <map>
#include <string>
#include <vector>
#include <ctime>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <iterator>

class SimpleStepState {
public:
    std::string _state_path;
    std::map<std::string, Step*> _steps;
    std::map<std::string, std::map<std::string, Step*>> _status_steps;
    std::map<std::string, Worker*> _active_workers;
    std::map<std::string, std::string> _step_batchers;
    std::string _metrics_collector;

    SimpleStepState(std::string state_path) {
        _state_path = state_path;
    }

    std::tuple<std::map<std::string, Step*>, std::map<std::string, Worker*>, std::map<std::string, std::string>> get_state() {
        return std::make_tuple(this->_steps, this->_active_workers, this->_step_batchers);
    }

    void set_state(std::tuple<std::map<std::string, Step*>, std::map<std::string, Worker*>, std::map<std::string, std::string>> state) {
        _steps = std::get<0>(state);
        _active_workers = std::get<1>(state);
        if (std::tuple_size<decltype(state)>::value >= 3) {
            _step_batchers = std::get<2>(state);
        }
    }

    void dump() {
        try {
            std::ofstream file(_state_path, std::ios::binary);
            if (!file) {
                throw std::runtime_error("Failed to open file");
            }
            boost::archive::text_oarchive oa(file);
            oa << get_state();
            file.close();
            std::cout << "Saved state in " << _state_path << std::endl;
        } catch (std::exception& e) {
            std::cerr << "Failed saving scheduler state: " << e.what() << std::endl;
        }
    }

    void load() {
        if (std::filesystem::exists(_state_path)) {
            std::cout << "Attempting to load state from " << _state_path << std::endl;
            try {
                std::ifstream file(_state_path, std::ios::binary);
                if (!file) {
                    throw std::runtime_error("Failed to open file");
                }
                boost::archive::text_iarchive ia(file);
                std::tuple<std::map<std::string, Step*>, std::map<std::string, Worker*>, std::map<std::string, std::string>> state;
                ia >> state;
                set_state(state);
                _status_steps.clear();
                for (auto const& [key, value] : _steps) {
                    _status_steps[value->status][key] = value;
                }
            } catch (std::exception& e) {
                std::cerr << "Error when loading state. Starting from empty state: " << e.what() << std::endl;
            }
        } else {
            std::cout << "No prior state file exists at " << _state_path << ". Starting with empty state" << std::endl;
        }
    }

    std::vector<Step*> get_active_steps() {
        std::vector<Step*> steps;
        for (auto const& [key, value] : _steps) {
            steps.push_back(value);
        }
        return steps;
    }

    std::vector<Step*> get_active_steps_by_status(std::vector<std::string> statuses) {
        std::vector<Step*> steps;
        for (auto const& status : statuses) {
            for (auto const& [key, value] : this->_status_steps[status]) {
                steps.push_back(value);
            }
        }
        return steps;
    }

    int get_active_step_count_for_status(std::string status) {
        if (!status.empty()) {
            return _status_steps[status].size();
        } else {
            return _steps.size();
        }
    }

    std::vector<Step*> get_batch_running_steps(std::string batch_id) {
        assert(!batch_id.empty());
        std::vector<Step*> batch_running_steps;
        for (Step* step : this->get_active_steps_by_status({BATCH_RUNNING})) {
            if (step->batch_id == batch_id) {
                batch_running_steps.push_back(step);
            }
        }
        return batch_running_steps;
    }

    void set_batcher(std::string worker_id, std::string family, std::string batcher_args, int max_batch_size) {
        if (_step_batchers.find(worker_id) == _step_batchers.end()) {
            _step_batchers[worker_id] = std::map<std::string, std::pair<std::string, int>>();
        }
        _step_batchers[worker_id][family] = std::make_pair(batcher_args, max_batch_size);
    }

    std::pair<std::string, int> get_batcher(std::string worker_id, std::string family) {
        if (_step_batchers.find(worker_id) != _step_batchers.end()) {
            if (_step_batchers[worker_id].find(family) != _step_batchers[worker_id].end()) {
                return _step_batchers[worker_id][family];
            }
        }
        return std::make_pair("", 1);
    }

    int num_pending_steps() {
        return _status_steps[PENDING].size() + _status_steps[RUNNING].size();
    }

    Step* get_step(std::string step_id, Step* default_value = nullptr, Step* setdefault = nullptr) {
        if (setdefault) {
            auto it = _steps.find(step_id);
            if (it != _steps.end()) {
                return it->second;
            } else {
                _steps[step_id] = setdefault;
                _status_steps[setdefault->status][step_id] = setdefault;
                return setdefault;
            }
        } else {
            auto it = _steps.find(step_id);
            if (it != _steps.end()) {
                return it->second;
            } else {
                return default_value;
            }
        }
    }

    bool has_step(std::string step_id) {
        return _steps.find(step_id) != _steps.end();
    }

    void re_enable(Step* step, std::string config = "") {
        step->scheduler_disable_time = 0;
        step->clear_failures();
        if (!config.empty()) {
            set_status(step, FAILED, config);
            step->clear_failures();
        }
    }

    void set_batch_running(Step* step, std::string batch_id, std::string worker_id) {
        set_status(step, BATCH_RUNNING);
        step->batch_id = batch_id;
        step->worker_running = worker_id;
        step->resources_running = step->resources;
        step->time_running = std::time(0);
    }

    void set_status(Step* step, std::string new_status, std::string config = "") {
        if (new_status == FAILED) {
            assert(!config.empty());
        }

        if (new_status == DISABLED && (step->status == RUNNING || step->status == BATCH_RUNNING)) {
            return;
        }

        bool remove_on_failure = !step->batch_id.empty() && !step->is_batchable();

        if (step->status == DISABLED) {
            if (new_status == DONE) {
                re_enable(step);
            } else if (step->scheduler_disable_time != 0 && new_status != DISABLED) {
                return;
            }
        }

        if (step->status == RUNNING && !step->batch_id.empty() && new_status != RUNNING) {
            for (Step* batch_step : get_batch_running_steps(step->batch_id)) {
                set_status(batch_step, new_status, config);
                batch_step->batch_id = "";
            }
            step->batch_id = "";
        }

        if (new_status == FAILED && step->status != DISABLED) {
            step->add_failure();
            if (step->has_excessive_failures()) {
                step->scheduler_disable_time = std::time(0);
                new_status = DISABLED;
                if (!config.batch_emails) {
                    // Send error email
                }
            }
        } else if (new_status == DISABLED) {
            step->scheduler_disable_time = 0;
        }

        if (new_status != step->status) {
            _status_steps[step->status].erase(step->id);
            _status_steps[new_status][step->id] = step;
            step->status = new_status;
            step->updated = std::time(0);
            update_metrics(step, config);
        }

        if (new_status == FAILED) {
            step->retry = std::time(0) + config.retry_delay;
            if (remove_on_failure) {
                step->remove = std::time(0) + config.remove_delay;
            }
        }
    }

    void fail_dead_worker_step(Step* step, std::string config, std::vector<std::string> assistants) {
        // If a running worker disconnects, tag all its jobs as FAILED and subject it to the same retry logic
        if ((step->status == BATCH_RUNNING || step->status == RUNNING) && !step->worker_running.empty() &&
            (step->stakeholders.find(step->worker_running) == step->stakeholders.end() &&
             std::find(assistants.begin(), assistants.end(), step->worker_running) == assistants.end())) {

            std::cout << "Step " << step->id << " is marked as running by disconnected worker " << step->worker_running
                      << " -> marking as FAILED with retry delay of " << config.retry_delay << "s" << std::endl;

            step->worker_running = "";
            set_status(step, FAILED, config);
            step->retry = std::time(0) + std::stoi(config.retry_delay);
        }
    }

    void update_status(Step* step, std::string config) {
        // Mark steps with no remaining active stakeholders for deletion
        if (step->stakeholders.empty() && step->remove == 0 && step->status != RUNNING) {
            std::cout << "Step " << step->id << " has no stakeholders anymore -> might remove "
                      << "step in " << config.remove_delay << " seconds" << std::endl;
            step->remove = std::time(0) + std::stoi(config.remove_delay);
        }

        // Re-enable step after the disable time expires
        if (step->status == DISABLED && step->scheduler_disable_time != 0) {
            if (std::time(0) - step->scheduler_disable_time > std::stoi(config.disable_persist)) {
                re_enable(step, config);
            }
        }

        // Reset FAILED steps to PENDING if max timeout is reached, and retry delay is >= 0
        if (step->status == FAILED && std::stoi(config.retry_delay) >= 0 && step->retry < std::time(0)) {
            set_status(step, PENDING, config);
        }
    }

    bool may_prune(Step* step) {
        return step->remove != 0 && std::time(0) >= step->remove;
    }

    void inactivate_steps(std::vector<std::string> delete_steps) {
        // The terminology is a bit confusing: we used to "delete" steps when they became inactive,
        // but with a pluggable state storage, you might very well want to keep some history of
        // older steps as well. That's why we call it "inactivate" (as in the verb)
        for (std::string step : delete_steps) {
            Step* step_obj = _steps[step];
            _steps.erase(step);
            _status_steps[step_obj->status].erase(step);
        }
    }

    std::vector<Worker*> SimpleStepState::get_active_workers(time_t last_active_lt = 0, time_t last_get_work_gt = 0) {
        std::vector<Worker*> active_workers;
        for (auto const& [key, worker] : _active_workers) {
            if (last_active_lt != 0 && worker->last_active >= last_active_lt) {
                continue;
            }
            time_t last_get_work = worker->last_get_work;
            if (last_get_work_gt != 0 && (last_get_work == 0 || last_get_work <= last_get_work_gt)) {
                continue;
            }
            active_workers.push_back(worker);
        }
        return active_workers;
    }

    std::vector<Worker*> SimpleStepState::get_assistants(time_t last_active_lt = 0) {
        std::vector<Worker*> assistants;
        for (Worker* worker : get_active_workers(last_active_lt)) {
            if (worker->assistant()) {
                assistants.push_back(worker);
            }
        }
        return assistants;
    }

    std::vector<std::string> get_worker_ids() {
        std::vector<std::string> worker_ids;
        for (auto const& [key, value] : _active_workers) {
            worker_ids.push_back(key);
        }
        return worker_ids;
    }

    Worker* get_worker(std::string worker_id) {
        auto it = _active_workers.find(worker_id);
        if (it != _active_workers.end()) {
            return it->second;
        } else {
            Worker* worker = new Worker(worker_id);
            _active_workers[worker_id] = worker;
            return worker;
        }
    }

    void inactivate_workers(std::vector<std::string> delete_workers) {
        // Mark workers as inactive
        for (std::string worker : delete_workers) {
            _active_workers.erase(worker);
        }
        _remove_workers_from_steps(delete_workers);
    }

    void _remove_workers_from_steps(std::vector<std::string> workers, bool remove_stakeholders = true) {
        for (Step* step : get_active_steps()) {
            if (remove_stakeholders) {
                for (const std::string& worker : workers) {
                    step->stakeholders.erase(worker);
                }
            }
            for (const std::string& worker : workers) {
                step->workers.discard(worker);
            }
        }
    }

    void disable_workers(std::vector<std::string> worker_ids) {
        _remove_workers_from_steps(worker_ids, false);
        for (std::string worker_id : worker_ids) {
            Worker* worker = get_worker(worker_id);
            worker->disabled = true;
            worker->steps.clear();
        }
    }

    void update_metrics(Step* step, std::string config) {
        if (step->status == DISABLED) {
            _metrics_collector.handle_step_disabled(step, config);
        } else if (step->status == DONE) {
            _metrics_collector.handle_step_done(step);
        } else if (step->status == FAILED) {
            _metrics_collector.handle_step_failed(step);
        }
    }
};

Scheduler::Scheduler(scheduler* config, std::map<std::string, int> resources, StepHistory* step_history_impl, std::map<std::string, std::string> kwargs) {
    this->_config = config ? config : new scheduler(kwargs);
    this->_state = new SimpleStepState(this->_config->state_path);

    if (step_history_impl) {
        this->_step_history = step_history_impl;
    } else if (this->_config->record_step_history) {
        // Assuming db_step_history is a class that implements StepHistory
        this->_step_history = new db_step_history();
    } else {
        this->_step_history = new NopHistory();
    }

    this->_resources = resources.empty() ? configuration::get_config().getintdict("resources") : resources;

    // Assuming make_step is a function that takes a RetryPolicy and returns a Step*
    this->_make_step = std::bind(make_step, this->_config->_get_retry_policy());

    this->_paused = false;

    if (this->_config->batch_emails) {
        // Assuming BatchNotifier is a class that handles batch emails
        this->_email_batcher = new BatchNotifier();
    }

    // Assuming MetricsCollectors is a class that provides metrics collectors
    this->_state->_metrics_collector = MetricsCollectors::get(this->_config->metrics_collector, this->_config->metrics_custom_import);
}

void Scheduler::load() {
    _state.load();
}
void Scheduler::dump() {
    _state.dump();
    if (_config.batch_emails) {
        _email_batcher.send_email();
    }
}

void Scheduler::prune() {
    logger.debug("Starting pruning of step graph");
    _prune_workers();
    _prune_steps();
    _prune_emails();
    logger.debug("Done pruning step graph");
}

void Scheduler::_prune_workers() {
    std::vector<Worker> remove_workers; // Assuming Worker is a class and get_active_workers returns a vector of Worker
    for (auto &worker : _state.get_active_workers()) {
        if (worker.prune(_config)) {
            logger.debug("Worker %s timed out (no contact for >=%ss)", worker, _config.worker_disconnect_delay);
            remove_workers.push_back(worker.id);
        }
    }
    _state.inactivate_workers(remove_workers);
}
void Scheduler::_prune_steps() {
    std::set<int> assistant_ids; // Assuming id is an integer
    for (auto &assistant : _state.get_assistants()) {
        assistant_ids.insert(assistant.id);
    }

    std::vector<int> remove_steps; // Assuming id is an integer

    for (auto &step : _state.get_active_steps()) {
        _state.fail_dead_worker_step(step, _config, assistant_ids);
        _state.update_status(step, _config);
        if (_state.may_prune(step)) {
            logger.info("Removing step %r", step.id);
            remove_steps.push_back(step.id);
        }
    }

    _state.inactivate_steps(remove_steps);
}

void Scheduler::_prune_emails() {
    if (_config.batch_emails) {
        _email_batcher.update();
    }
}
Worker Scheduler::_update_worker(int worker_id, Worker* worker_reference = nullptr, bool get_work = false) {
    // Assuming Worker is a class and get_worker returns a Worker object
    Worker worker = _state.get_worker(worker_id);
    worker.update(worker_reference, get_work);
    return worker;
}


void Scheduler::_update_priority(Step& step, int prio, Worker& worker) {
    // Assuming Step is a class with a priority member and deps is a vector of dependencies
    // Assuming Worker is a class
    step.priority = prio = std::max(prio, step.priority);
    for (auto& dep : step.deps) {
        Step* t = _state.get_step(dep);
        if (t != nullptr && prio > t->priority) {
            _update_priority(*t, prio, worker);
        }
    }
}

void Scheduler::add_step_batcher(Worker& worker, std::string step_family, std::vector<std::string> batched_args, double max_batch_size = std::numeric_limits<double>::infinity()) {
    _state.set_batcher(worker, step_family, batched_args, max_batch_size);
}

std::map<std::string, std::string> Scheduler::forgive_failures(std::string step_id = "") {
    std::string status = "PENDING";
    Step* step = _state.get_step(step_id);
    if (step == nullptr) {
        return {{"step_id", step_id}, {"status", "None"}};
    }

    if (step->status == "FAILED") {
        _update_step_history(*step, status);
        _state.set_status(*step, status, _config);
    }
    return {{"step_id", step_id}, {"status", step->status}};
}

std::map<std::string, std::string> Scheduler::mark_as_done(std::string step_id = "") {
    std::string status = "DONE";
    Step* step = _state.get_step(step_id);
    if (step == nullptr) {
        return {{"step_id", step_id}, {"status", "None"}};
    }

    if (step->status == "RUNNING" || step->status == "FAILED" || step->status == "DISABLED") {
        _update_step_history(*step, status);
        _state.set_status(*step, status, _config);
    }
    return {{"step_id", step_id}, {"status", step->status}};
}

void Scheduler::add_step(std::string step_id = "", std::string status = "PENDING", bool runnable = true,
                         std::vector<std::string> deps = {}, std::vector<std::string> new_deps = {}, std::string expl = "", std::map<std::string, std::string> resources = {},
                         int priority = 0, std::string family = "", std::string module = "", std::map<std::string, std::string> params = {}, std::map<std::string, std::string> param_visibilities = {}, bool accepts_messages = false,
                         bool assistant = false, std::string tracking_url = "", Worker* worker = nullptr, bool batchable = false,
                         std::string batch_id = "", std::map<std::string, std::string> retry_policy_dict = {}, std::vector<std::string> owners = {}, std::map<std::string, std::string> kwargs = {}) {
    assert(worker != nullptr);
    int worker_id = worker->id;
    Worker updated_worker = _update_worker(worker_id);

    if (retry_policy_dict.empty()) {
        retry_policy_dict = {};
    }

    RetryPolicy retry_policy = _generate_retry_policy(retry_policy_dict);

    if (updated_worker.enabled) {
        Step _default_step = _make_step(step_id, "PENDING", deps, resources, priority, family, module, params, param_visibilities);
    } else {
        Step _default_step = nullptr;
    }

    Step* step = _state.get_step(step_id, _default_step);

    if (step == nullptr || (step->status != "RUNNING" && !updated_worker.enabled)) {
        return;
    }

    if (status == "PENDING" && step->status == "DONE" && (time(nullptr) - step->updated) < _config.stable_done_cooldown_secs) {
        return;
    }

    if (!step->family) {
        step->family = family;
    }
    if (!step->module) {
        step->module = module;
    }
    if (!step->param_visibilities) {
        step->param_visibilities = param_visibilities;
    }
    if (!step->params) {
        step->set_params(params);
    }

    if (batch_id != "") {
        step->batch_id = batch_id;
    }
    if (status == "RUNNING" && !step->worker_running) {
        step->worker_running = worker_id;
        if (batch_id != "") {
            std::vector<Step> batch_steps = _state.get_batch_running_steps(batch_id);
            step->resources_running = batch_steps[0].resources_running;
        }
        step->time_running = time(nullptr);
    }

    if (accepts_messages != false) {
        step->accepts_messages = accepts_messages;
    }

    if (tracking_url != "" || step->status != "RUNNING") {
        step->tracking_url = tracking_url;
        if (step->batch_id != "") {
            for (Step& batch_step : _state.get_batch_running_steps(step->batch_id)) {
                batch_step.tracking_url = tracking_url;
            }
        }
    }

    if (batchable != false) {
        step->batchable = batchable;
    }

    if (step->remove != nullptr) {
        step->remove = nullptr;
    }

    if (expl != "") {
        step->expl = expl;
        if (step->batch_id != "") {
            for (Step& batch_step : _state.get_batch_running_steps(step->batch_id)) {
                batch_step.expl = expl;
            }
        }
    }

    bool step_is_not_running = step->status != "RUNNING";
    bool step_started_a_run = status == "DONE" || status == "FAILED" || status == "RUNNING";
    bool running_on_this_worker = step->worker_running == worker_id;
    if (step_is_not_running || (step_started_a_run && running_on_this_worker) || !new_deps.empty()) {
        if (status != step->status || status == "PENDING") {
            _update_step_history(*step, status);
        }
        _state.set_status(*step, status == "SUSPENDED" ? "PENDING" : status, _config);
    }

    if (status == "FAILED" && _config.batch_emails) {
        std::vector<std::string> batched_params, _;
        std::tie(batched_params, _) = _state.get_batcher(worker_id, family);
        std::map<std::string, std::string> unbatched_params;
        if (!batched_params.empty()) {
            for (auto const& [param, value] : step->params) {
                if (std::find(batched_params.begin(), batched_params.end(), param) == batched_params.end()) {
                    unbatched_params[param] = value;
                }
            }
        } else {
            unbatched_params = step->params;
        }
        std::string expl_raw;
        try {
            expl_raw = json::parse(expl).dump();
        } catch (json::parse_error& e) {
            expl_raw = expl;
        }

        _email_batcher.add_failure(step->pretty_id, step->family, unbatched_params, expl_raw, owners);
        if (step->status == "DISABLED") {
            _email_batcher.add_disable(step->pretty_id, step->family, unbatched_params, owners);
        }
    }

    if (!deps.empty()) {
        step->deps = deps;
    }

    if (!new_deps.empty()) {
        step->deps.insert(step->deps.end(), new_deps.begin(), new_deps.end());
    }

    if (!resources.empty()) {
        step->resources = resources;
    }

    if (updated_worker.enabled && !assistant) {
        step->stakeholders.insert(worker_id);

        for (std::string& dep : step->deps) {
            Step* t = _state.get_step(dep, _make_step(dep, "UNKNOWN", {}, priority));
            t->stakeholders.insert(worker_id);
        }
    }

    _update_priority(*step, priority, worker_id);

    step->retry_policy = retry_policy;

    if (runnable && status != "FAILED" && updated_worker.enabled) {
        step->workers.insert(worker_id);
        _state.get_worker(worker_id)->steps.insert(step);
        step->runnable = runnable;
    }
}

void Scheduler::announce_scheduling_failure(std::string step_name, std::string family, std::map<std::string, std::string> params, std::string expl, std::vector<std::string> owners, std::map<std::string, std::string> kwargs) {
    if (!_config.batch_emails) {
        return;
    }
    int worker_id = std::stoi(kwargs["worker"]);
    std::vector<std::string> batched_params;
    std::tie(batched_params, std::ignore) = _state.get_batcher(worker_id, family);
    std::map<std::string, std::string> unbatched_params;
    if (!batched_params.empty()) {
        for (auto const& [param, value] : params) {
            if (std::find(batched_params.begin(), batched_params.end(), param) == batched_params.end()) {
                unbatched_params[param] = value;
            }
        }
    } else {
        unbatched_params = params;
    }
    _email_batcher.add_scheduling_fail(step_name, family, unbatched_params, expl, owners);
}

void Scheduler::add_worker(int worker, std::map<std::string, std::string> info, std::map<std::string, std::string> kwargs) {
    _state.get_worker(worker).add_info(info);
}

void Scheduler::disable_worker(int worker) {
    _state.disable_workers({worker});
}

void Scheduler::set_worker_processes(int worker, int n) {
    _state.get_worker(worker).add_rpc_message("set_worker_processes", n);
}

std::map<std::string, std::string> Scheduler::send_scheduler_message(int worker, std::string step, std::string content) {
    if (!_config.send_messages) {
        return {{"message_id", "None"}};
    }

    std::string message_id = boost::lexical_cast<std::string>(boost::uuids::random_generator()());
    _state.get_worker(worker).add_rpc_message("dispatch_scheduler_message", {{"step_id", step}, {"message_id", message_id}, {"content", content}});

    return {{"message_id", message_id}};
}

void Scheduler::add_scheduler_message_response(std::string step_id, std::string message_id, std::string response) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        step->scheduler_message_responses[message_id] = response;
    }
}

std::map<std::string, std::string> Scheduler::get_scheduler_message_response(std::string step_id, std::string message_id) {
    std::string response = "None";
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        response = step->scheduler_message_responses[message_id];
        step->scheduler_message_responses.erase(message_id);
    }
    return {{"response", response}};
}

bool Scheduler::has_step_history() {
    return _config.record_step_history;
}

std::map<std::string, bool> Scheduler::is_pause_enabled() {
    return {{"enabled", _config.pause_enabled}};
}

std::map<std::string, bool> Scheduler::is_paused() {
    return {{"paused", _paused}};
}

void Scheduler::pause() {
    if (_config.pause_enabled) {
        _paused = true;
    }
}

void Scheduler::unpause() {
    if (_config.pause_enabled) {
        _paused = false;
    }
}

void Scheduler::update_resources(std::map<std::string, int> resources) {
    if (_resources.empty()) {
        _resources = {};
    }
    _resources.insert(resources.begin(), resources.end());
}

bool Scheduler::update_resource(std::string resource, int amount) {
    if (!std::is_integral<decltype(amount)>::value || amount < 0) {
        return false;
    }
    _resources[resource] = amount;
    return true;
}

RetryPolicy Scheduler::_generate_retry_policy(std::map<std::string, std::string> step_retry_policy_dict) {
    std::map<std::string, std::string> retry_policy_dict = _config._get_retry_policy()._asdict();
    for (auto const& [k, v] : step_retry_policy_dict) {
        if (v != "None") {
            retry_policy_dict[k] = v;
        }
    }
    return RetryPolicy(retry_policy_dict);
}

bool Scheduler::_has_resources(std::map<std::string, int> needed_resources, std::map<std::string, int> used_resources) {
    if (needed_resources.empty()) {
        return true;
    }

    for (auto const& [resource, amount] : needed_resources) {
        if (amount + used_resources[resource] > _resources[resource]) {
            return false;
        }
    }
    return true;
}

std::map<std::string, int> Scheduler::_used_resources() {
    std::map<std::string, int> used_resources;
    if (!_resources.empty()) {
        for (auto const& step : _state.get_active_steps_by_status("RUNNING")) {
            std::map<std::string, int> resources_running = step.resources_running.empty() ? step.resources : step.resources_running;
            for (auto const& [resource, amount] : resources_running) {
                used_resources[resource] += amount;
            }
        }
    }
    return used_resources;
}

std::pair<int, double> Scheduler::_rank(Step& step) {
    return {step.priority, -step.time};
}

bool Scheduler::_schedulable(Step& step) {
    if (step.status != "PENDING") {
        return false;
    }
    for (auto const& dep : step.deps) {
        Step* dep_step = _state.get_step(dep, "None");
        if (dep_step == nullptr || dep_step->status != "DONE") {
            return false;
        }
    }
    return true;
}

void Scheduler::_reset_orphaned_batch_running_steps(int worker_id) {
    std::set<std::string> running_batch_ids;
    for (auto const& step : _state.get_active_steps_by_status("RUNNING")) {
        if (step.worker_running == worker_id) {
            running_batch_ids.insert(step.batch_id);
        }
    }
    for (auto const& step : _state.get_active_steps_by_status("BATCH_RUNNING")) {
        if (step.worker_running == worker_id && running_batch_ids.find(step.batch_id) == running_batch_ids.end()) {
            _state.set_status(step, "PENDING");
        }
    }
}

std::map<std::string, int> Scheduler::count_pending(int worker) {
    int worker_id = worker;
    Worker worker = _update_worker(worker_id);

    int num_pending = 0, num_unique_pending = 0, num_pending_last_scheduled = 0;
    std::vector<std::map<std::string, std::string>> running_steps;

    std::map<std::string, std::string> upstream_status_table;
    for (auto const& step : worker.get_steps(_state, "RUNNING")) {
        if (_upstream_status(step.id, upstream_status_table) == "UPSTREAM_DISABLED") {
            continue;
        }
        Worker* other_worker = _state.get_worker(step.worker_running);
        if (other_worker != nullptr) {
            std::map<std::string, std::string> more_info = {{"step_id", step.id}, {"worker", other_worker->to_string()}};
            more_info.insert(other_worker->info.begin(), other_worker->info.end());
            running_steps.push_back(more_info);
        }
    }

    for (auto const& step : worker.get_steps(_state, "PENDING", "FAILED")) {
        if (_upstream_status(step.id, upstream_status_table) == "UPSTREAM_DISABLED") {
            continue;
        }
        num_pending++;
        num_unique_pending += step.workers.size() == 1;
        num_pending_last_scheduled += *step.workers.rbegin() == worker_id;
    }

    return {
            {"n_pending_steps", num_pending},
            {"n_unique_pending", num_unique_pending},
            {"n_pending_last_scheduled", num_pending_last_scheduled},
            {"worker_state", worker.state},
            {"running_steps", running_steps.size()}
    };
}

std::map<std::string, std::string> Scheduler::get_work(std::string host = "", bool assistant = false, std::vector<std::string> current_steps = {}, int worker = 0, std::map<std::string, std::string> kwargs = {}) {
    if (_config.prune_on_get_work) {
        prune();
    }

    assert(worker != 0);
    int worker_id = worker;
    Worker updated_worker = _update_worker(worker_id, {{"host", host}}, true);
    if (!updated_worker.enabled) {
        return {
                {"n_pending_steps", "0"},
                {"running_steps", ""},
                {"step_id", ""},
                {"n_unique_pending", "0"},
                {"worker_state", updated_worker.state},
        };
    }

    if (assistant) {
        add_worker(worker_id, {{"assistant", assistant}});
    }

    std::vector<std::string> batched_params, unbatched_params, batched_steps;
    int max_batch_size = 1;
    Step* best_step = nullptr;
    if (current_steps.size() != 0) {
        std::set<std::string> ct_set(current_steps.begin(), current_steps.end());
        for (auto& step : _state.get_active_steps_by_status("RUNNING")) {
            if (step.worker_running == worker_id && ct_set.find(step.id) == ct_set.end()) {
                best_step = &step;
            }
        }
    }

    if (current_steps.size() != 0) {
        _reset_orphaned_batch_running_steps(worker_id);
    }

    std::map<std::string, int> greedy_resources;

    Worker* worker_ptr = _state.get_worker(worker_id);
    std::vector<Step*> relevant_steps;
    std::map<std::string, int> used_resources;
    std::map<int, int> greedy_workers;
    if (_paused) {
        relevant_steps = {};
    } else if (worker_ptr->is_trivial_worker(_state)) {
        relevant_steps = worker_ptr->get_steps(_state, "PENDING", "RUNNING");
        used_resources = {};
        greedy_workers = {};  // If there's no resources, then they can grab any step
    } else {
        relevant_steps = _state.get_active_steps_by_status("PENDING", "RUNNING");
        used_resources = _used_resources();
        int activity_limit = time(nullptr) - _config.worker_disconnect_delay;
        std::vector<Worker*> active_workers = _state.get_active_workers(activity_limit);
        for (auto& worker : active_workers) {
            greedy_workers[worker->id] = worker->info["workers"];
        }
    }
    std::vector<Step*> steps = relevant_steps;
    std::sort(steps.begin(), steps.end(), [this](Step* a, Step* b) { return _rank(*a) > _rank(*b); });

    for (auto& step : steps) {
        // ... continue the implementation based on the Python code
    }

    // ... continue the implementation based on the Python code

    return reply;
}
std::map<std::string, std::string> Scheduler::ping(std::map<std::string, std::string> kwargs) {
    int worker_id = std::stoi(kwargs["worker"]);
    Worker updated_worker = _update_worker(worker_id);
    return {{"rpc_messages", updated_worker.fetch_rpc_messages()}};
}

std::string Scheduler::_upstream_status(std::string step_id, std::map<std::string, std::string>& upstream_status_table) {
    if (upstream_status_table.find(step_id) != upstream_status_table.end()) {
        return upstream_status_table[step_id];
    } else if (_state.has_step(step_id)) {
        std::vector<std::string> step_stack = {step_id};

        while (!step_stack.empty()) {
            std::string dep_id = step_stack.back();
            step_stack.pop_back();
            Step* dep = _state.get_step(dep_id);
            if (dep) {
                if (dep->status == "DONE") {
                    continue;
                }
                if (upstream_status_table.find(dep_id) == upstream_status_table.end()) {
                    if (dep->status == "PENDING" && !dep->deps.empty()) {
                        step_stack.push_back(dep_id);
                        step_stack.insert(step_stack.end(), dep->deps.begin(), dep->deps.end());
                        upstream_status_table[dep_id] = "";  // will be updated postorder
                    } else {
                        std::string dep_status = STATUS_TO_UPSTREAM_MAP[dep->status];
                        upstream_status_table[dep_id] = dep_status;
                    }
                } else if (upstream_status_table[dep_id] == "" && !dep->deps.empty()) {
                    // This is the postorder update step when we set the
                    // status based on the previously calculated child elements
                    std::string status = *std::max_element(dep->deps.begin(), dep->deps.end(), [&](const std::string& a, const std::string& b) {
                        return UPSTREAM_SEVERITY_KEY[a] < UPSTREAM_SEVERITY_KEY[b];
                    });
                    upstream_status_table[dep_id] = status;
                }
            }
        }
        return upstream_status_table[dep_id];
    }
    return "";
}


std::map<std::string, std::string> Scheduler::_serialize_step(std::string step_id, bool include_deps=true, std::vector<std::string> deps={}) {
    Step* step = _state.get_step(step_id);

    std::map<std::string, std::string> ret = {
            {"display_name", step->pretty_id},
            {"status", step->status},
            // ... continue for the rest of the attributes
    };

    if (step->status == "DISABLED") {
        ret["re_enable_able"] = step->scheduler_disable_time != nullptr ? "true" : "false";
    }

    if (include_deps) {
        ret["deps"] = deps.empty() ? join(step->deps, ",") : join(deps, ",");
    }

    if (_config.send_messages && step->status == "RUNNING") {
        ret["accepts_messages"] = step->accepts_messages ? "true" : "false";
    }

    return ret;
}


std::map<std::string, std::map<std::string, std::string>> Scheduler::graph(std::map<std::string, std::string> kwargs) {
    this->prune();
    std::map<std::string, std::map<std::string, std::string>> serialized;
    std::set<std::string> seen;
    for (auto& step : _state.get_active_steps()) {
        std::map<std::string, std::map<std::string, std::string>> step_serialized = this->_traverse_graph(step.id, seen);
        serialized.insert(step_serialized.begin(), step_serialized.end());
    }
    return serialized;
}

std::vector<std::string> Scheduler::_filter_done(std::vector<std::string> step_ids) {
    std::vector<std::string> filtered_step_ids;
    for (const auto& step_id : step_ids) {
        Step* step = _state.get_step(step_id);
        if (step == nullptr || step->status != "DONE") {
            filtered_step_ids.push_back(step_id);
        }
    }
    return filtered_step_ids;
}


std::map<std::string, std::map<std::string, std::string>> Scheduler::_traverse_graph(std::string root_step_id, std::set<std::string>& seen, std::function<std::vector<std::string>(Step*)> dep_func = nullptr, bool include_done = true) {
    if (seen.find(root_step_id) != seen.end()) {
        return {};
    }

    if (dep_func == nullptr) {
        dep_func = [](Step* t) { return t->deps; };
    }

    seen.insert(root_step_id);
    std::map<std::string, std::map<std::string, std::string>> serialized;
    std::deque<std::string> queue = {root_step_id};
    while (!queue.empty()) {
        std::string step_id = queue.front();
        queue.pop_front();

        Step* step = _state.get_step(step_id);
        if (step == nullptr || step->family.empty()) {
            // ... continue the implementation based on the Python code
        } else {
            std::vector<std::string> deps = dep_func(step);
            if (!include_done) {
                deps = _filter_done(deps);
            }
            serialized[step_id] = _serialize_step(step_id, true, deps);
            for (auto& dep : deps) {
                if (seen.find(dep) == seen.end()) {
                    seen.insert(dep);
                    queue.push_back(dep);
                }
            }
        }

        if (step_id != root_step_id) {
            serialized[step_id].erase("display_name");
        }
        if (serialized.size() >= _config.max_graph_nodes) {
            break;
        }
    }

    return serialized;
}

std::map<std::string, std::map<std::string, std::string>> Scheduler::dep_graph(std::string step_id, bool include_done = true, std::map<std::string, std::string> kwargs = {}) {
    this->prune();
    if (!_state.has_step(step_id)) {
        return {};
    }
    return this->_traverse_graph(step_id, include_done);
}

std::map<std::string, std::set<std::string>> Scheduler::inverse_dep_graph(std::string step_id, bool include_done = true, std::map<std::string, std::string> kwargs = {}) {
    this->prune();
    if (!_state.has_step(step_id)) {
        return {};
    }
    std::map<std::string, std::set<std::string>> inverse_graph;
    for (auto& step : _state.get_active_steps()) {
        for (auto& dep : step.deps) {
            inverse_graph[dep].insert(step.id);
        }
    }
    return this->_traverse_graph(step_id, [&](Step* t) { return std::vector<std::string>(inverse_graph[t->id].begin(), inverse_graph[t->id].end()); }, include_done);
}

std::map<std::string, std::map<std::string, std::string>> Scheduler::step_list(std::string status = "", std::string upstream_status = "", bool limit = true, std::string search = "", int max_shown_steps = 0, std::map<std::string, std::string> kwargs = {}) {
    if (search.empty()) {
        int count_limit = max_shown_steps ? max_shown_steps : _config.max_shown_steps;
        int pre_count = _state.get_active_step_count_for_status(status);
        if (limit && pre_count > count_limit) {
            return {{"num_steps", upstream_status.empty() ? std::to_string(pre_count) : "-1"}};
        }
    }
    this->prune();

    std::map<std::string, std::map<std::string, std::string>> result;
    std::map<std::string, std::string> upstream_status_table;  // used to memoize upstream status
    std::vector<std::string> terms;
    if (!search.empty()) {
        std::istringstream iss(search);
        for(std::string s; iss >> s; )
            terms.push_back(s);
    }

    std::vector<Step*> steps = !status.empty() ? _state.get_active_steps_by_status(status) : _state.get_active_steps();
    for (auto& step : steps) {
        if (search.empty() || std::all_of(terms.begin(), terms.end(), [&](std::string term) { return step->pretty_id.find(term) != std::string::npos; })) {
            if (step->status != "PENDING" || upstream_status.empty() || upstream_status == _upstream_status(step->id, upstream_status_table)) {
                result[step->id] = _serialize_step(step->id, false);
            }
        }
    }
    if (limit && result.size() > (max_shown_steps ? max_shown_steps : _config.max_shown_steps)) {
        return {{"num_steps", std::to_string(result.size())}};
    }
    return result;
}

std::string Scheduler::_first_step_display_name(Worker& worker) {
    std::string step_id = worker.info["first_step"];
    if (_state.has_step(step_id)) {
        return _state.get_step(step_id)->pretty_id;
    } else {
        return step_id;
    }
}

std::vector<std::map<std::string, std::string>> Scheduler::worker_list(bool include_running = true, std::map<std::string, std::string> kwargs = {}) {
    this->prune();
    std::vector<std::map<std::string, std::string>> workers;
    for (auto& worker : _state.get_active_workers()) {
        workers.push_back({
                                  {"name", worker.id},
                                  {"last_active", std::to_string(worker.last_active)},
                                  {"started", std::to_string(worker.started)},
                                  {"state", worker.state},
                                  {"first_step_display_name", _first_step_display_name(worker)},
                                  {"num_unread_rpc_messages", std::to_string(worker.rpc_messages.size())},
                                  // ... add worker.info entries here
                          });
    }
    std::sort(workers.begin(), workers.end(), [](const std::map<std::string, std::string>& a, const std::map<std::string, std::string>& b) {
        return std::stoi(a.at("started")) > std::stoi(b.at("started"));
    });

    if (include_running) {
        std::map<std::string, std::map<std::string, std::string>> running;
        for (auto& step : _state.get_active_steps_by_status("RUNNING")) {
            if (step.worker_running != "") {
                running[step.worker_running][step.id] = _serialize_step(step.id, false);
            }
        }

        std::map<std::string, int> num_pending;
        std::map<std::string, int> num_uniques;
        for (auto& step : _state.get_active_steps_by_status("PENDING")) {
            for (auto& worker : step.workers) {
                num_pending[worker]++;
            }
            if (step.workers.size() == 1) {
                num_uniques[*step.workers.begin()]++;
            }
        }

        for (auto& worker : workers) {
            std::map<std::string, std::string> steps = running[worker["name"]];
            worker["num_running"] = std::to_string(steps.size());
            worker["num_pending"] = std::to_string(num_pending[worker["name"]]);
            worker["num_uniques"] = std::to_string(num_uniques[worker["name"]]);
            // ... add steps to worker here
        }
    }
    return workers;
}

std::vector<std::map<std::string, std::string>> Scheduler::resource_list() {
    this->prune();
    std::vector<std::map<std::string, std::string>> resources;
    for (auto& [resource, r_dict] : this->resources()) {
        resources.push_back({
                                    {"name", resource},
                                    {"num_total", std::to_string(r_dict["total"])},
                                    {"num_used", std::to_string(r_dict["used"])}
                            });
    }
    if (!_resources.empty()) {
        std::map<std::string, std::map<std::string, std::string>> consumers;
        for (auto& step : _state.get_active_steps_by_status("RUNNING")) {
            if (step.status == "RUNNING" && !step.resources.empty()) {
                for (auto& [resource, amount] : step.resources) {
                    consumers[resource][step.id] = _serialize_step(step.id, false);
                }
            }
        }
        for (auto& resource : resources) {
            std::map<std::string, std::string> steps = consumers[resource["name"]];
            resource["num_consumer"] = std::to_string(steps.size());
            // ... add steps to resource here
        }
    }
    return resources;
}


std::map<std::string, std::map<std::string, int>> Scheduler::resources() {
    std::map<std::string, int> used_resources = this->_used_resources();
    std::map<std::string, std::map<std::string, int>> ret;
    for (auto& [resource, total] : _resources) {
        ret[resource]["total"] = total;
        if (used_resources.find(resource) != used_resources.end()) {
            ret[resource]["used"] = used_resources[resource];
        } else {
            ret[resource]["used"] = 0;
        }
    }
    return ret;
}

std::map<std::string, std::map<std::string, std::map<std::string, std::string>>> Scheduler::step_search(std::string step_str, std::map<std::string, std::string> kwargs = {}) {
this->prune();
std::map<std::string, std::map<std::string, std::map<std::string, std::string>>> result;
for (auto& step : _state.get_active_steps()) {
if (step.id.find(step_str) != std::string::npos) {
std::map<std::string, std::string> serialized = _serialize_step(step.id, false);
result[step.status][step.id] = serialized;
}
}
return result;
}

std::map<std::string, std::string> Scheduler::re_enable_step(std::string step_id) {
    std::map<std::string, std::string> serialized;
    Step* step = _state.get_step(step_id);
    if (step != nullptr && step->status == "DISABLED" && step->scheduler_disable_time != 0) {
        _state.re_enable(*step, _config);
        serialized = _serialize_step(step_id);
    }
    return serialized;
}

std::map<std::string, std::string> Scheduler::fetch_error(std::string step_id, std::map<std::string, std::string> kwargs = {}) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        return {
                {"stepId", step_id},
                {"error", step->expl},
                {"displayName", step->pretty_id},
                {"stepParams", step->params}, // Assuming params is a string
                {"stepModule", step->module},
                {"stepFamily", step->family}
        };
    } else {
        return {{"stepId", step_id}, {"error", ""}};
    }
}

void Scheduler::set_step_status_message(std::string step_id, std::string status_message) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        step->status_message = status_message;
        if (step->status == "RUNNING" && !step->batch_id.empty()) {
            for (auto& batch_step : _state.get_batch_running_steps(step->batch_id)) {
                batch_step.status_message = status_message;
            }
        }
    }
}


std::map<std::string, std::string> Scheduler::get_step_status_message(std::string step_id) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        return {{"stepId", step_id}, {"statusMessage", step->status_message}};
    } else {
        return {{"stepId", step_id}, {"statusMessage", ""}};
    }
}

void Scheduler::set_step_progress_percentage(std::string step_id, double progress_percentage) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        step->progress_percentage = progress_percentage;
        if (step->status == "RUNNING" && !step->batch_id.empty()) {
            for (auto& batch_step : _state.get_batch_running_steps(step->batch_id)) {
                batch_step.progress_percentage = progress_percentage;
            }
        }
    }
}

std::map<std::string, std::string> Scheduler::get_step_progress_percentage(std::string step_id) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        return {{"stepId", step_id}, {"progressPercentage", std::to_string(step->progress_percentage)}};
    } else {
        return {{"stepId", step_id}, {"progressPercentage", "None"}};
    }
}

void Scheduler::decrease_running_step_resources(std::string step_id, std::map<std::string, int> decrease_resources) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        if (step->status != "RUNNING") {
            return;
        }

        auto decrease = [](std::map<std::string, int>& resources, const std::map<std::string, int>& decrease_resources) {
            for (const auto& [resource, decrease_amount] : decrease_resources) {
                if (decrease_amount > 0 && resources.find(resource) != resources.end()) {
                    resources[resource] = std::max(0, resources[resource] - decrease_amount);
                }
            }
        };

        decrease(step->resources_running, decrease_resources);
        if (!step->batch_id.empty()) {
            for (auto& batch_step : _state.get_batch_running_steps(step->batch_id)) {
                decrease(batch_step.resources_running, decrease_resources);
            }
        }
    }
}
std::map<std::string, std::string> Scheduler::get_running_step_resources(std::string step_id) {
    if (_state.has_step(step_id)) {
        Step* step = _state.get_step(step_id);
        std::string resources = step->resources_running.empty() ? "None" : step->resources_running;
        return {{"stepId", step_id}, {"resources", resources}};
    } else {
        return {{"stepId", step_id}, {"resources", "None"}};
    }
}

void Scheduler::_update_step_history(Step& step, std::string status, std::string host = "") {
    try {
        if (status == "DONE" || status == "FAILED") {
            bool successful = (status == "DONE");
            _step_history.step_finished(step, successful);
        } else if (status == "PENDING") {
            _step_history.step_scheduled(step);
        } else if (status == "RUNNING") {
            _step_history.step_started(step, host);
        }
    } catch (const std::exception& e) {
        logger.warning("Error saving Step history", e.what());
    }
}

StepHistory& Scheduler::get_step_history() {
    return _step_history;
}


void Scheduler::update_metrics_step_started(Step& step) {
    _state._metrics_collector.handle_step_started(step);
}

