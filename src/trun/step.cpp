#include <string>
#include <map>
#include <regex>
#include <algorithm>
#include <openssl/md5.h>

const int STEP_ID_INCLUDE_PARAMS = 3;
const int STEP_ID_TRUNCATE_PARAMS = 16;
const int STEP_ID_TRUNCATE_HASH = 10;
const std::regex STEP_ID_INVALID_CHAR_REGEX("[^A-Za-z0-9_]");
const std::string SAME_AS_CPP_MODULE = "_same_as_cpp_module";

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

class BulkCompleteNotImplementedError : public std::logic_error {
public:
    BulkCompleteNotImplementedError(const std::string& what_arg) : std::logic_error(what_arg) {}
};

#include <string>
#include <map>
#include <vector>
#include <functional>

class Step {
public:
    // Member variables
    static std::map<std::string, std::vector<std::function<void()>>> event_callbacks;
    int priority = 0;
    bool disabled = false;
    std::map<std::string, int> resources;

    // Member functions
    Step() {}
    virtual ~Step() {}

    virtual bool batchable() {
        // Implement logic to check if instance can be run as part of a batch
        return false;
    }

    virtual int disable_window() {
        // Implement logic to override disable_window at step level
        return 0;
    }

    static void event_handler(std::string event, std::function<void()> callback) {
        event_callbacks[event].push_back(callback);
    }

    void trigger_event(std::string event) {
        for (auto& callback : event_callbacks[event]) {
            callback();
        }
    }

    virtual bool accepts_messages() {
        return false;
    }
};
