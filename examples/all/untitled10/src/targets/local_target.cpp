#include <string>

namespace te {

    LocalTarget::LocalTarget(std::string path = "", std::string format = ""):
    FileSystemTarget(path){
        if (path.empty()) {
            throw std::runtime_error("path or is_tmp must be set");
        }
    }

    void LocalTarget::makedirs() {
        std::filesystem::path normpath = std::filesystem::path(path).lexically_normal();
        std::filesystem::path parentfolder = normpath.parent_path();
        if (!parentfolder.empty()) {
            std::filesystem::create_directories(parentfolder);
        }
    }

    std::fstream LocalTarget::open(std::string mode = "r") {
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

    void LocalTarget::move(const std::string &new_path, bool raise_if_exists = false) override {
        if (raise_if_exists && std::filesystem::exists(new_path)) {
            throw FileAlreadyExists("Destination exists: " + new_path);
        }
        std::filesystem::path d = std::filesystem::path(new_path).parent_path();
        if (!d.empty() && !std::filesystem::exists(d)) {
            mkdir(d.string());
        }
        std::filesystem::rename(path, new_path);
    }

    void LocalTarget::mkdir(const std::string &path, bool parents = true, bool raise_if_exists = false) override {
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

    void LocalTarget::move_dir(std::string new_path) {
        move(new_path, false);
    }

    void LocalTarget::remove() {
        fs().remove(path);
    }

    void LocalTarget::copy(std::string new_path, bool raise_if_exists = false) {
        fs().copy(path, new_path, raise_if_exists);
    }

    std::string LocalTarget::fn() {
        std::cout << "Use LocalTarget.path to reference filename" << std::endl;
        return path;
    }

    LocalTarget::~LocalTarget() {}
}
