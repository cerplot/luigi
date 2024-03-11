#pragma once

#include <string>
#include <map>
#include <set>
#include <filesystem>

class CommandLineProcessor {
public:
    CommandLineProcessor(int argc, char* argv[]);

    std::string getArgument(const std::string& name) const;
    bool getFlag(const std::string& name) const;
    bool isRegistered(const std::string& name) const;

    void addOption(const std::string& name, const std::string& description, const std::string& defaultValue = "");

    std::map<std::string, std::string> arguments;
    std::set<std::string> flags;

    void buildProject() const;
    void parseArguments(int argc, char* argv[]);
    std::string usage() const;
    struct Option {
        std::string name;
        std::string help;
        std::string description;
        std::string defaultValue;
        std::string currentValue;
    };

    std::map<std::string, Option> options;

    std::string getOption(const std::string &name) const;

    std::string help() const;

    void printHelp();
private:

};
