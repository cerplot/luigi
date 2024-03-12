#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <functional>

class StepClassException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class StepClassNotFoundException : public StepClassException {
public:
    using StepClassException::StepClassException;
};

class StepClassAmbigiousException : public StepClassException {
public:
    using StepClassException::StepClassException;
};



class Step {
public:
    virtual ~Step() = default;
    virtual void run() = 0;
    virtual std::map<std::string, std::string> getParams() = 0; // Each Step class should implement this
};

class StepRegister {
public:
    static void add(std::string name, std::shared_ptr<Step> step) {
        registry[name] = step;
    }

    static std::shared_ptr<Step> get(std::string name) {
        return registry[name];
    }

private:
    static std::map<std::string, std::shared_ptr<Step>> registry;
};

std::map<std::string, std::shared_ptr<Step>> StepRegister::registry = {};

class StepFactory {
public:
    // Placeholder denoting an error
    static const std::shared_ptr<Step> AMBIGUOUS_CLASS;

    // Cache instances of objects
    static std::map<std::tuple<std::string, std::vector<std::string>>, std::shared_ptr<Step>> instanceCache;

    // Keep track of all subclasses of Step
    static std::vector<std::shared_ptr<Step>> reg;

    // Default namespace dict
    static std::map<std::string, std::string> defaultNamespaceDict;

    template <typename T>
    static void registerType(const std::string& type) {
        creators[type] = []() {
            auto it = instance_cache.find(type);
            if (it != instance_cache.end()) {
                return it->second;
            } else {
                std::shared_ptr<Step> instance = std::make_shared<T>();
                instance_cache[type] = instance;
                return instance;
            }
        };
    }

    template <typename... Args>
    static std::shared_ptr<Step> create(const std::string& name, Args... args) {
        auto it = instanceCache.find(std::make_tuple(name, args...));
        if (it != instanceCache.end()) {
            return it->second;
        }

        auto creatorIt = creators.find(name);
        if (creatorIt == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }

        std::shared_ptr<Step> instance = creatorIt->second(args...);
        instanceCache[std::make_tuple(name, args...)] = instance;
        return instance;
    }

    static std::shared_ptr<Step> createInstance(const std::string& type) {
        return creators[type]();
    }

    static std::string stepFamily(const std::string& name) {
        auto it = creators.find(name);
        if (it == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }
        std::string stepNamespace = ""; // Replace with actual namespace retrieval if needed
        if (stepNamespace.empty()) {
            return name;
        } else {
            return stepNamespace + "." + name;
        }
    }

    static std::vector<std::string> stepNames() {
        std::vector<std::string> names;
        for (const auto& pair : creators) {
            names.push_back(pair.first);
        }
        std::sort(names.begin(), names.end());
        return names;
    }

    static std::string stepsStr() {
        std::string result;
        for (const auto& pair : creators) {
            if (!result.empty()) {
                result += ",";
            }
            result += pair.first;
        }
        return result;
    }
    static void clearInstanceCache() {
        instanceCache.clear();
    }

    static void disableInstanceCache() {
        instanceCacheEnabled = false;
    }


    static std::shared_ptr<Step> getStepCls(const std::string& name) {
        auto it = creators.find(name);
        if (it == creators.end()) {
            throw std::runtime_error("Step class not found: " + name);
        }
        if (it->second == nullptr) { // Assuming nullptr is used to mark ambiguous classes
            throw std::runtime_error("Step class is ambiguous: " + name);
        }
        return it->second();
    }

    static std::map<std::string, std::map<std::string, std::string>> getAllParams() {
        std::map<std::string, std::map<std::string, std::string>> allParams;
        for (const auto& pair : creators) {
            std::shared_ptr<Step> instance = pair.second();
            allParams[pair.first] = instance->getParams();
        }
        return allParams;
    }

    static std::map<std::string, std::shared_ptr<Step>> getReg() {
        std::map<std::string, std::shared_ptr<Step>> reg;
        for (const auto& pair : creators) {
            if (!pair.second) { // Assuming nullptr is used to mark invisible classes
                continue;
            }
            std::string name = pair.first;
            if (reg.count(name) > 0 &&
                (reg[name] == nullptr ||
                 !std::dynamic_pointer_cast<Step>(pair.second))) {
                // Registering two different classes - this means we can't instantiate them by name
                // The only exception is if one class is a subclass of the other. In that case, we
                // instantiate the most-derived class (this fixes some issues with decorator wrappers).
                reg[name] = nullptr;
            } else {
                reg[name] = pair.second;
            }
        }
        return reg;
    }

    static int editDistance(const std::string& a, const std::string& b) {
        std::vector<int> r0(b.size() + 1);
        std::iota(r0.begin(), r0.end(), 0);
        std::vector<int> r1(b.size() + 1);

        for (size_t i = 0; i < a.size(); ++i) {
            r1[0] = i + 1;

            for (size_t j = 0; j < b.size(); ++j) {
                int c = (a[i] == b[j]) ? 0 : 1;
                r1[j + 1] = std::min({r1[j] + 1, r0[j + 1] + 1, r0[j] + c});
            }

            r0 = r1;
        }

        return r1[b.size()];
    }

    static std::string missingStepMsg(const std::string& stepName) {
        std::vector<std::pair<int, std::string>> weightedSteps;
        for (const auto& stepName2 : stepNames()) {
            weightedSteps.emplace_back(editDistance(stepName, stepName2), stepName2);
        }
        std::sort(weightedSteps.begin(), weightedSteps.end());

        std::vector<std::string> candidates;
        for (const auto& [dist, step] : weightedSteps) {
            if (dist <= 5 && dist < step.size()) {
                candidates.push_back(step);
            }
        }

        if (!candidates.empty()) {
            return "No step " + stepName + ". Did you mean:\n" + join(candidates, "\n");
        } else {
            return "No step " + stepName + ". Candidates are: " + stepsStr();
        }
    }

    static std::string getNamespace(const std::string& moduleName) {
        for (const auto& parent : moduleParents(moduleName)) {
            auto it = defaultNamespaceDict.find(parent);
            if (it != defaultNamespaceDict.end()) {
                return it->second;
            }
        }
        return "";
    }

    static std::vector<std::string> moduleParents(const std::string& moduleName) {
        std::vector<std::string> parents;
        size_t pos = 0;
        std::string token;
        std::string s = moduleName;
        while ((pos = s.find(".")) != std::string::npos) {
            token = s.substr(0, pos);
            parents.push_back(token);
            s.erase(0, pos + 1);
        }
        parents.push_back(s);
        std::reverse(parents.begin(), parents.end());
        return parents;
    }

    static void setReg(const std::map<std::string, std::shared_ptr<Step>>& reg) {
        creators.clear();
        for (const auto& pair : reg) {
            if (pair.second != nullptr) {
                creators[pair.first] = pair.second;
            }
        }
    }

private:
    static std::map<std::string, std::string> defaultNamespaceDict;
    static std::map<std::tuple<std::string, std::vector<std::string>>, std::shared_ptr<Step>> instanceCache;
    static std::map<std::string, std::function<std::shared_ptr<Step>(Args...)>> creators;
    static std::map<std::string, std::function<std::shared_ptr<Step>()>> creators;
    static std::map<std::string, std::shared_ptr<Step>> instance_cache;
    static std::map<std::tuple<std::string, std::vector<std::string>>, std::shared_ptr<Step>> instanceCache;
    static bool instanceCacheEnabled;
};

std::map<std::string, std::function<std::shared_ptr<Step>()>> StepFactory::creators = {};
std::map<std::string, std::shared_ptr<Step>> StepFactory::instance_cache = {};

class MyStep : public Step {
public:
    void run() override {
        // Implement your step here
    }
};

// Register the step type
StepFactory::registerType<MyStep>("MyStep");




//##################################
#include <iostream>
#include <string>
#include <map>

// Step abstract class
class Step {
public:
    virtual ~Step() = default;
    // Define the common interface for all Steps here
};

// StoredStep class
class StoredStep {
public:
    StoredStep(Step* step, bool status, std::string host = "")
            : step(step), status(status), host(host) {}

    std::string getStepFamily() {
        // Implement this method based on your Step class
    }

    std::map<std::string, std::string> getParameters() {
        // Implement this method based on your Step class
    }

private:
    Step* step;
    bool status;
    std::string host;
    std::string record_id;
};

// StepHistory abstract class
class StepHistory {
public:
    virtual ~StepHistory() = default;
    virtual void stepScheduled(Step* step) = 0;  // Pure virtual function
    virtual void stepFinished(Step* step, bool successful) = 0;  // Pure virtual function
    virtual void stepStarted(Step* step, std::string worker_host) = 0;  // Pure virtual function
};

// NopHistory class
class NopHistory : public StepHistory {
public:
    void stepScheduled(Step* step) override {
        // Do nothing
    }

    void stepFinished(Step* step, bool successful) override {
        // Do nothing
    }

    void stepStarted(Step* step, std::string worker_host) override {
        // Do nothing
    }
};
//##########################################
enum class StepStatus {
    PENDING,
    FAILED,
    DONE,
    RUNNING,
    BATCH_RUNNING,
    SUSPENDED,  // Only kept for backward compatibility with old clients
    UNKNOWN,
    DISABLED
};

//##################
#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <ctime>
#include <regex>

// Target abstract class
class Target {
public:
    virtual ~Target() = default;
    virtual bool exists() const = 0;  // Pure virtual function
};

// FileSystemException classes
class FileSystemException : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class FileAlreadyExists : public FileSystemException {
public:
    using FileSystemException::FileSystemException;
};

class MissingParentDirectory : public FileSystemException {
public:
    using FileSystemException::FileSystemException;
};

class NotADirectory : public FileSystemException {
public:
    using FileSystemException::FileSystemException;
};

// FileSystem abstract class
class FileSystem {
public:
    virtual ~FileSystem() = default;
    virtual bool exists(const std::string& path) const = 0;  // Pure virtual function
    virtual void remove(const std::string& path, bool recursive = true, bool skip_trash = true) = 0;  // Pure virtual function
    // Other methods omitted for brevity
};

// FileSystemTarget class
class FileSystemTarget : public Target {
public:
    FileSystemTarget(const std::string& path) : path(path) {}
    virtual ~FileSystemTarget() = default;
    virtual bool exists() const override {
        // Implementation depends on the specific FileSystem
    }
    virtual FileSystem& fs() const = 0;  // Pure virtual function
    // Other methods omitted for brevity
protected:
    std::string path;
};
#include <fstream>
#include <string>
#include <cstdio>

class AtomicLocalFile {
public:
    AtomicLocalFile(const std::string& path) : path(path), tmp_path(generate_tmp_path(path)) {
        file.open(tmp_path);
    }

    ~AtomicLocalFile() {
        if (file.is_open()) {
            file.close();
            std::rename(tmp_path.c_str(), path.c_str());
        }
    }

    std::ofstream& get_file() {
        return file;
    }

private:
    std::string generate_tmp_path(const std::string& path) {
        // Generate a temporary path based on the original path
        // This is a simplified version and might need to be adjusted based on your specific requirements
        return "/tmp/" + path + "-tmp";
    }

    std::string path;
    std::string tmp_path;
    std::ofstream file;
};
//##############
#include <string>
#include <stdexcept>
#include <optional>
#include <vector>
#include <map>
#include <chrono>
#include <ctime>
#include <regex>

// Parameter base class
class Parameter {
public:
    virtual ~Parameter() = default;
    virtual std::string parse(const std::string& input) const = 0;  // Pure virtual function
    virtual std::string serialize(const std::string& input) const = 0;  // Pure virtual function
};

// IntParameter class
class IntParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        try {
            std::stoi(input);
            return input;
        } catch (const std::invalid_argument& e) {
            throw std::invalid_argument("Invalid integer: " + input);
        }
    }

    std::string serialize(const std::string& input) const override {
        try {
            std::stoi(input);
            return input;
        } catch (const std::invalid_argument& e) {
            throw std::invalid_argument("Invalid integer: " + input);
        }
    }
};

// FloatParameter class
class FloatParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        try {
            std::stof(input);
            return input;
        } catch (const std::invalid_argument& e) {
            throw std::invalid_argument("Invalid float: " + input);
        }
    }

    std::string serialize(const std::string& input) const override {
        try {
            std::stof(input);
            return input;
        } catch (const std::invalid_argument& e) {
            throw std::invalid_argument("Invalid float: " + input);
        }
    }
};

// BoolParameter class
class BoolParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        if (input == "true" || input == "1") {
            return "true";
        } else if (input == "false" || input == "0") {
            return "false";
        } else {
            throw std::invalid_argument("Invalid boolean: " + input);
        }
    }

    std::string serialize(const std::string& input) const override {
        if (input == "true" || input == "1") {
            return "true";
        } else if (input == "false" || input == "0") {
            return "false";
        } else {
            throw std::invalid_argument("Invalid boolean: " + input);
        }
    }
};

// DateParameter class
class DateParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement date parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement date serialization logic here
        return input;
    }
};

// MonthParameter class
class MonthParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement month parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement month serialization logic here
        return input;
    }
};

// YearParameter class
class YearParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement year parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement year serialization logic here
        return input;
    }
};

// DateHourParameter class
class DateHourParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement date hour parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement date hour serialization logic here
        return input;
    }
};

// DateMinuteParameter class
class DateMinuteParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement date minute parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement date minute serialization logic here
        return input;
    }
};

// DateSecondParameter class
class DateSecondParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement date second parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement date second serialization logic here
        return input;
    }
};

// DictParameter class
class DictParameter : public Parameter {
public:
    std::map<std::string, std::string> parse(const std::string& input) const override {
        // Implement dictionary parsing logic here
        return std::map<std::string, std::string>();
    }

    std::string serialize(const std::map<std::string, std::string>& input) const override {
        // Implement dictionary serialization logic here
        return "";
    }
};

// ListParameter class
class ListParameter : public Parameter {
public:
    std::vector<std::string> parse(const std::string& input) const override {
        // Implement list parsing logic here
        return std::vector<std::string>();
    }

    std::string serialize(const std::vector<std::string>& input) const override {
        // Implement list serialization logic here
        return "";
    }
};

// TupleParameter class
class TupleParameter : public Parameter {
public:
    std::pair<std::string, std::string> parse(const std::string& input) const override {
        // Implement tuple parsing logic here
        return std::pair<std::string, std::string>();
    }

    std::string serialize(const std::pair<std::string, std::string>& input) const override {
        // Implement tuple serialization logic here
        return "";
    }
};

// NumericalParameter class
class NumericalParameter : public Parameter {
public:
    double parse(const std::string& input) const override {
        // Implement numerical parsing logic here
        return std::stod(input);
    }

    std::string serialize(const double& input) const override {
        // Implement numerical serialization logic here
        return std::to_string(input);
    }
};

// ChoiceParameter class
class ChoiceParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement choice parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement choice serialization logic here
        return input;
    }
};

// PathParameter class
class PathParameter : public Parameter {
public:
    std::string parse(const std::string& input) const override {
        // Implement path parsing logic here
        return input;
    }

    std::string serialize(const std::string& input) const override {
        // Implement path serialization logic here
        return input;
    }
};


//##################################
#include <string>
#include <vector>
#include <iostream>

class BaseParser {
public:
    static BaseParser* instance() {
        if (_instance == nullptr) {
            _instance = new BaseParser();
            bool loaded = _instance->reload();
            std::cout << "Loaded " << loaded << std::endl;
        }
        return _instance;
    }

    static void add_config_path(const std::string& path) {
        _config_paths.push_back(path);
        reload();
    }

    static bool reload() {
        return instance()->read(_config_paths);
    }

    bool read(const std::vector<std::string>& paths) {
        // Implement the logic to read the config paths here
        return true;
    }

private:
    BaseParser() = default;
    static BaseParser* _instance;
    static std::vector<std::string> _config_paths;
};

// Initialize static members
BaseParser* BaseParser::_instance = nullptr;
std::vector<std::string> BaseParser::_config_paths = {};

//##################################

#include <string>
#include <map>
#include <vector>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include "toml++/toml.h"  // Include the toml++ library

class TrunTomlParser {
public:
    TrunTomlParser() {
        _config_paths = {"/etc/trun/trun.toml", "trun.toml"};
        read(_config_paths);
    }

    std::shared_ptr<toml::table> read(const std::vector<std::string>& config_paths) {
        for (const auto& path : config_paths) {
            std::ifstream file(path);
            if (file.is_open()) {
                data = toml::parse_file(path);
            }
        }
        return data;
    }

    template<typename T>
    T get(const std::string& section, const std::string& option, T default_value) {
        try {
            return data->get_qualified_as<T>(section + "." + option).value_or(default_value);
        } catch (const std::out_of_range& e) {
            throw std::invalid_argument("Invalid section or option: " + section + "." + option);
        }
    }

    bool has_option(const std::string& section, const std::string& option) {
        return data->contains_qualified(section + "." + option);
    }

private:
    std::shared_ptr<toml::table> data;
    std::vector<std::string> _config_paths;
};

//##################################
#include <iostream>
#include <map>
#include <string>
#include <fstream>
#include "TrunConfigParser.h"  // Include the TrunConfigParser class
#include "TrunTomlParser.h"  // Include the TrunTomlParser class

std::map<std::string, BaseParser*> PARSERS = {
        {"cfg", new TrunConfigParser()},
        {"conf", new TrunConfigParser()},
        {"ini", new TrunConfigParser()},
        {"toml", new TrunTomlParser()},
};

std::string DEFAULT_PARSER = "toml";

std::string get_env_var(const std::string& key, const std::string& default_value) {
    char* val = getenv(key.c_str());
    return val == NULL ? default_value : std::string(val);
}

BaseParser* get_default_parser() {
    std::string parser = get_env_var("TRUN_CONFIG_PARSER", DEFAULT_PARSER);
    if (PARSERS.find(parser) == PARSERS.end()) {
        std::cerr << "Invalid parser: " << parser << std::endl;
        parser = DEFAULT_PARSER;
    }
    return PARSERS[parser];
}

void check_parser(BaseParser* parser_class, const std::string& parser) {
    if (!parser_class->enabled) {
        std::cerr << "Parser not installed yet. Please, install trun with required parser:\n"
                  << "pip install trun[" << parser << "]" << std::endl;
        exit(1);
    }
}

BaseParser* get_config(std::string parser = "") {
    if (parser.empty()) {
        parser = get_default_parser()->name;
    }
    BaseParser* parser_class = PARSERS[parser];
    check_parser(parser_class, parser);
    return parser_class->instance();
}

bool add_config_path(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        std::cerr << "Config file does not exist: " << path << std::endl;
        return false;
    }

    std::string default_parser = get_default_parser()->name;
    std::string ext = path.substr(path.find_last_of(".") + 1);
    std::string parser = (PARSERS.find(ext) != PARSERS.end()) ? ext : default_parser;
    BaseParser* parser_class = PARSERS[parser];

    check_parser(parser_class, parser);
    if (parser != default_parser) {
        std::cerr << "Config for " << parser << " parser added, but used " << default_parser << " parser. "
                  << "Set up right parser via env var: "
                  << "export TRUN_CONFIG_PARSER=" << parser << std::endl;
    }

    parser_class->add_config_path(path);
    return true;
}

//int main() {
//    std::string config_path = get_env_var("TRUN_CONFIG_PATH", "");
//    if (!config_path.empty()) {
//        add_config_path(config_path);
//    }
//
//    return 0;
//}
//##################################

#include <iostream>
#include <map>
#include <string>
#include <fstream>
#include <stdexcept>
#include "soci/soci.h"  // Include the soci library

class StepParameter {
public:
    int step_id;
    std::string name;
    std::string value;
};

class StepEvent {
public:
    int id;
    int step_id;
    std::string event_name;
    std::string ts;  // timestamp
};

class StepRecord {
public:
    int id;
    std::string step_id;
    std::string name;
    std::string host;
    std::map<std::string, StepParameter> parameters;
    std::vector<StepEvent> events;
};

class DbStepHistory {
public:
    DbStepHistory() {
        // Initialize the soci session
        soci::session sql(soci::postgresql, "dbname=trun user=postgres password=secret");

        // Create the tables if they don't exist
        sql << "CREATE TABLE IF NOT EXISTS step_parameters (step_id INTEGER, name VARCHAR(128), value TEXT)";
        sql << "CREATE TABLE IF NOT EXISTS step_events (id INTEGER, step_id INTEGER, event_name VARCHAR(20), ts TIMESTAMP)";
        sql << "CREATE TABLE IF NOT EXISTS steps (id INTEGER, step_id VARCHAR(200), name VARCHAR(128), host VARCHAR(128))";
    }

    // Implement the methods for step_scheduled, step_finished, step_started, etc.
    // These methods will involve SQL queries to insert/update data in the database.
    // The implementation will depend on the specific requirements of your application.
};

void upgrade_schema(soci::session& sql) {
    // Check if 'step_id' column exists in 'steps' table
    std::string check_column_query = "SELECT column_name FROM information_schema.columns WHERE table_name='steps' AND column_name='step_id'";
    std::string column_name;
    soci::statement st = (sql.prepare << check_column_query, soci::into(column_name));
    st.execute(true);

    if (column_name.empty()) {
        // 'step_id' column doesn't exist, so add it
        std::string add_column_query = "ALTER TABLE steps ADD COLUMN step_id VARCHAR(200)";
        sql << add_column_query;
        std::string create_index_query = "CREATE INDEX ix_step_id ON steps (step_id)";
        sql << create_index_query;
    }

    // Alter 'value' column to be TEXT
    std::string alter_column_query = "ALTER TABLE step_parameters MODIFY COLUMN value TEXT";
    sql << alter_column_query;
}

//##################################
namespace Event {
    constexpr auto DEPENDENCY_DISCOVERED = "event.core.dependency.discovered";
    constexpr auto DEPENDENCY_MISSING = "event.core.dependency.missing";
    constexpr auto DEPENDENCY_PRESENT = "event.core.dependency.present";
    constexpr auto BROKEN_STEP = "event.core.step.broken";
    constexpr auto START = "event.core.start";
    constexpr auto PROGRESS = "event.core.progress";
    constexpr auto FAILURE = "event.core.failure";
    constexpr auto SUCCESS = "event.core.success";
    constexpr auto PROCESSING_TIME = "event.core.processing_time";
    constexpr auto TIMEOUT = "event.core.timeout";
    constexpr auto PROCESS_FAILURE = "event.core.process_failure";
}

#include <string>
#include <map>

enum class TrunStatusCode {
    SUCCESS,
    SUCCESS_WITH_RETRY,
    FAILED,
    FAILED_AND_SCHEDULING_FAILED,
    SCHEDULING_FAILED,
    NOT_RUN,
    MISSING_EXT
};

std::map<TrunStatusCode, std::pair<std::string, std::string>> StatusCodeMeaning = {
        {TrunStatusCode::SUCCESS, {":)", "there were no failed steps or missing dependencies"}},
        {TrunStatusCode::SUCCESS_WITH_RETRY, {":)", "there were failed steps but they all succeeded in a retry"}},
        {TrunStatusCode::FAILED, {":(", "there were failed steps"}},
        {TrunStatusCode::FAILED_AND_SCHEDULING_FAILED, {":(", "there were failed steps and steps whose scheduling failed"}},
        {TrunStatusCode::SCHEDULING_FAILED, {":(", "there were steps whose scheduling failed"}},
        {TrunStatusCode::NOT_RUN, {":|", "there were steps that were not granted run permission by the scheduler"}},
        {TrunStatusCode::MISSING_EXT, {":|", "there were missing external dependencies"}}
};

class TrunRunResult {
public:
    TrunRunResult(Worker* worker, bool worker_add_run_status) {
        // Implementation depends on the Worker class and other functions
    }

    std::string toString() {
        return "TrunRunResult with status " + std::to_string(static_cast<int>(status));
    }

    std::string repr() {
        return "TrunRunResult(status=" + std::to_string(static_cast<int>(status)) + ",worker=" + worker->toString() + ",scheduling_succeeded=" + std::to_string(scheduling_succeeded) + ")";
    }

private:
    Worker* worker;
    std::string summary_text;
    TrunStatusCode status;
    std::string one_line_summary;
    bool scheduling_succeeded;
};

#include <cstdio>
#include <iostream>
#include <stdexcept>

class PipeProcessWrapper {
private:
    FILE* pipe;
    bool isInput;

public:
    PipeProcessWrapper(std::string command, bool isInput) : isInput(isInput) {
        if (isInput) {
            pipe = popen(command.c_str(), "r");
        } else {
            pipe = popen(command.c_str(), "w");
        }

        if (!pipe) {
            throw std::runtime_error("popen() failed!");
        }
    }

    ~PipeProcessWrapper() {
        pclose(pipe);
    }

    std::string read() {
        if (!isInput) {
            throw std::runtime_error("Cannot read from an output pipe!");
        }

        char buffer[128];
        std::string result = "";
        while (!feof(pipe)) {
            if (fgets(buffer, 128, pipe) != NULL)
                result += buffer;
        }
        return result;
    }

    void write(std::string content) {
        if (isInput) {
            throw std::runtime_error("Cannot write to an input pipe!");
        }

        fputs(content.c_str(), pipe);
    }

    // ... other methods as needed ...
};


#include <map>
#include <vector>
#include <string>
#include <variant>

class FrozenOrderedDict {
private:
    std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>> dict;

public:
    FrozenOrderedDict(std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>> input_dict) {
        dict = input_dict;
    }

    std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>> operator[](std::string key) {
        return dict[key];
    }

    // ... other methods as needed ...
};

FrozenOrderedDict recursively_freeze(std::variant<std::string, std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>>> value) {
    if (std::holds_alternative<std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>>>(value)) {
        std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>> input_map = std::get<std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>>>(value);
        for (auto& item : input_map) {
            item.second = recursively_freeze(item.second);
        }
        return FrozenOrderedDict(input_map);
    } else if (std::holds_alternative<std::vector<std::variant<std::string, FrozenOrderedDict>>>(value)) {
        std::vector<std::variant<std::string, FrozenOrderedDict>> input_vector = std::get<std::vector<std::variant<std::string, FrozenOrderedDict>>>(value);
        for (auto& item : input_vector) {
            item = recursively_freeze(item);
        }
        return FrozenOrderedDict(input_vector);
    }
    return value;
}

std::map<std::string, std::variant<std::string, std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>>> recursively_unfreeze(FrozenOrderedDict value) {
std::map<std::string, std::variant<std::string, FrozenOrderedDict, std::vector<std::variant<std::string, FrozenOrderedDict>>>> output_map;
for (auto& item : value) {
if (std::holds_alternative<FrozenOrderedDict>(item.second)) {
output_map[item.first] = recursively_unfreeze(std::get<FrozenOrderedDict>(item.second));
} else if (std::holds_alternative<std::vector<std::variant<std::string, FrozenOrderedDict>>>(item.second)) {
std::vector<std::variant<std::string, FrozenOrderedDict>> output_vector;
std::vector<std::variant<std::string, FrozenOrderedDict>> input_vector = std::get<std::vector<std::variant<std::string, FrozenOrderedDict>>>(item.second);
for (auto& vector_item : input_vector) {
if (std::holds_alternative<FrozenOrderedDict>(vector_item)) {
output_vector.push_back(recursively_unfreeze(std::get<FrozenOrderedDict>(vector_item)));
} else {
output_vector.push_back(vector_item);
}
}
output_map[item.first] = output_vector;
} else {
output_map[item.first] = item.second;
}
}
return output_map;
}

#include <string>

class Core {
private:
    bool local_scheduler;
    std::string scheduler_host;
    int scheduler_port;
    std::string scheduler_url;
    int lock_size;
    bool no_lock;
    std::string lock_pid_dir;
    bool take_lock;
    int workers;
    std::string logging_conf_file;
    std::string log_level;
    std::string module;
    bool parallel_scheduling;
    int parallel_scheduling_processes;
    bool assistant;
    bool help;
    bool help_all;

public:
    Core(/* parameters */) {
        // Initialize variables based on parameters
    }

    // Getter and setter methods for each variable
};

class WorkerSchedulerFactory {
public:
    Scheduler create_local_scheduler() {
        // Create and return a local scheduler
    }

    RemoteScheduler create_remote_scheduler(std::string url) {
        // Create and return a remote scheduler
    }

    Worker create_worker(Scheduler scheduler, int worker_processes, bool assistant) {
        // Create and return a worker
    }
};

bool schedule_and_run(std::vector<Step> steps, WorkerSchedulerFactory worker_scheduler_factory, std::map<std::string, std::variant<int, std::string, bool>> override_defaults) {
    // Create a Core object with the override_defaults
    // Create a Scheduler and a Worker using the WorkerSchedulerFactory
    // Use the Worker to schedule and run the steps
    // Return true if all steps were successfully run, false otherwise
}


//##################################
#include <filesystem>
#include <fstream>
#include <string>
#include <stdexcept>
#include <random>

namespace fs = std::filesystem;

class AtomicFile {
private:
    fs::path tmp_path;
    fs::path path;
    std::fstream file;

public:
    AtomicFile(fs::path path) : path(std::move(path)) {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> distrib(0, 999999999);
        tmp_path = this->path.string() + "-trun-tmp-" + std::to_string(distrib(gen));
        file.open(tmp_path, std::ios::out);
    }

    std::fstream& get() {
        return file;
    }

    void close() {
        file.close();
        fs::rename(tmp_path, path);
    }

    ~AtomicFile() {
        if (fs::exists(tmp_path)) {
            fs::remove(tmp_path);
        }
    }
};

class LocalFileSystem {
public:
    void copy(const fs::path& old_path, const fs::path& new_path, bool raise_if_exists = false) {
        if (raise_if_exists && fs::exists(new_path)) {
            throw std::runtime_error("Destination exists: " + new_path.string());
        }
        fs::create_directories(new_path.parent_path());
        fs::copy(old_path, new_path);
    }

    bool exists(const fs::path& path) {
        return fs::exists(path);
    }

    void mkdir(const fs::path& path, bool parents = true, bool raise_if_exists = false) {
        if (exists(path)) {
            if (raise_if_exists) {
                throw std::runtime_error("Directory already exists: " + path.string());
            } else if (!fs::is_directory(path)) {
                throw std::runtime_error("Path exists but is not a directory: " + path.string());
            } else {
                return;
            }
        }

        if (parents) {
            fs::create_directories(path);
        } else {
            fs::create_directory(path);
        }
    }

    bool isdir(const fs::path& path) {
        return fs::is_directory(path);
    }

    void remove(const fs::path& path, bool recursive = true) {
        if (recursive && isdir(path)) {
            fs::remove_all(path);
        } else {
            fs::remove(path);
        }
    }

    void move(const fs::path& old_path, const fs::path& new_path, bool raise_if_exists = false) {
        if (raise_if_exists && fs::exists(new_path)) {
            throw std::runtime_error("Destination exists: " + new_path.string());
        }
        fs::create_directories(new_path.parent_path());
        fs::rename(old_path, new_path);
    }

    void rename_dont_move(const fs::path& path, const fs::path& dest) {
        if (fs::exists(dest)) {
            throw std::runtime_error("Destination exists: " + dest.string());
        }
        fs::path new_path = dest / path.filename();
        fs::rename(path, new_path);
    }
};

class LocalTarget {
private:
    fs::path path;
    std::string format;
    bool is_tmp;
    LocalFileSystem fs;

public:
    LocalTarget(fs::path path = "", std::string format = "", bool is_tmp = false)
            : path(std::move(path)), format(std::move(format)), is_tmp(is_tmp) {
        if (this->format.empty()) {
            this->format = "default_format";
        }

        if (this->path.empty()) {
            if (!this->is_tmp) {
                throw std::runtime_error("path or is_tmp must be set");
            }
            std::random_device rd;
            std::mt19937 gen(rd());
            std::uniform_int_distribution<> distrib(0, 999999999);
            this->path = fs::temp_directory_path() / ("trun-tmp-" + std::to_string(distrib(gen)));
        }
    }

    void makedirs() {
        fs.mkdir(path, true);
    }

    AtomicFile open(const std::string& mode) {
        if (mode == "w") {
            makedirs();
            return AtomicFile(path);
        } else if (mode == "r") {
            return AtomicFile(path);
        } else {
            throw std::runtime_error("mode must be 'r' or 'w' (got: " + mode + ")");
        }
    }

    void move(const fs::path& new_path, bool raise_if_exists = false) {
        fs.move(path, new_path, raise_if_exists);
    }

    void remove() {
        fs.remove(path);
    }

    void copy(const fs::path& new_path, bool raise_if_exists = false) {
        fs.copy(path, new_path, raise_if_exists);
    }

    ~LocalTarget() {
        if (is_tmp && fs.exists(path)) {
            fs.remove(path);
        }
    }
};
//##################################

#include <filesystem>
#include <fstream>
#include <string>
#include <stdexcept>
#include <set>
#include <cstdlib>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <openssl/md5.h>

namespace fs = std::filesystem;

std::string getpcmd(pid_t pid) {
    // This function is platform-dependent and may need to be implemented differently on different platforms.
    // Here's a simple implementation for Linux:
    std::string cmdline_file = "/proc/" + std::to_string(pid) + "/cmdline";
    std::ifstream file(cmdline_file);
    std::string cmd;
    std::getline(file, cmd, '\0');
    return cmd;
}

std::string get_info(const fs::path& pid_dir, pid_t my_pid = 0) {
    if (my_pid == 0) {
        my_pid = getpid();
    }

    std::string my_cmd = getpcmd(my_pid);
    unsigned char result[MD5_DIGEST_LENGTH];
    MD5((unsigned char*)my_cmd.data(), my_cmd.size(), result);
    std::string cmd_hash;
    for(int i = 0; i < MD5_DIGEST_LENGTH; ++i) {
        cmd_hash += std::to_string(result[i]);
    }
    fs::path pid_file = pid_dir / (cmd_hash + ".pid");

    return pid_file.string();
}

bool acquire_for(const fs::path& pid_dir, int num_available = 1, int kill_signal = 0) {
    pid_t my_pid = getpid();
    fs::path pid_file = get_info(pid_dir, my_pid);

    fs::create_directories(pid_dir);
    chmod(pid_dir.c_str(), 0777);

    std::set<pid_t> pids;
    std::ifstream file(pid_file);
    pid_t pid;
    while (file >> pid) {
        pids.insert(pid);
    }

    if (kill_signal != 0) {
        for (pid_t pid : pids) {
            kill(pid, kill_signal);
        }
        std::cout << "Sent kill signal to Pids: " << pids.size() << std::endl;
        num_available += 1;
    }

    if (pids.size() >= num_available) {
        std::cout << "Pid(s) " << pids.size() << " already running" << std::endl;
        if (kill_signal != 0) {
            std::cout << "Note: There have (probably) been 1 other \"--take-lock\" process which continued to run! Probably no need to run this one as well." << std::endl;
        }
        return false;
    }

    std::ofstream out_file(pid_file, std::ios::app);
    out_file << my_pid << std::endl;

    return true;
}


#include <filesystem>
#include <fstream>
#include <string>
#include <stdexcept>
#include <map>
#include <sstream>
#include <iostream>

namespace fs = std::filesystem;

class Buffer {
private:
    std::stringstream buffer;
    bool mirror_on_stderr;
    std::string path;

public:
    Buffer(const std::string& path, bool mirror_on_stderr)
            : path(path), mirror_on_stderr(mirror_on_stderr) {}

    void write(const std::string& data) {
        if (mirror_on_stderr) {
            std::cerr << path << ": " << data;
        }
        buffer << data;
    }

    std::string read() {
        return buffer.str();
    }

    void clear() {
        buffer.str(std::string());
    }
};

class MockFileSystem {
private:
    std::map<std::string, Buffer> data;

public:
    void copy(const std::string& path, const std::string& dest, bool raise_if_exists = false) {
        if (raise_if_exists && data.count(dest)) {
            throw std::runtime_error("Destination exists: " + dest);
        }
        data[dest] = data[path];
    }

    bool exists(const std::string& path) {
        return data.count(path);
    }

    void remove(const std::string& path, bool recursive = true) {
        if (recursive) {
            for (auto it = data.begin(); it != data.end();) {
                if (it->first.find(path) == 0) {
                    it = data.erase(it);
                } else {
                    ++it;
                }
            }
        } else {
            data.erase(path);
        }
    }

    void move(const std::string& path, const std::string& dest, bool raise_if_exists = false) {
        if (raise_if_exists && data.count(dest)) {
            throw std::runtime_error("Destination exists: " + dest);
        }
        data[dest] = data[path];
        data.erase(path);
    }

    void clear() {
        data.clear();
    }

    Buffer& get_buffer(const std::string& path) {
        return data[path];
    }
};

class MockTarget {
private:
    std::string path;
    std::string format;
    bool mirror_on_stderr;
    MockFileSystem fs;

public:
    MockTarget(std::string path, bool is_tmp = false, bool mirror_on_stderr = false, std::string format = "")
            : path(std::move(path)), mirror_on_stderr(mirror_on_stderr), format(std::move(format)) {
        if (this->format.empty()) {
            this->format = "default_format";
        }
    }

    bool exists() {
        return fs.exists(path);
    }

    void move(const std::string& new_path, bool raise_if_exists = false) {
        fs.move(path, new_path, raise_if_exists);
        path = new_path;
    }

    Buffer& open(const std::string& mode) {
        Buffer& buffer = fs.get_buffer(path);
        if (mode == "w") {
            buffer.clear();
        } else if (mode != "r") {
            throw std::runtime_error("mode must be 'r' or 'w' (got: " + mode + ")");
        }
        return buffer;
    }
};


#include <iostream>
#include <string>
#include <stdexcept>
#include <map>
#include <asio.hpp>

class TestNotificationsStep {
private:
    bool raise_in_complete;

public:
    TestNotificationsStep(bool raise_in_complete = false)
            : raise_in_complete(raise_in_complete) {}

    void run() {
        throw std::runtime_error("Testing notifications triggering");
    }

    bool complete() {
        if (raise_in_complete) {
            throw std::runtime_error("Testing notifications triggering");
        }
        return false;
    }
};

class Email {
private:
    bool force_send;
    std::string format;
    std::string method;
    std::string prefix;
    std::string receiver;
    int traceback_max_length;
    std::string sender;

public:
    Email(bool force_send = false, std::string format = "plain", std::string method = "smtp",
          std::string prefix = "", std::string receiver = "", int traceback_max_length = 5000,
          std::string sender = "trun-client@localhost")
            : force_send(force_send), format(std::move(format)), method(std::move(method)),
              prefix(std::move(prefix)), receiver(std::move(receiver)), traceback_max_length(traceback_max_length),
              sender(std::move(sender)) {}
};

class Smtp {
private:
    std::string host;
    std::string local_hostname;
    bool no_tls;
    std::string password;
    int port;
    bool ssl;
    float timeout;
    std::string username;

public:
    Smtp(std::string host = "localhost", std::string local_hostname = "", bool no_tls = false,
         std::string password = "", int port = 0, bool ssl = false, float timeout = 10.0,
         std::string username = "")
            : host(std::move(host)), local_hostname(std::move(local_hostname)), no_tls(no_tls),
              password(std::move(password)), port(port), ssl(ssl), timeout(timeout),
              username(std::move(username)) {}
};

#include <asio.hpp>
#include <iostream>
#include <string>
#include <stdexcept>

void send_email_smtp(const std::string& sender, const std::string& subject, const std::string& message, const std::vector<std::string>& recipients) {
    // C++ does not have a built-in SMTP library like Python's smtplib.
    // You would need to use a third-party library or an API to send emails.
    // Here is a pseudocode representation of what the function might look like:

    // Create an SMTP connection using the host and port
    // If SSL is enabled, use SMTP_SSL instead of SMTP
    // If the SMTP server requires authentication, log in with the username and password
    // Create the email message with the sender, recipients, and message
    // Send the email
    // Close the SMTP connection
}

void send_email_ses(const std::string& sender, const std::string& subject, const std::string& message, const std::vector<std::string>& recipients) {
    // C++ does not have a built-in library for AWS SES like Python's boto3.
    // You would need to use the AWS SDK for C++ to send emails through SES.
    // Here is a pseudocode representation of what the function might look like:

    // Create an AWS SES client
    // Create the email message with the sender, recipients, and message
    // Send the email through SES
}
//##################################

#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <chrono>
#include <ctime>
#include <sys/types.h>
#include <signal.h>

namespace fs = std::filesystem;

int check_pid(const std::string& pidfile) {
    if (!pidfile.empty() && fs::exists(pidfile)) {
        std::ifstream file(pidfile);
        int pid;
        file >> pid;
        if (kill(pid, 0) == 0) {
            return pid;
        }
    }
    return 0;
}

void write_pid(const std::string& pidfile) {
    std::cout << "Writing pid file" << std::endl;
    fs::path piddir = fs::path(pidfile).parent_path();
    if (!piddir.empty()) {
        fs::create_directories(piddir);
    }

    std::ofstream file(pidfile);
    file << getpid();
}

std::string get_log_format() {
    return "%Y-%m-%d %H:%M:%S [PID] LEVEL: MESSAGE";
}

// C++ does not have a built-in logging library like Python's logging.
// You would need to use a third-party library or an API to handle logging.
// Here is a pseudocode representation of what the function might look like:
void get_spool_handler(const std::string& filename) {
    // Create a rotating file handler with the filename, when='d', encoding='utf8', and backupCount=7
    // Set the formatter of the handler to the log format
}

bool server_already_running(const std::string& pidfile) {
    int existing_pid = check_pid(pidfile);
    if (!pidfile.empty() && existing_pid) {
        return true;
    }
    return false;
}

// C++ does not have a built-in library for daemon operations like Python's daemon.
// You would need to use a third-party library or an API to handle daemon operations.
// Here is a pseudocode representation of what the function might look like:
void daemonize(std::function<void(int, const std::string&, const std::string&)> cmd, const std::string& pidfile = "", const std::string& logdir = "", int api_port = 8082, const std::string& address = "", const std::string& unix_socket = "") {
    // Set the logdir to "/var/log/trun" if it's not provided
    // Create the logdir if it does not exist
    // Set the paths of the log, stdout, and stderr files
    // Open the stdout and stderr files
    // Create a daemon context with the stdout and stderr files and the current working directory
    // Add the log handler to the root logger
    // If a pidfile is provided, check if the server is already running and return if it is
    // Otherwise, write the pid to the pidfile
    // Run the command with the provided api_port, address, and unix_socket
}

#include <stdio.h>
#include <stdlib.h>

struct Retcode {
    int unhandled_exception;
    int missing_data;
    int step_failed;
    int already_running;
    int scheduling_error;
    int not_run;
};

void run_with_retcodes(char* argv[]) {
    struct Retcode retcodes = {4, 0, 0, 0, 0, 0};

    // Pseudocode: Create a worker and run the command with the provided argv
    // If an exception is thrown, log the exception and exit with the unhandled_exception retcode
    // If the worker is already running, exit with the already_running retcode

    // Pseudocode: Get the step sets and root step from the worker
    // Determine the non-empty categories from the step sets

    // Pseudocode: Define a function to check if a status is in the non-empty categories

    // Pseudocode: Define the codes and conditions
    // Determine the expected retcode based on the codes and conditions

    // If the expected retcode is 0 and the root step is not completed or already done, exit with the not_run retcode
    // Otherwise, exit with the expected retcode
}

//##################################
#include <iostream>
#include <string>
#include <filesystem>
#include <map>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <retry/retry.hpp>

class RPCError : public std::exception {
public:
    std::string message;
    std::exception sub_exception;

    RPCError(const std::string& message, const std::exception& sub_exception)
            : message(message), sub_exception(sub_exception) {}

    const char* what() const throw() {
        return message.c_str();
    }
};

class FetcherInterface {
public:
    virtual std::string fetch(const std::string& full_url, const std::map<std::string, std::string>& body, int timeout) = 0;
    virtual void close() = 0;
};

class URLLibFetcher : public FetcherInterface {
public:
    std::string fetch(const std::string& full_url, const std::map<std::string, std::string>& body, int timeout) override {
        // Pseudocode: Create a request with the full_url and body
        // Send the request and return the response
    }

    void close() override {
        // Pseudocode: Close the fetcher
    }
};

class RequestsFetcher : public FetcherInterface {
public:
    int process_id;

    RequestsFetcher() : process_id(getpid()) {}

    void check_pid() {
        if (getpid() != process_id) {
            // Pseudocode: Create a new session
            process_id = getpid();
        }
    }

    std::string fetch(const std::string& full_url, const std::map<std::string, std::string>& body, int timeout) override {
        check_pid();
        // Pseudocode: Send a POST request to the full_url with the body and timeout
        // Raise an exception if the response status is not OK
        // Return the response text
    }

    void close() override {
        // Pseudocode: Close the session
    }
};

class RemoteScheduler {
public:
    std::string url;
    int connect_timeout;
    int rpc_retry_attempts;
    int rpc_retry_wait;
    bool rpc_log_retries;
    FetcherInterface* fetcher;

    RemoteScheduler(const std::string& url = "http://localhost:8082/", int connect_timeout = 10)
            : url(url), connect_timeout(connect_timeout) {
        // Pseudocode: Get the configuration
        // Set the rpc_retry_attempts, rpc_retry_wait, and rpc_log_retries based on the configuration
        // If requests is available, set the fetcher to a RequestsFetcher
        // Otherwise, set the fetcher to a URLLibFetcher
    }

    void close() {
        fetcher->close();
    }

    // Pseudocode: Define the get_retryer function

    std::string fetch(const std::string& url_suffix, const std::map<std::string, std::string>& body) {
        std::string full_url = urljoin(url, url_suffix);
        // Pseudocode: Get the scheduler retry
        // Try to fetch the response with the fetcher
        // If an exception is raised, raise an RPCError
        // Return the response
    }

    nlohmann::json request(const std::string& url, const nlohmann::json& data, int attempts = 3, bool allow_null = true) {
        std::map<std::string, std::string> body = {{"data", data.dump()}};

        for (int i = 0; i < attempts; i++) {
            std::string page = fetch(url, body);
            nlohmann::json response = nlohmann::json::parse(page)["response"];
            if (allow_null || !response.is_null()) {
                return response;
            }
        }
        throw RPCError("Received null response from remote scheduler " + url);
    }

    // Pseudocode: Define the RPC methods
};

#include <set>
#include <string>
#include <unordered_map>
#include <vector>
#include <ctime>

enum class Status {
    DISABLED, DONE, FAILED, PENDING, RUNNING, SUSPENDED, UNKNOWN, BATCH_RUNNING
};

class Step {
public:
    std::string id;
    std::set<std::string> stakeholders;
    std::set<std::string> workers;
    std::set<std::string> deps;
    Status status;
    time_t time;
    time_t updated;
    std::string worker_running;
    time_t time_running;
    std::string expl;
    int priority;
    std::unordered_map<std::string, std::string> resources;
    std::string family;
    std::string module;
    std::unordered_map<std::string, std::string> params;
    std::unordered_map<std::string, std::string> public_params;
    std::unordered_map<std::string, std::string> hidden_params;
    bool accepts_messages;
    std::string retry_policy;
    std::vector<time_t> failures;
    time_t first_failure_time;
    std::string tracking_url;
    std::string status_message;
    int progress_percentage;
    std::unordered_map<std::string, std::string> scheduler_message_responses;
    time_t scheduler_disable_time;
    bool runnable;
    bool batchable;
    std::string batch_id;

    Step(std::string step_id, Status status, std::set<std::string> deps);
    void set_params(std::unordered_map<std::string, std::string> params);
    bool is_batchable();
    void add_failure();
    int num_failures();
    bool has_excessive_failures();
    void clear_failures();
    std::string pretty_id();
};

class Worker {
public:
    std::string id;
    std::unordered_map<std::string, std::string> reference;
    time_t last_active;
    time_t last_get_work;
    time_t started;
    std::set<std::string> steps;
    std::unordered_map<std::string, std::string> info;
    bool disabled;
    std::vector<std::unordered_map<std::string, std::string>> rpc_messages;

    Worker(std::string worker_id, time_t last_active);
    void add_info(std::unordered_map<std::string, std::string> info);
    void update(std::unordered_map<std::string, std::string> worker_reference, bool get_work);
    bool prune(int worker_disconnect_delay);
    std::set<std::string> get_steps(Status status);
    bool is_trivial_worker();
    bool assistant();
    bool enabled();
    std::string state();
    void add_rpc_message(std::string name, std::unordered_map<std::string, std::string> kwargs);
    std::vector<std::unordered_map<std::string, std::string>> fetch_rpc_messages();
};

#include <string>
#include <map>
#include <vector>
#include <set>
#include <algorithm>
#include <ctime>
#include <cmath>

class Scheduler {
private:
    SimpleStepState _state;
    Step _make_step;
    std::map<std::string, int> _worker_requests;
    bool _paused;
    BatchNotifier _email_batcher;
    MetricsCollectors _metrics_collector;

public:
    Scheduler() {
        // Initialize variables
        _paused = false;
    }

    void load() {
        _state.load();
    }

    void dump() {
        _state.dump();
        _email_batcher.send_email();
    }

    void prune() {
        _prune_workers();
        _prune_steps();
        _prune_emails();
    }

    void _prune_workers() {
        // Implement worker pruning logic
    }

    void _prune_steps() {
        // Implement step pruning logic
    }

    void _prune_emails() {
        _email_batcher.update();
    }

    Worker _update_worker(std::string worker_id, Worker worker_reference, bool get_work) {
        // Implement worker update logic
    }

    void _update_priority(Step step, int prio, Worker worker) {
        // Implement priority update logic
    }

    void add_step_batcher(std::string worker, std::string step_family, std::vector<std::string> batched_args, float max_batch_size=std::numeric_limits<float>::infinity()) {
        _state.set_batcher(worker, step_family, batched_args, max_batch_size);
    }

    std::map<std::string, std::string> forgive_failures(std::string step_id) {
        // Implement failure forgiveness logic
    }

    std::map<std::string, std::string> mark_as_done(std::string step_id) {
        // Implement mark as done logic
    }

    void add_step(std::string step_id, std::string status, bool runnable, std::vector<std::string> deps, std::vector<std::string> new_deps, std::string expl, std::map<std::string, int> resources, int priority, std::string family, std::string module, std::map<std::string, std::string> params, std::map<std::string, std::string> param_visibilities, bool accepts_messages, bool assistant, std::string tracking_url, std::string worker, bool batchable, std::string batch_id, std::map<std::string, std::string> retry_policy_dict, std::vector<std::string> owners) {
        // Implement add step logic
    }

    void announce_scheduling_failure(std::string step_name, std::string family, std::map<std::string, std::string> params, std::string expl, std::vector<std::string> owners) {
        // Implement scheduling failure announcement logic
    }

    void add_worker(std::string worker, std::map<std::string, std::string> info) {
        _state.get_worker(worker).add_info(info);
    }

    void disable_worker(std::string worker) {
        _state.disable_workers({worker});
    }

    void set_worker_processes(std::string worker, int n) {
        _state.get_worker(worker).add_rpc_message("set_worker_processes", n);
    }

    std::map<std::string, std::string> send_scheduler_message(std::string worker, Step step, std::string content) {
        // Implement send scheduler message logic
    }

    void add_scheduler_message_response(std::string step_id, std::string message_id, std::string response) {
        // Implement add scheduler message response logic
    }

    std::map<std::string, std::string> get_scheduler_message_response(std::string step_id, std::string message_id) {
        // Implement get scheduler message response logic
    }

    bool has_step_history() {
        // Implement has step history logic
    }
    std::map<std::string, bool> is_pause_enabled() {
        return {{"enabled", _config.pause_enabled}};
    }

    std::map<std::string, bool> is_paused() {
        return {{"paused", _paused}};
    }

    void pause() {
        if (_config.pause_enabled) {
            _paused = true;
        }
    }

    void unpause() {
        if (_config.pause_enabled) {
            _paused = false;
        }
    }

    void update_resources(std::map<std::string, int> resources) {
        if (_resources.empty()) {
            _resources = {};
        }
        _resources.insert(resources.begin(), resources.end());
    }

    bool update_resource(std::string resource, int amount) {
        if (amount < 0) {
            return false;
        }
        _resources[resource] = amount;
        return true;
    }

};


#include <string>
#include <map>
#include <vector>
#include <functional>

class Step {
public:
    // Member variables
    static std::map<std::string, std::vector<std::function<void()>>> _event_callbacks;
    int priority = 0;
    bool disabled = false;
    std::map<std::string, int> resources;
    int worker_timeout = 0;
    float max_batch_size = std::numeric_limits<float>::infinity();
    std::string step_namespace = "__not_user_specified";
    std::string step_id;
    int __hash;

    // Member functions
    Step() {
        // Constructor logic
    }

    virtual ~Step() {
        // Destructor logic
    }

    virtual bool batchable() {
        // To be implemented in derived classes
        return false;
    }

    virtual int retry_count() {
        // To be implemented in derived classes
        return 0;
    }

    virtual int disable_hard_timeout() {
        // To be implemented in derived classes
        return 0;
    }

    virtual int disable_window() {
        // To be implemented in derived classes
        return 0;
    }

    virtual std::string owner_email() {
        // To be implemented in derived classes
        return "";
    }

    virtual bool use_cmdline_section() {
        // To be implemented in derived classes
        return true;
    }

    virtual bool accepts_messages() {
        // To be implemented in derived classes
        return false;
    }

    virtual std::string step_module() {
        // To be implemented in derived classes
        return "";
    }

    virtual bool complete() {
        // To be implemented in derived classes
        return false;
    }

    virtual void run() {
        // To be implemented in derived classes
    }

    virtual std::string on_failure(std::exception& exception) {
        // To be implemented in derived classes
        return "";
    }

    virtual void on_success() {
        // To be implemented in derived classes
    }

    // Other methods are omitted as they cannot be directly translated to C++
};

#include <vector>
#include <functional>

class MixinNaiveBulkComplete {
public:
    template <typename T>
    static std::vector<T> bulk_complete(std::vector<T> parameter_tuples) {
        std::vector<T> generated_tuples;
        for (auto& parameter_tuple : parameter_tuples) {
            if (parameter_tuple.complete()) {
                generated_tuples.push_back(parameter_tuple);
            }
        }
        return generated_tuples;
    }
};

class DynamicRequirements {
private:
    std::vector<Step> requirements;
    std::function<bool(std::function<bool(Step)>)> custom_complete;
public:
    DynamicRequirements(std::vector<Step> requirements, std::function<bool(std::function<bool(Step)>)> custom_complete = nullptr)
            : requirements(requirements), custom_complete(custom_complete) {}

    bool complete(std::function<bool(Step)> complete_fn = nullptr) {
        if (complete_fn == nullptr) {
            complete_fn = [](Step step) { return step.complete(); };
        }

        if (custom_complete) {
            return custom_complete(complete_fn);
        }

        for (auto& requirement : requirements) {
            if (!complete_fn(requirement)) {
                return false;
            }
        }
        return true;
    }
};

class ExternalStep : public Step {
public:
    // The run method is not implemented, signifying that the output is generated outside of Trun.
    void run() override {
        throw std::logic_error("The run method is not implemented for ExternalStep.");
    }
};


#include <vector>
#include <map>
#include <functional>
#include <algorithm>
#include <typeinfo>
#include <type_traits>

class Step;

// Function to create a copy of a Step object or class
template <typename T>
T* externalize(T* stepclass_or_stepobject) {
    // Create a copy of the object or class
    T* copied_value = new T(*stepclass_or_stepobject);

    // If it's a class, create a new class that inherits from it and set its run method to null
    if (std::is_class<T>::value) {
        class _CopyOfClass : public T {
        public:
            _CopyOfClass() : T() {
                // Set the run method to null
                this->run = nullptr;
            }
        };

        return new _CopyOfClass();
    } else {
        // If it's an object, set its run method to null
        copied_value->run = nullptr;
        return copied_value;
    }
}

class WrapperStep : public Step {
public:
    bool complete() {
        // This method should return true if all the requirements of the step are complete
        // This is a placeholder implementation and should be replaced with the actual logic
        return true;
    }
};

class Config : public Step {
    // This class is for configuration
    // The implementation depends on the specific configuration requirements
};

std::vector<Step*> getpaths(std::vector<Step*> struct_) {
    // This function maps all Steps in a structured data object to their output
    // This is a placeholder implementation and should be replaced with the actual logic
    return struct_;
}

std::vector<Step*> flatten(std::vector<Step*> struct_) {
    // This function creates a flat list of all items in structured output
    // This is a placeholder implementation and should be replaced with the actual logic
    return struct_;
}

std::vector<Step*> flatten_output(Step* step) {
    // This function lists all output targets by recursively walking output-less (wrapper) steps
    // This is a placeholder implementation and should be replaced with the actual logic
    return std::vector<Step*>();
}


#include <string>
#include <map>
#include <regex>
#include <algorithm>
#include <openssl/md5.h>

// Constants
const int STEP_ID_INCLUDE_PARAMS = 3;
const int STEP_ID_TRUNCATE_PARAMS = 16;
const int STEP_ID_TRUNCATE_HASH = 10;
const std::regex STEP_ID_INVALID_CHAR_REGEX("[^A-Za-z0-9_]");
const std::string _SAME_AS_PYTHON_MODULE = "_same_as_python_module";

// Global variables
std::map<std::string, std::string> _default_namespace_dict;

// Function to set namespace of steps declared after the call
void namespace_(std::string namespace_ = "", std::string scope = "") {
    _default_namespace_dict[scope] = namespace_;
}

// Function to set the namespace to the __module__ of the step class
void auto_namespace(std::string scope = "") {
    namespace_(_SAME_AS_PYTHON_MODULE, scope);
}

// Function to return a canonical string used to identify a particular step
std::string step_id_str(std::string step_family, std::map<std::string, std::string> params) {
    // Convert params to JSON string
    std::string param_str = json(params);  // This function needs to be implemented

    // Compute MD5 hash of param_str
    unsigned char digest[MD5_DIGEST_LENGTH];
    MD5((unsigned char*)param_str.c_str(), param_str.size(), (unsigned char*)&digest);

    char mdString[33];
    for(int i = 0; i < 16; i++)
        sprintf(&mdString[i*2], "%02x", (unsigned int)digest[i]);

    std::string param_hash(mdString);

    // Generate param_summary
    std::string param_summary = "";
    int count = 0;
    for (auto const& param : params) {
        if (count >= STEP_ID_INCLUDE_PARAMS) {
            break;
        }
        param_summary += param.second.substr(0, STEP_ID_TRUNCATE_PARAMS) + "_";
        count++;
    }

    // Replace invalid characters in param_summary
    param_summary = std::regex_replace(param_summary, STEP_ID_INVALID_CHAR_REGEX, "_");

    return step_family + "_" + param_summary + "_" + param_hash.substr(0, STEP_ID_TRUNCATE_HASH);
}

// Exception class
class BulkCompleteNotImplementedError : public std::logic_error {
public:
    BulkCompleteNotImplementedError(const std::string& message) : std::logic_error(message) {}
};