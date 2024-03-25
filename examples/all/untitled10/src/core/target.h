#pragma once

#include <string>
#include <vector>


namespace te {
    class Target {
    public:
        virtual ~Target() = default;
        virtual bool exists() const = 0;
    };

    class FileTarget : public Target {
    public:
        FileTarget(const std::string &path);

        virtual ~FileTarget() = default;

        virtual bool exists() const override;

        virtual void open(const std::string &mode);

        virtual void remove();

        void _touchz();

        std::string _trailing_slash() const;

        std::string getPath() const {
            return path;
        }
    private:
        std::string path;
    };

}