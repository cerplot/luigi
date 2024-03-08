#pragma once

#include <string>
#include <map>
#include <set>

class CommandLineProcessor {
public:
    CommandLineProcessor(int argc, char* argv[]);

    std::string getArgument(const std::string& name) const;
    bool getFlag(const std::string& name) const;

private:
    std::map<std::string, std::string> arguments;
    std::set<std::string> flags;

    void buildProject() const;
    void parseArguments(int argc, char* argv[]);
    std::string usage() const;
};