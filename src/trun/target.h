#ifndef TARGET_H
#define TARGET_H

#include <string>
#include <vector>
#include <fstream>

// Target abstract class
class Target {
public:
    virtual ~Target() = default;
    virtual bool exists() const = 0;  // Pure virtual function
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
};


class FileSystemTarget : public Target {
public:
    FileSystemTarget(const std::string& path);
    virtual ~FileSystemTarget() = default;

    // Override the pure virtual function from the base class
    virtual bool exists() const override;

    // Pure virtual function
    virtual FileSystem& fs() const = 0;

    // Other methods
    virtual void open(const std::string& mode);
    virtual void remove();

    void _touchz();

    std::string _trailing_slash() const;

    friend std::ostream& operator<<(std::ostream& os, const FileSystemTarget& obj);
    std::string getPath() const {
        return path;
    }

protected:
    std::string path;
};

#endif //TARGET_H