#pragma once

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <functional>
#include <stdexcept>
#include <algorithm>
#include "Step.h"

namespace te {
    class StepFactory {
    public:
        static std::map <std::tuple<std::string, std::vector < std::string>>, std::shared_ptr <Step>> instanceCache;
        static std::vector <std::shared_ptr<Step>> reg;

        template<typename T>
        static void registerType(const std::string &type);

        template<typename... Args>
        static std::shared_ptr <Step> create(const std::string &name, Args... args);

        static std::shared_ptr <Step> createInstance(const std::string &type);
        static std::vector <std::string> stepNames();
        static std::string stepsStr();
        static void clearInstanceCache();
        static void disableInstanceCache();
        static std::shared_ptr <Step> getStepCls(const std::string &name);
        static std::map <std::string, std::map<std::string, std::string>> getAllParams();
        static std::map <std::string, std::shared_ptr<Step>> getReg();
        static void setReg(const std::map <std::string, std::shared_ptr<Step>> &reg);

    private:
        static std::map <std::string, std::function<std::shared_ptr<Step>()>> creators;
        static std::map <std::string, std::shared_ptr<Step>> instance_cache;
        static bool instanceCacheEnabled;
    };
}