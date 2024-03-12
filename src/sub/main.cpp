#include <string>
#include <map>
#include <vector>
#include <functional>
#include <iostream>
#include <vector>
#include <map>
#include <optional>
#include <variant>
#include <memory>
#include <algorithm>
#include <numeric>
#include <functional>
#include <stdexcept>
#include <tuple>
#include <sstream>
#include <string>
#include <map>
#include <regex>
#include <algorithm>
#include <openssl/md5.h>
#include "command_line_processor.h"
#include "step.h"

std::string join(const std::vector<std::string>& vec, const char* delim) {
    std::ostringstream os;
    std::copy(vec.begin(), vec.end() - 1, std::ostream_iterator<std::string>(os, delim));
    os << *vec.rbegin();  // Copy the last element without a trailing delimiter
    return os.str();
}


std::map<std::string, std::string> default_namespace_dict;

void namespace_func(std::string namespace_str = "", std::string scope = "") {
    default_namespace_dict[scope] = namespace_str;
}

void auto_namespace(std::string scope = "") {
    namespace_func(SAME_AS_CPP_MODULE, scope);
}

std::string step_id_str(std::string step_family, std::map<std::string, std::string> params) {
    // Sort params by key
    std::vector<std::pair<std::string, std::string>> params_vec(params.begin(), params.end());
    std::sort(params_vec.begin(), params_vec.end());

    // Concatenate first values of the first 3 parameters
    std::string param_summary;
    for (int i = 0; i < STEP_ID_INCLUDE_PARAMS && i < params_vec.size(); ++i) {
        param_summary += params_vec[i].second.substr(0, STEP_ID_TRUNCATE_PARAMS) + "_";
    }

    // Replace invalid characters
    param_summary = std::regex_replace(param_summary, STEP_ID_INVALID_CHAR_REGEX, "_");

    // Compute MD5 hash of the concatenated string
    unsigned char digest[MD5_DIGEST_LENGTH];
    MD5((unsigned char*)param_summary.c_str(), param_summary.size(), (unsigned char*)&digest);

    char mdString[33];
    for (int i = 0; i < 16; i++)
        sprintf(&mdString[i*2], "%02x", (unsigned int)digest[i]);

    std::string param_hash(mdString);
    param_hash = param_hash.substr(0, STEP_ID_TRUNCATE_HASH);

    return step_family + "_" + param_summary + "_" + param_hash;
}

bool Step::batchable() {
    // Implement logic to check if the step is batchable
    // For example, return true if there are any batched parameters
    return !batch_param_names().empty();
}
int Step::getRetryCount() {
    // Implement logic to get retry count
    // For example, return a member variable that stores the retry count
    return retry_count;
}
int Step::getDisableHardTimeout() {
    // Implement logic to get disable_hard_timeout
    // For example, return a member variable that stores the disable_hard_timeout
    return disable_hard_timeout;
}
int Step::getDisableWindow() {
    // Implement logic to get disable_window
    // For example, return a member variable that stores the disable_window
    return disable_window;
}
std::vector<std::string> Step::getOwnerEmail() {
    // Implement logic to get owner_email
    // For example, return a member variable that stores the owner_email
    return owner_email;
}
std::vector<std::string> Step::_owner_list() {
    // Turns the owner_email property into a list. This should not be overridden.
    std::vector<std::string> owner_list;
    if (owner_email.empty()) {
        return owner_list;
    } else {
        std::stringstream ss(owner_email);
        std::string token;
        while (std::getline(ss, token, ',')) {
            owner_list.push_back(token);
        }
        return owner_list;
    }
}
bool Step::getUseCmdlineSection() {
    // Implement logic to get use_cmdline_section
    // For example, return a member variable that stores the use_cmdline_section
    return use_cmdline_section;
}

static std::function<void()> Step::event_handler(std::string event, std::function<void()> callback) {
    _event_callbacks[event].insert(callback);
    return callback;
}

std::map<std::string, std::set<std::function<void()>>> Step::event_callbacks;
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

bool Step::getAcceptsMessages() {
    // Implement logic to get accepts_messages
    // For example, return a member variable that stores the accepts_messages
    return accepts_messages;
}

std::string Step::getStepModule() {
    // Implement logic to get step_module
    // For example, return a member variable that stores the step_module
    return step_module;
}

static std::string Step::getStepNamespace() {
    if (step_namespace != not_user_specified) {
        return step_namespace;
    } else if (namespace_at_class_time == SAME_AS_CPP_NAMESPACE) {
        return "Step"; // Replace "Step" with the actual namespace of the Step class
    }
    return namespace_at_class_time;
}

// Initialize static members
std::string Step::step_namespace = "";
const std::string Step::not_user_specified = "";
const std::string Step::namespace_at_class_time = "";
const std::string Step::SAME_AS_CPP_NAMESPACE = "";

std::string Step::getStepFamily() {
    // Implement logic to get step_family
    // For example, return a member variable that stores the step_family
    return step_family;
}

// this should go inside Registerer
static std::string Step::get_step_family() {
    if (step_namespace.empty()) {
        return class_name;
    } else {
        return step_namespace + "." + class_name;
    }
}


// Initialize static members
std::string Step::step_namespace = "";
std::string Step::class_name = "Step"; // Replace "Step" with the actual class name
static std::vector<std::pair<std::string, Parameter>> Step::get_params() {
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

bool initialized();

void _warn_on_wrong_param_types();

std::map<std::string, std::string> to_str_params(bool only_significant, bool only_public);

static std::vector<std::string> Step::batch_param_names() {
    std::vector<std::string> batchable_param_names;
    std::vector<std::pair<std::string, Parameter>> params = get_params();
    for (const auto& param : params) {
        if (param.second.is_batchable()) { // Assuming Parameter class has a method is_batchable()
            batchable_param_names.push_back(param.first);
        }
    }
    return batchable_param_names;
}


static std::vector<std::string> Step::get_param_names(bool include_significant = false) {
    std::vector<std::string> param_names;
    std::vector<std::pair<std::string, Parameter>> params = get_params();

    for (const auto& param : params) {
        if (include_significant || param.second.is_significant()) { // Assuming Parameter class has a method is_significant()
            param_names.push_back(param.first);
        }
    }

    return param_names;
}

std::vector<std::pair<std::string, std::string>> Step::get_param_values(std::vector<std::pair<std::string, Parameter>> params, std::vector<std::string> args, std::map<std::string, std::string> kwargs) {
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
            if (!param_obj.has_step_value(step_family, param_name)) {
                // Assuming Parameter class has a method has_step_value()
                throw std::invalid_argument("Missing parameter " + param_name);
            }
            result[param_name] = param_obj.step_value(step_family, param_name);
            // Assuming Parameter class has a method step_value()
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

    bool Step::initialized() {
        return !step_id.empty();
    }

    std::map<std::string, std::string> param_kwargs;
    std::map<std::string, Parameter> params;

    void Step::_warn_on_wrong_param_types() {
        for (const auto& param : param_kwargs) {
            std::string param_name = param.first;
            std::string param_value = param.second;
            if (params.find(param_name) != params.end()) {
                params[param_name]._warn_on_wrong_param_type(param_name, param_value); // Assuming Parameter class has a method _warn_on_wrong_param_type()
            }
        }
    }

    Step Step::from_str_params(std::map<std::string, std::string> params_str) {
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
        // A Step will only run if all the Steps that it requires are completed.
        // If your Step does not require any other Steps, then you don't need to
        // override this method. Otherwise, a subclass can override this method
        // to return vector of Step instances

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
}

virtual std::string Step::on_failure(const std::exception& e) {
    // Override for custom error handling.
    // This method gets called if an exception is raised in run().

    // Default behavior is to return a string representation of the stack trace.

    std::stringstream ss;
    ss << "Runtime error:\n" << e.what();
    return ss.str();
}

virtual std::string Step::on_success() {
    // This method gets called when run() completes without raising any exceptions.
    // This is a default implementation that does nothing.
    return "";
}

class MyStep : public Step {
public:
    void run() override {
        // Provide an implementation for the run method
        std::cout << "Running MyStep" << std::endl;
    }
    std::map<std::string, std::string> getParams() override {
        // Provide an implementation for the getParams method
        return std::map<std::string, std::string>();
    }
};

class StepRegister {
public:
    static void add(std::string name, std::shared_ptr<Step> step) {
        registry[name] = step;
    }

    static std::shared_ptr<Step> get(std::string name) {
        return registry[name];
    }

private:
    static std::map<std::string, std::shared_ptr<Step>> registry;
};

std::map<std::string, std::shared_ptr<Step>> StepRegister::registry = {};

class StepFactory {
public:
    // Placeholder denoting an error
    static const std::shared_ptr<Step> AMBIGUOUS_CLASS;

    // Cache instances of objects
    static std::map<std::tuple<std::string, std::vector<std::string>>, std::shared_ptr<Step>> instanceCache;

    // Keep track of all subclasses of Step
    static std::vector<std::shared_ptr<Step>> reg;

    // Default namespace dict
    static std::map<std::string, std::string> defaultNamespaceDict;

    template <typename T>
    static void registerType(const std::string& type) {
        creators[type] = [type]() { // capture 'type' by value
            auto it = instance_cache.find(type);
            if (it != instance_cache.end()) {
                return it->second;
            } else {
                std::shared_ptr<Step> instance = std::make_shared<T>();
                instance_cache[type] = instance;
                return instance;
            }
        };
    }

    template <typename... Args>
    static std::shared_ptr<Step> create(const std::string& name, Args... args) {
        auto it = instanceCache.find(std::make_tuple(name, args...));
        if (it != instanceCache.end()) {
            return it->second;
        }

        auto creatorIt = creators.find(name);
        if (creatorIt == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }

        std::shared_ptr<Step> instance = creatorIt->second(args...);
        instanceCache[std::make_tuple(name, args...)] = instance;
        return instance;
    }

    static std::shared_ptr<Step> createInstance(const std::string& type) {
        return creators[type]();
    }

    static std::string stepFamily(const std::string& name) {
        auto it = creators.find(name);
        if (it == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }
        std::string stepNamespace = ""; // Replace with actual namespace retrieval if needed
        if (stepNamespace.empty()) {
            return name;
        } else {
            return stepNamespace + "." + name;
        }
    }

    static std::vector<std::string> stepNames() {
        std::vector<std::string> names;
        for (const auto& pair : creators) {
            names.push_back(pair.first);
        }
        std::sort(names.begin(), names.end());
        return names;
    }

    static std::string stepsStr() {
        std::string result;
        for (const auto& pair : creators) {
            if (!result.empty()) {
                result += ",";
            }
            result += pair.first;
        }
        return result;
    }
    static void clearInstanceCache() {
        instanceCache.clear();
    }

    static void disableInstanceCache() {
        instanceCacheEnabled = false;
    }

    static std::shared_ptr<Step> getStepCls(const std::string& name) {
        auto it = creators.find(name);
        if (it == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }
        if (it->second == nullptr) { // Assuming nullptr is used to mark ambiguous classes
            throw std::runtime_error("Step class is ambiguous: " + name);
        }
        return it->second();
    }

    static std::map<std::string, std::map<std::string, std::string>> getAllParams() {
        std::map<std::string, std::map<std::string, std::string>> allParams;
        for (const auto& pair : creators) {
            std::shared_ptr<Step> instance = pair.second();
            allParams[pair.first] = instance->getParams();
        }
        return allParams;
    }

    static std::map<std::string, std::shared_ptr<Step>> getReg() {
        std::map<std::string, std::shared_ptr<Step>> reg;
        for (const auto& pair : creators) {
            if (!pair.second) { // Assuming nullptr is used to mark invisible classes
                continue;
            }
            std::string name = pair.first;
            std::shared_ptr<Step> stepInstance = pair.second();
            if (reg.count(name) > 0 &&
                (reg[name] == nullptr ||
                 !std::dynamic_pointer_cast<MyStep>(stepInstance))) {
                // Registering two different classes - this means we can't instantiate them by name
                // The only exception is if one class is a subclass of the other. In that case, we
                // instantiate the most-derived class (this fixes some issues with decorator wrappers).
                reg[name] = nullptr;
            } else {
                std::shared_ptr<Step> stepInstance = pair.second();
                reg[name] = stepInstance;
            }
        }
        return reg;
    }

    static int editDistance(const std::string& a, const std::string& b) {
        std::vector<int> r0(b.size() + 1);
        std::iota(r0.begin(), r0.end(), 0);
        std::vector<int> r1(b.size() + 1);

        for (size_t i = 0; i < a.size(); ++i) {
            r1[0] = i + 1;

            for (size_t j = 0; j < b.size(); ++j) {
                int c = (a[i] == b[j]) ? 0 : 1;
                r1[j + 1] = std::min({r1[j] + 1, r0[j + 1] + 1, r0[j] + c});
            }
            r0 = r1;
        }

        return r1[b.size()];
    }

    static std::string missingStepMsg(const std::string& stepName) {
        std::vector<std::pair<int, std::string>> weightedSteps;
        for (const auto& stepName2 : stepNames()) {
            weightedSteps.emplace_back(editDistance(stepName, stepName2), stepName2);
        }
        std::sort(weightedSteps.begin(), weightedSteps.end());

        std::vector<std::string> candidates;
        for (const auto& [dist, step] : weightedSteps) {
            if (dist <= 5 && dist < step.size()) {
                candidates.push_back(step);
            }
        }

        if (!candidates.empty()) {
            return "No step " + stepName + ". Did you mean:\n" + join(candidates, "\n");
        } else {
            return "No step " + stepName + ". Candidates are: " + stepsStr();
        }
    }

    static std::string getNamespace(const std::string& moduleName) {
        for (const auto& parent : moduleParents(moduleName)) {
            auto it = defaultNamespaceDict.find(parent);
            if (it != defaultNamespaceDict.end()) {
                return it->second;
            }
        }
        return "";
    }

    static std::vector<std::string> moduleParents(const std::string& moduleName) {
        std::vector<std::string> parents;
        size_t pos = 0;
        std::string token;
        std::string s = moduleName;
        while ((pos = s.find(".")) != std::string::npos) {
            token = s.substr(0, pos);
            parents.push_back(token);
            s.erase(0, pos + 1);
        }
        parents.push_back(s);
        std::reverse(parents.begin(), parents.end());
        return parents;
    }

    static void setReg(const std::map<std::string, std::shared_ptr<Step>>& reg) {
        creators.clear();
        for (const auto& pair : reg) {
            if (pair.second != nullptr) {
                creators[pair.first] = [pair]() { return pair.second; };
            }
        }
    }

private:
//    static std::map<std::string, std::function<std::shared_ptr<Step>(Args...)>> creators;
    static std::map<std::string, std::function<std::shared_ptr<Step>()>> creators;
    static std::map<std::string, std::shared_ptr<Step>> instance_cache;
    static bool instanceCacheEnabled;
};

std::map<std::string, std::function<std::shared_ptr<Step>()>> StepFactory::creators = {};
std::map<std::string, std::shared_ptr<Step>> StepFactory::instance_cache = {};


class CmdlineParser {
private:
    static std::optional<CmdlineParser> instance;
    std::map<std::string, std::variant<int, double, std::string>> known_args;

public:
    static CmdlineParser& get_instance() {
        if (!instance) {
            throw std::logic_error("Instance not created");
        }
        return *instance;
    }

    static void create_instance(const std::vector<std::string>& cmdline_args) {
        if (instance) {
            throw std::logic_error("Instance already created");
        }
        instance.emplace(cmdline_args);
    }

    CmdlineParser(const std::vector<std::string>& cmdline_args) {
        // Parse cmdline_args and populate known_args
        for (const auto& arg : cmdline_args) {
            // Parse argument and add to known_args
            // This is a placeholder and needs to be replaced with actual parsing logic
            known_args[arg] = arg;
        }
    }

    static void build_parser(CommandLineProcessor& cmdProcessor, std::string root_step = "", bool help_all = false) {
        cmdProcessor.addOption("root_step", "Step family to run. Is not optional.");

        auto allParams = StepFactory::getAllParams();
        for (auto& param : allParams) {
            std::string step_name = param.first;
            auto param_obj = param.second;

            for(auto& p : param_obj) {
                std::string param_name = p.first;
                std::string help = p.second;

                // Replace underscores with hyphens in the option name
                std::replace(param_name.begin(), param_name.end(), '_', '-');

                std::string flag_name_underscores = step_name + "_" + param_name;
                std::string global_flag_name = "--" + flag_name_underscores;

                cmdProcessor.addOption(global_flag_name, help);
            }
        }
    }

    std::variant<int, double, std::string> get_arg(const std::string& arg_name) {
        if (known_args.find(arg_name) == known_args.end()) {
            throw std::invalid_argument("Unknown argument: " + arg_name);
        }
        return known_args[arg_name];
    }

//    std::shared_ptr<Step> get_step_obj() {
//        std::string root_step = std::get<std::string>(get_arg("root_step"));
//        std::shared_ptr<Step> step = StepFactory::getStepCls(root_step);
//        step->someMethod();  // Replace 'someMethod' with the actual method name
//    }
//
//    std::function<std::shared_ptr<Step>()> _get_step_cls() {
//        std::string root_step = std::get<std::string>(get_arg("root_step"));
//        return StepFactory::getStepCls(root_step);
//    }


    std::map<std::string, std::string> _get_step_kwargs() {
        std::string root_step = std::get<std::string>(get_arg("root_step"));
        auto step_params = StepFactory::getAllParams()[root_step];
        std::map<std::string, std::string> step_kwargs;
        for (const auto& param : step_params) {
            if (known_args.count(param.first) > 0) {
                step_kwargs[param.first] = std::get<std::string>(known_args[param.first]);
            }
        }
        return step_kwargs;
    }
    void _possibly_exit_with_help(CommandLineProcessor& cmdProcessor) {
        if (known_args.count("help") > 0 || known_args.count("help_all") > 0) {
            cmdProcessor.printHelp();
            std::exit(0);
        }
    }
};

std::optional<CmdlineParser> CmdlineParser::instance = std::nullopt;



int main1() {
    // Register the step type
    StepFactory::registerType<MyStep>("MyStep");

    std::cout << "Hello, World!" << std::endl;
    return 0;
}
int main() {
    // Register the step type
    StepFactory::registerType<MyStep>("MyStep");

    // Create an instance of MyStep using the factory
    std::shared_ptr<Step> myStepInstance = StepFactory::createInstance("MyStep");

    // Add the instance to the StepRegister
    StepRegister::add("MyStep", myStepInstance);

    // Retrieve the instance from the StepRegister
    std::shared_ptr<Step> retrievedStep = StepRegister::get("MyStep");

    // Run the retrieved step
    retrievedStep->run();

    return 0;
}