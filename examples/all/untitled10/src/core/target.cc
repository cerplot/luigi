#include <filesystem>
#include <iostream>
#include <fstream>
#include <vector>
#include <stdexcept>
#include "target.h"

namespace te {

    bool FileTarget::exists() const {
        return std::filesystem::exists(path);
    }

    static_assert(sizeof(double) * 8 == 64, "double is not 64 bits");
    static_assert(sizeof(float) * 8 == 32, "float is not 32 bits");

    class BinaryFile {
    public:
        BinaryFile(const std::string& filename) : filename_(filename) {}
        bool exists() const {
            return std::filesystem::exists(filename_);
        }
        std::streamsize size() const {
            return std::filesystem::file_size(filename_);
        }
        void write(const std::vector<char>& data) {
            writeToFile(data, std::ios::binary);
        }
        void append(const std::vector<char>& data) {
            writeToFile(data, std::ios::binary | std::ios::app);
        }
        std::vector<char> read() {
            std::ifstream input_file(filename_, std::ios::binary);
            if (!input_file) {
                throw std::runtime_error("Failed to open file: " + filename_);
            }
            return std::vector<char>((std::istreambuf_iterator<char>(input_file)), std::istreambuf_iterator<char>());
        }
        std::string filename() const {
            return filename_;
        }
    private:
        std::string filename_;
        void writeToFile(const std::vector<char>& data, std::ios::openmode mode) {
            std::ofstream output_file(filename_, mode);
            if (!output_file) {
                throw std::runtime_error("Failed to open file: " + filename_);
            }
            output_file.write(data.data(), data.size());
            if (!output_file) {
                throw std::runtime_error("Failed to write to file: " + filename_);
            }
        }
    };

    template <typename T>
    class ArrayFile {
    public:
        static_assert(std::is_trivially_copyable<T>::value, "T must be trivially copyable");
        ArrayFile(const std::string& filename) : file_(filename) {}
        void write(const std::vector<T>& array) {
            writeOrAppend(array, false);
        }
        void append(const std::vector<T>& array) {
            writeOrAppend(array, true);
        }
        std::vector<T> read() {
            if (file_.size() == 0) {
                throw std::runtime_error("Attempted to read an empty file: " + file_.filename());
            }
            std::vector<char> data = file_.read();
            if (data.size() % sizeof(T) != 0) {
                throw std::runtime_error("File size is not a multiple of the size of T: " + file_.filename());
            }
            return convert(data);
        }
    private:
        BinaryFile file_;
        void writeOrAppend(const std::vector<T>& array, bool append) {
            if (array.empty()) {
                throw std::runtime_error("Attempted to " + std::string(append ? "append" : "write") + " an empty array to file: " + file_.filename());
            }
            std::vector<char> data(reinterpret_cast<const char*>(array.data()), reinterpret_cast<const char*>(array.data()) + array.size() * sizeof(T));
            if (append) {
                file_.append(data);
            } else {
                if (file_.exists()) {
                    throw std::runtime_error("File already exists: " + file_.filename());
                }
                file_.write(data);
            }
        }
        std::vector<T> convert(const std::vector<char>& data) {
            return std::vector<T>(
                    reinterpret_cast<const T*>(data.data()),
                    reinterpret_cast<const T*>(data.data()) + data.size() / sizeof(T));
        }
    };

}
