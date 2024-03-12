#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <ctime>
#include <regex>
#include <fstream>
#include <filesystem>
#include "target.h"

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
    FileAlreadyExists(const std::string& message) : FileSystemException(message) {}
};

class MissingParentDirectory : public FileSystemException {
public:
    MissingParentDirectory(const std::string& message) : FileSystemException(message) {}
};

class NotADirectory : public FileSystemException {
public:
    NotADirectory(const std::string& message) : FileSystemException(message) {}
};

// FileSystem abstract class
class FileSystem {
public:
    virtual ~FileSystem() = default; // Virtual destructor

    // Pure virtual functions
    virtual bool exists(const std::string& path) const = 0;
    virtual void remove(const std::string& path, bool recursive = true, bool skip_trash = true) = 0;
    virtual void mkdir(const std::string& path, bool parents = true, bool raise_if_exists = false) = 0;
    virtual bool isdir(const std::string& path) const = 0;
    virtual std::vector<std::string> listdir(const std::string& path) const = 0;
    virtual void move(const std::string& path, const std::string& dest) = 0;
    virtual void rename_dont_move(const std::string& path, const std::string& dest) = 0;
    virtual void rename(const std::string& path, const std::string& dest) = 0;
    virtual void copy(const std::string& path, const std::string& dest) = 0;
    virtual void copy(const std::string& old_path, const std::string& new_path, bool raise_if_exists = false) = 0;
};

#include <random>


class FileSystemTarget : public Target {
public:
    FileSystemTarget(const std::string& path) : path(path) {}
    virtual ~FileSystemTarget() = default;

    // Override the pure virtual function from the base class
    virtual bool exists() const override {
        // Implementation depends on the specific FileSystem
        return fs().exists(path);
    }

    // Pure virtual function
    virtual FileSystem& fs() const = 0;

    // Other methods
    virtual void open(const std::string& mode) = 0;
    virtual void remove() {
        fs().remove(path);
    }

    void _touchz() {
        std::ofstream ofs(path);
    }

    std::string _trailing_slash() const {
        char last_char = path.back();
        if (last_char == '/' || last_char == '\\') {
            return std::string(1, last_char);
        } else {
            return "";
        }
    }
    friend std::ostream& operator<<(std::ostream& os, const FileSystemTarget& obj) {
        os << obj.path;
        return os;
    }
    std::string getPath() const {
        return path;
    }

protected:
    std::string path;
};


class TemporaryPath {
public:
    TemporaryPath(FileSystemTarget& target) : target(target) {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 9999999999);

        std::string slashless_path = target.getPath();
        slashless_path.erase(std::remove(slashless_path.end() - 1, slashless_path.end(), '/'), slashless_path.end());
        slashless_path.erase(std::remove(slashless_path.end() - 1, slashless_path.end(), '\\'), slashless_path.end());

        temp_path = slashless_path + "-trun-tmp-" + std::to_string(dis(gen)) + target._trailing_slash();

        std::string tmp_dir = slashless_path.substr(0, slashless_path.find_last_of("/\\"));
        if (!tmp_dir.empty()) {
            target.fs().mkdir(tmp_dir, true, false);
        }
    }

    ~TemporaryPath() {
        target.fs().rename_dont_move(temp_path, target.getPath());
    }

    std::string get() const {
        return temp_path;
    }

private:
    FileSystemTarget& target;
    std::string temp_path;
};



class AtomicLocalFile {
public:
    AtomicLocalFile(const std::string& path) : path(path) {
        tmp_path = generate_tmp_path(path);
        ofs.open(tmp_path, std::ios::out);
    }

    ~AtomicLocalFile() {
        if (std::filesystem::exists(tmp_path)) {
            std::filesystem::remove(tmp_path);
        }
    }

    void close() {
        ofs.close();
        move_to_final_destination();
    }

    virtual std::string generate_tmp_path(const std::string& path) {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 9999999999);
        return std::filesystem::temp_directory_path().string() + "/trun-s3-tmp-" + std::to_string(dis(gen));
    }

    virtual void move_to_final_destination() = 0;

    std::string get_tmp_path() const {
        return tmp_path;
    }
    std::string getPath() const {
        return path;
    }

private:
    std::string path;
    std::string tmp_path;
    std::ofstream ofs;
};

class atomic_file : public AtomicLocalFile {
public:
    atomic_file(const std::string& path) : AtomicLocalFile(path) {}

    void move_to_final_destination() override {
        std::filesystem::rename(get_tmp_path(), getPath());
    }

    std::string generate_tmp_path(const std::string& path) override {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(0, 9999999999);
        return path + "-trun-tmp-" + std::to_string(dis(gen));
    }
};


class LocalFileSystem : public FileSystem {
public:
    void copy(const std::string& old_path, const std::string& new_path, bool raise_if_exists = false) override {
        if (raise_if_exists && std::filesystem::exists(new_path)) {
            throw std::runtime_error("Destination exists: " + new_path);
        }
        std::filesystem::path d = std::filesystem::path(new_path).parent_path();
        if (!d.empty() && !std::filesystem::exists(d)) {
            mkdir(d.string());
        }
        std::filesystem::copy(old_path, new_path);
    }

    bool exists(const std::string& path) const override {
        return std::filesystem::exists(path);
    }

    void mkdir(const std::string& path, bool parents = true, bool raise_if_exists = false) override {
        if (exists(path)) {
            if (raise_if_exists) {
                throw FileAlreadyExists("File already exists");
            } else if (!isdir(path)) {
                throw NotADirectory("Not A Directory");
            } else {
                return;
            }
        }

        if (parents) {
            std::filesystem::create_directories(path);
        } else {
            if (!std::filesystem::exists(std::filesystem::path(path).parent_path())) {
                throw MissingParentDirectory("Missing Parent Directory");
            }
            std::filesystem::create_directory(path);
        }
    }

    bool isdir(const std::string& path) const override {
        return std::filesystem::is_directory(path);
    }

    std::vector<std::string> listdir(const std::string& path) const override {
        std::vector<std::string> files;
        for (const auto & entry : std::filesystem::recursive_directory_iterator(path)) {
            files.push_back(entry.path().string());
        }
        return files;
    }

    void remove(const std::string& path, bool recursive = true) override {
        if (recursive && isdir(path)) {
            std::filesystem::remove_all(path);
        } else {
            std::filesystem::remove(path);
        }
    }

    void move(const std::string& old_path, const std::string& new_path, bool raise_if_exists = false) override {
        if (raise_if_exists && std::filesystem::exists(new_path)) {
            throw FileAlreadyExists("Destination exists: " + new_path);
        }
        std::filesystem::path d = std::filesystem::path(new_path).parent_path();
        if (!d.empty() && !std::filesystem::exists(d)) {
            mkdir(d.string());
        }
        std::filesystem::rename(old_path, new_path);
    }

    void rename_dont_move(const std::string& path, const std::string& dest) override {
        move(path, dest, true);
    }
};

class LocalTarget : public FileSystemTarget {
public:
    LocalTarget(std::string path = "", std::string format = "", bool is_tmp = false) : FileSystemTarget(path), format(format), is_tmp(is_tmp) {
        if (format.empty()) {
            format = get_default_format();
        }

        if (path.empty()) {
            if (!is_tmp) {
                throw std::runtime_error("path or is_tmp must be set");
            }
            std::random_device rd;
            std::mt19937 gen(rd());
            std::uniform_int_distribution<> dis(0, 9999999999);
            path = std::filesystem::temp_directory_path().string() + "/trun-tmp-" + std::to_string(dis(gen));
        }
    }

    void makedirs() {
        std::filesystem::path normpath = std::filesystem::path(path).lexically_normal();
        std::filesystem::path parentfolder = normpath.parent_path();
        if (!parentfolder.empty()) {
            std::filesystem::create_directories(parentfolder);
        }
    }

    std::fstream open(std::string mode = "r") {
        std::string rwmode = mode;
        rwmode.erase(std::remove(rwmode.begin(), rwmode.end(), 'b'), rwmode.end());
        rwmode.erase(std::remove(rwmode.begin(), rwmode.end(), 't'), rwmode.end());

        if (rwmode == "w") {
            makedirs();
            return std::fstream(path, std::ios::out);
        } else if (rwmode == "r") {
            return std::fstream(path, std::ios::in);
        } else {
            throw std::runtime_error("mode must be 'r' or 'w' (got: " + mode + ")");
        }
    }

    void move(const std::string& new_path, bool raise_if_exists = false) override {
        if (raise_if_exists && std::filesystem::exists(new_path)) {
            throw FileAlreadyExists("Destination exists: " + new_path);
        }
        std::filesystem::path d = std::filesystem::path(new_path).parent_path();
        if (!d.empty() && !std::filesystem::exists(d)) {
            mkdir(d.string());
        }
        std::filesystem::rename(path, new_path);
    }

    void mkdir(const std::string& path, bool parents = true, bool raise_if_exists = false) override {
        if (std::filesystem::exists(path)) {
            if (raise_if_exists) {
                throw FileAlreadyExists("File already exists");
            } else if (!std::filesystem::is_directory(path)) {
                throw NotADirectory("Not A Directory");
            } else {
                return;
            }
        }

        if (parents) {
            std::filesystem::create_directories(path);
        } else {
            if (!std::filesystem::exists(std::filesystem::path(path).parent_path())) {
                throw MissingParentDirectory("Missing Parent Directory");
            }
            std::filesystem::create_directory(path);
        }
    }

    void move_dir(std::string new_path) {
        move(new_path, false);
    }

    void remove() {
        fs().remove(path);
    }

    void copy(std::string new_path, bool raise_if_exists = false) {
        fs().copy(path, new_path, raise_if_exists);
    }

    std::string fn() {
        std::cout << "Use LocalTarget.path to reference filename" << std::endl;
        return path;
    }

    ~LocalTarget() {
        if (is_tmp && exists()) {
            remove();
        }
    }

private:
    std::string format;
    bool is_tmp;
};
