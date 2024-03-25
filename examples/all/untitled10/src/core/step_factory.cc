#include "step_factory.h"

namespace te {
    // Cache instances of objects
    static std::map <std::tuple<std::string, std::vector < std::string>>, std::shared_ptr <Step>> instanceCache;

    // Keep track of all subclasses of Step
    static std::vector <std::shared_ptr<Step>> reg;

    template<typename T>
    static void StepFactory::registerType(const std::string &type) {
        creators[type] = [type]() {
            // capture 'type' by value
            auto it = instance_cache.find(type);
            if (it != instance_cache.end()) {
                return it->second;
            } else {
                std::shared_ptr <Step> instance = std::make_shared<T>();
                instance_cache[type] = instance;
                return instance;
            }
        };
    }

    template<typename... Args>
    std::shared_ptr <Step> StepFactory::create(const std::string &name, Args... args) {
        auto it = instanceCache.find(std::make_tuple(name, args...));
        if (it != instanceCache.end()) {
            return it->second;
        }

        auto creatorIt = creators.find(name);
        if (creatorIt == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }

        std::shared_ptr <Step> instance = creatorIt->second(args...);
        instanceCache[std::make_tuple(name, args...)] = instance;
        return instance;
    }

    std::shared_ptr <Step> StepFactory::createInstance(const std::string &type) {
        return creators[type]();
    }

    std::vector <std::string> StepFactory::stepNames() {
        std::vector <std::string> names;
        for (const auto &pair: creators) {
            names.push_back(pair.first);
        }
        std::sort(names.begin(), names.end());
        return names;
    }

    std::string StepFactory::stepsStr() {
        std::string result;
        for (const auto &pair: creators) {
            if (!result.empty()) {
                result += ",";
            }
            result += pair.first;
        }
        return result;
    }

    void StepFactory::clearInstanceCache() {
        instanceCache.clear();
    }

    void StepFactory::disableInstanceCache() {
        instanceCacheEnabled = false;
    }

    std::shared_ptr <Step> StepFactory::getStepCls(const std::string &name) {
        auto it = creators.find(name);
        if (it == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }
        return it->second();
    }

    std::map <std::string, std::map<std::string, std::string>> StepFactory::getAllParams() {
        std::map <std::string, std::map<std::string, std::string>> allParams;
        for (const auto &pair: creators) {
            std::shared_ptr <Step> instance = pair.second();
            allParams[pair.first] = instance->getParams();
        }
        return allParams;
    }

    std::map <std::string, std::shared_ptr<Step>> StepFactory::getReg() {
        std::map <std::string, std::shared_ptr<Step>> reg;
        for (const auto &pair: creators) {
            if (pair.second) {
                // Only add to the registry if the shared_ptr is not null
                reg[pair.first] = pair.second();
            }
        }
        return reg;
    }

    void StepFactory::setReg(const std::map <std::string, std::shared_ptr<Step>> &reg) {
        creators.clear();
        for (const auto &pair: reg) {
            if (pair.second != nullptr) {
                creators[pair.first] = [pair]() { return pair.second; };
            }
        }
    }

    static std::map <std::string, std::function<std::shared_ptr<Step>()>> creators;
    static std::map <std::string, std::shared_ptr<Step>> instance_cache;
    static bool instanceCacheEnabled;


std::map <std::string, std::function<std::shared_ptr<Step>()>> StepFactory::creators = {};
std::map <std::string, std::shared_ptr<Step>> StepFactory::instance_cache = {};

}
