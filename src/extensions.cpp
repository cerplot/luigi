#include <map>
#include <string>
#include <vector>
#include <sstream>
#include <iostream>
#include <regex>
#include <memory>
#include <functional>

class Namespace {
public:
    std::map<std::string, std::shared_ptr<Namespace>> children;
    std::string value;
};

void update_namespace(std::shared_ptr<Namespace> ns, std::vector<std::string> path, std::string value) {
    if (path.size() == 1) {
        ns->value = value;
    } else {
        if (ns->children.find(path[0]) == ns->children.end()) {
            ns->children[path[0]] = std::make_shared<Namespace>();
        }
        path.erase(path.begin());
        update_namespace(ns->children[path[0]], path, value);
    }
}

std::map<std::string, std::string> parse_extension_arg(std::string arg) {
    std::regex re("^(([\\w]+)(\\.[\\w]+)*)=(.*)$");
    std::smatch match;
    if (std::regex_search(arg, match, re) && match.size() > 1) {
        return { {match.str(1), match.str(4)} };
    } else {
        throw std::invalid_argument("invalid extension argument '" + arg + "', must be in key=value form");
    }
}

void create_args(std::vector<std::string> args, std::shared_ptr<Namespace> root) {
    std::map<std::string, std::string> extension_args;
    for (auto& arg : args) {
        auto parsed_arg = parse_extension_arg(arg);
        extension_args.insert(parsed_arg.begin(), parsed_arg.end());
    }
    for (auto& arg : extension_args) {
        std::istringstream ss(arg.first);
        std::string token;
        std::vector<std::string> path;
        while(std::getline(ss, token, '.')) {
            path.push_back(token);
        }
        update_namespace(root, path, arg.second);
    }
}

template <typename T>
class Registry {
public:
    std::map<std::string, std::function<std::shared_ptr<T>()>> factories;

    std::shared_ptr<T> load(std::string name) {
        if (factories.find(name) != factories.end()) {
            return factories[name]();
        } else {
            throw std::invalid_argument("no factory registered under name " + name);
        }
    }

    void register_factory(std::string name, std::function<std::shared_ptr<T>()> factory) {
        if (factories.find(name) != factories.end()) {
            throw std::invalid_argument("factory with name " + name + " is already registered");
        }
        factories[name] = factory;
    }

    void unregister(std::string name) {
        if (factories.find(name) == factories.end()) {
            throw std::invalid_argument("factory " + name + " was not already registered");
        }
        factories.erase(name);
    }

    void clear() {
        factories.clear();
    }
};

std::map<std::string, std::shared_ptr<Registry<void>>> custom_types;

template <typename T>
std::shared_ptr<Registry<T>> get_registry() {
    std::string type_name = typeid(T).name();
    if (custom_types.find(type_name) != custom_types.end()) {
        return std::static_pointer_cast<Registry<T>>(custom_types[type_name]);
    } else {
        throw std::invalid_argument("class specified is not an extendable type");
    }
}

template <typename T>
std::shared_ptr<T> load(std::string name) {
    return get_registry<T>()->load(name);
}

template <typename T>
void register_factory(std::string name, std::function<std::shared_ptr<T>()> factory) {
    get_registry<T>()->register_factory(name, factory);
}

template <typename T>
void unregister(std::string name) {
    get_registry<T>()->unregister(name);
}

template <typename T>
void clear() {
    get_registry<T>()->clear();
}

template <typename T>
void create_registry() {
    std::string type_name = typeid(T).name();
    if (custom_types.find(type_name) != custom_types.end()) {
        throw std::invalid_argument("there is already a Registry instance for the specified type");
    }
    custom_types[type_name] = std::make_shared<Registry<T>>();
}
