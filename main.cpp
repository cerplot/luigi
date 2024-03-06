#include <iostream>
#include <filesystem>
#include "config_parser.h"
#include <map>
#include <functional>


class Step {
public:
    virtual void execute(bool use_saved_data) = 0;
};

class Step1 : public Step {
public:
    void execute(bool use_saved_data) override {
        std::cout << "Running step1" << std::endl;
        // TODO: Implement the logic for step1
    }
};

class Step2 : public Step {
public:
    void execute(bool use_saved_data) override {
        std::cout << "Running step2" << std::endl;
        // TODO: Implement the logic for step2
    }
};

class Step3 : public Step {
public:
    void execute(bool use_saved_data) override {
        std::cout << "Running step3" << std::endl;
        // TODO: Implement the logic for step3
    }
};

class StepManager {
public:
    StepManager() {
        steps["step1"] = std::make_unique<Step1>();
        steps["step2"] = std::make_unique<Step2>();
        steps["step3"] = std::make_unique<Step3>();
    }

    void runStep(const std::string& step_name, bool use_saved_data) {
        auto it = steps.find(step_name);
        if (it != steps.end()) {
            it->second->execute(use_saved_data);
        } else {
            throw std::runtime_error("Step not found: " + step_name);
        }
    }

private:
    std::map<std::string, std::unique_ptr<Step>> steps;
};


int main(int argc, char *argv[]) {
    try {
        std::filesystem::path config_path;
        if (argc == 1) {
            config_path = std::filesystem::current_path() / "config.toml";
        }
        else if (argc == 2) {
            config_path = std::filesystem::path(argv[1]);
        }
        else {
            std::cerr << "Usage: " + std::string(argv[0]) + " [config_file_path]" << std::endl;
            return 1;
        }
        std::filesystem::path exe_path = std::filesystem::path(argv[0]).parent_path();
        auto config = *validate_config_file(
                exe_path / "default_config.toml", config_path);

        // Get the step and mode from the configuration file
        auto step = config["step"].value<std::string>();
        auto use_saved_data = config["use_saved_data"].value<bool>();

        StepManager stepManager;

        // Run the specified step in the specified mode
        stepManager.runStep(step.value(), use_saved_data.value());

    } catch (const std::runtime_error& e) {
        std::cerr << e.what() << std::endl;
        return 1;
    }

    return 0;
}