#include <string>
#include <vector>
#include <cstdlib>  // for system function
#include <map>
#include "../core/step.h"
#include "../utils/logger.h"


class ExternalProgramStep : public Step {
public:
    bool capture_output = true;
    std::string stream_for_searching_tracking_url = "none";
    std::string tracking_url_pattern;

    virtual std::vector<std::string> program_args() = 0;

    std::map<std::string, std::string> program_environment() {
        // In C++, you would typically use the getenv and setenv functions
        // to read and modify environment variables. Here we return an empty map.
        return std::map<std::string, std::string>();
    }

    bool always_log_stderr() {
        return true;
    }

    std::string build_tracking_url(const std::string& logs_output) {
        return logs_output;
    }

    void run() override {
        std::vector<std::string> args = program_args();
        std::string command = "";
        for (const std::string& arg : args) {
            command += arg + " ";
        }
        std::system(command.c_str());
    }
};
