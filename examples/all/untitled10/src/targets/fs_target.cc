#include <string>
namespace te {

    FileSystemTarget::FileSystemTarget(const std::string &path) : path(path) {}

    // Override the pure virtual function from the base class
    virtual bool FileSystemTarget::exists() const override {
        // Implementation depends on the specific FileSystem
        return fs().exists(path);
    }

    // Pure virtual function
    virtual FileSystem &FileSystemTarget::fs() const = 0;

    // Other methods
    virtual void FileSystemTarget::open(const std::string &mode) = 0;

    virtual void FileSystemTarget::remove() {
        fs().remove(path);
    }

    void FileSystemTarget::_touchz() {
        std::ofstream ofs(path);
    }

    std::string FileSystemTarget::_trailing_slash() const {
        char last_char = path.back();
        if (last_char == '/' || last_char == '\\') {
            return std::string(1, last_char);
        } else {
            return "";
        }
    }

    std::ostream &operator<<(std::ostream &os, const FileSystemTarget &obj) {
        os << obj.path;
        return os;
    }

    std::string FileSystemTarget::getPath() const {
        return path;
    }

}