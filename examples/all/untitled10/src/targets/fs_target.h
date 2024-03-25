#pragma once
#include <string>
#include "target.h"


class FileSystemTarget : public Target {
public:
    FileSystemTarget(const std::string& path);
    virtual ~FileSystemTarget() = default;

    virtual bool exists() const override;
    virtual FileSystem& fs() const = 0;
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
