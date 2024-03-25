#pragma once

#include <string>
#include <vector>

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
