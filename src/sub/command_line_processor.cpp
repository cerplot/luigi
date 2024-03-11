#include "command_line_processor.h"
#include <stdexcept>

CommandLineProcessor::CommandLineProcessor(int argc, char* argv[]) {
    parseArguments(argc, argv);
}

std::string CommandLineProcessor::getArgument(const std::string& name) const {
    auto it = arguments.find(name);
    if (it == arguments.end()) {
        if (name == "S" || name == "B") {
            std::string currentDirectory = std::filesystem::current_path().string();
            return currentDirectory;
        }
        throw std::runtime_error("Argument not found: " + name + "\n" + usage());
    }
    return it->second;
}
bool CommandLineProcessor::getFlag(const std::string& name) const {
    return flags.count(name) > 0;
}
bool CommandLineProcessor::isRegistered(const std::string& name) const {
    // Check if the name exists in either the arguments or flags map
    return arguments.count(name) > 0 || flags.count(name) > 0;
}

void CommandLineProcessor::addOption(const std::string& name, const std::string& description, const std::string& defaultValue) {
    options[name] = {description, defaultValue, defaultValue};
}

std::string CommandLineProcessor::getOption(const std::string& name) const {
    auto it = options.find(name);
    if (it == options.end()) {
        throw std::runtime_error("Option not found: " + name);
    }
    return it->second.currentValue;
}
void CommandLineProcessor::printHelp() {
    // Iterate over all options and print their names and help texts
    for (const auto& option : options) {
//        std::cout << option.name << ": " << option.help << std::endl;
    }
}

std::string CommandLineProcessor::help() const {
    std::string helpMessage;
    for (const auto& option : options) {
        helpMessage += "--" + option.first + ": " + option.second.description + "\n";
        helpMessage += "Default value: " + option.second.defaultValue + "\n\n";
    }
    return helpMessage;
}

void CommandLineProcessor::buildProject() const {
    if (getFlag("--build")) {
        std::string buildCommand = "cmake --build " + getArgument("B");
        if (isRegistered("--target")) {
            buildCommand += " --target " + getArgument("--target");
        }
        std::system(buildCommand.c_str());
    }
}

void CommandLineProcessor::parseArguments(int argc, char* argv[]) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg[0] == '-') {
            arg = arg.substr(1);  // Remove the leading '-'
            if (arg == "D" && i + 1 < argc) {  // Check for '-D' flag
                std::string var = argv[i + 1];
                size_t pos = var.find('=');
                if (pos != std::string::npos) {
                    std::string name = var.substr(0, pos);
                    std::string value = var.substr(pos + 1);
                    arguments[name] = value;
                    ++i;  // Skip the value
                } else {
                    throw std::runtime_error("Invalid argument: " + arg + "\n" + usage());
                }
            } else if (arg == "G" || arg == "T" || arg == "C" || arg == "E" || arg == "L" || arg == "P" || arg == "N" || arg == "--build") {
                if (i + 1 < argc && argv[i + 1][0] != '-') {
                    std::string value = argv[i + 1];
                    arguments[arg] = value;
                    ++i;  // Skip the value
                } else {
                    // If the argument does not have a value, treat it as a flag
                    flags.insert(arg);
                }
            } else {
                // If the argument does not have a value, treat it as a flag
                flags.insert(arg);
            }
        } else {
            throw std::runtime_error("Invalid argument: " + arg + "\n" + usage());
        }
    }
}

std::string CommandLineProcessor::usage() const {
    return "Usage: program [-flag] [-argument [value]] ...";
}
