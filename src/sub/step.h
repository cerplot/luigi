#pragma once
#include <string>
#include <map>
#include <vector>
#include <functional>
#include <limits>
#include <regex>
const int STEP_ID_INCLUDE_PARAMS = 3;
const int STEP_ID_TRUNCATE_PARAMS = 16;
const int STEP_ID_TRUNCATE_HASH = 10;
const std::regex STEP_ID_INVALID_CHAR_REGEX("[^A-Za-z0-9_]");
const std::string SAME_AS_CPP_MODULE = "_same_as_cpp_module";

class Step {
public:
    // Member variables
    static std::map<std::string, std::vector<std::function<void()>>> event_callbacks;
    int priority = 0;
    bool disabled = false;
    std::map<std::string, int> resources;
    int worker_timeout = 0;
    int max_batch_size = std::numeric_limits<int>::max();
    std::string owner_email = "";
    int retry_count = 0;
    int disable_hard_timeout = 0;
    int disable_window = 0;

    static std::string step_namespace;
    static const std::string not_user_specified;
    static const std::string namespace_at_class_time;
    static const std::string SAME_AS_CPP_NAMESPACE;

    static std::string _step_namespace;
    static std::string class_name;


    Step();
    virtual ~Step();
    virtual bool batchable();
    virtual int getRetryCount();
    virtual int getDisableHardTimeout();
    virtual int getDisableWindow();
    static void event_handler(std::string event, std::function<void()> callback);
    void trigger_event(std::string event);
    virtual bool accepts_messages();
    virtual std::string step_module();
    virtual std::string step_namespace();
    virtual std::string step_family();
    virtual bool complete();
    virtual void run();

    std::vector<std::string> _owner_list();

    bool use_cmdline_section();

    std::string get_step_family();
};