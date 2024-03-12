#ifndef SCHEDULER_H
#define SCHEDULER_H

#include <map>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <string>
#include <functional>
#include "StepHistory.h" // Assuming StepHistory is defined in this header file

struct RetryPolicy {
    int retry_count;
    bool disable_hard_timeout;
    bool disable_window;
    std::map<std::string, int> asDict() const {
        return {
                {"retry_count", retry_count},
                {"disable_hard_timeout", disable_hard_timeout ? 1 : 0},
                {"disable_window", disable_window ? 1 : 0}
        };
    }
};

class scheduler; // Forward declaration

class Scheduler {
public:
    Scheduler(scheduler* config, std::map<std::string, int> resources, StepHistory* step_history_impl, std::map<std::string, std::string> kwargs);
    void load();
    void dump();
    std::map<std::string, std::string> _serialize_step(std::string step_id, bool include_deps=true, std::vector<std::string> deps={});
    std::map<std::string, std::map<std::string, std::string>> graph(std::map<std::string, std::string> kwargs);
    std::vector<std::string> _filter_done(std::vector<std::string> step_ids);
    std::map<std::string, std::map<std::string, std::string>> _traverse_graph(std::string root_step_id, std::set<std::string>& seen, std::function<std::vector<std::string>(Step*)> dep_func = nullptr, bool include_done = true);
    std::map<std::string, std::map<std::string, std::string>> dep_graph(std::string step_id, bool include_done = true, std::map<std::string, std::string> kwargs = {});
    std::map<std::string, std::set<std::string>> inverse_dep_graph(std::string step_id, bool include_done = true, std::map<std::string, std::string> kwargs = {});
    std::map<std::string, std::map<std::string, std::string>> step_list(std::string status = "", std::string upstream_status = "", bool limit = true, std::string search = "", int max_shown_steps = 0, std::map<std::string, std::string> kwargs = {});
    std::string _first_step_display_name(Worker& worker);
    std::vector<std::map<std::string, std::string>> worker_list(bool include_running = true, std::map<std::string, std::string> kwargs = {});
    std::vector<std::map<std::string, std::string>> resource_list();
    std::map<std::string, std::map<std::string, int>> resources();
    std::map<std::string, std::map<std::string, std::map<std::string, std::string>>> step_search(std::string step_str, std::map<std::string, std::string> kwargs = {});
    std::map<std::string, std::string> re_enable_step(std::string step_id);
    std::map<std::string, std::string> fetch_error(std::string step_id, std::map<std::string, std::string> kwargs = {});
    void set_step_status_message(std::string step_id, std::string status_message);
    std::map<std::string, std::string> get_step_status_message(std::string step_id);
    void set_step_progress_percentage(std::string step_id, double progress_percentage);
    std::map<std::string, std::string> get_step_progress_percentage(std::string step_id);
    void decrease_running_step_resources(std::string step_id, std::map<std::string, int> decrease_resources);
    std::map<std::string, std::string> get_running_step_resources(std::string step_id);
    void _update_step_history(Step& step, std::string status, std::string host = "");
    StepHistory& get_step_history();
    void update_metrics_step_started(Step& step);

private:
    // Private members and methods go here
};

#endif // SCHEDULER_H