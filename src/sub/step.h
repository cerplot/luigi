#pragma once
class Step {
public:
    // Member variables
    static std::map<std::string, std::vector<std::function<void()>>> event_callbacks;
    int priority = 0;
    bool disabled = false;
    std::map<std::string, int> resources;
    int worker_timeout = 0;
    float max_batch_size = std::numeric_limits<float>::infinity();
    std::string owner_email = "";

    static std::string step_namespace;
    static const std::string not_user_specified;
    static const std::string namespace_at_class_time;
    static const std::string SAME_AS_CPP_NAMESPACE;

    static std::string step_namespace;
    static std::string class_name;

    Step();
    virtual ~Step();
    virtual bool batchable();
    virtual int retry_count();
    virtual int disable_hard_timeout();
    virtual int disable_window();
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