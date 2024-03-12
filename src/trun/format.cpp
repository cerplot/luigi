#include <fstream>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <array>

class FileWrapper {
private:
    std::fstream _subpipe;

public:
    FileWrapper(const std::string& filename, std::ios_base::openmode mode = std::ios_base::in | std::ios_base::out)
            : _subpipe(filename, mode) {}

    std::fstream& get() {
        return _subpipe;
    }

    void open(const std::string& filename, std::ios_base::openmode mode = std::ios_base::in | std::ios_base::out) {
        _subpipe.open(filename, mode);
    }

    void close() {
        _subpipe.close();
    }

    // Mimic Python's __iter__ method by providing begin and end methods for range-based for loop
    std::istream_iterator<std::string> begin() {
        return std::istream_iterator<std::string>(_subpipe);
    }

    std::istream_iterator<std::string> end() {
        return std::istream_iterator<std::string>();
    }
};

class InputPipeProcessWrapper {
private:
    std::string command;
    std::string tmp_file;
    std::fstream& input_pipe;
    bool original_input;
    FILE* process;

public:
    InputPipeProcessWrapper(const std::string& command, std::fstream& input_pipe)
            : command(command), input_pipe(input_pipe), original_input(true) {
        // If input_pipe is not a file, write its contents to a temporary file
        if (!input_pipe.is_open()) {
            original_input = false;
            tmp_file = "/tmp/trun-process_tmp";
            std::ofstream tmp(tmp_file, std::ios::binary);
            tmp << input_pipe.rdbuf();
            tmp.close();
            this->input_pipe.open(tmp_file, std::ios::in);
        }
    }

    ~InputPipeProcessWrapper() {
        if (!original_input) {
            std::remove(tmp_file.c_str());
        }
    }
    void create_subprocess() {
        signal(SIGPIPE, SIG_DFL);
        process = popen(command.c_str(), "r");
        if (!process) {
            throw std::runtime_error("popen() failed!");
        }
    }
    void _finish() {
        if (process) {
            pclose(process);
            process = nullptr;
        }
        if (!original_input) {
            std::remove(tmp_file.c_str());
        }
        if (input_pipe.is_open()) {
            input_pipe.close();
        }
    }
    void close() {
        _finish();
    }

    std::string read() {
        std::array<char, 128> buffer;
        std::string result;
        while (fgets(buffer.data(), buffer.size(), process) != nullptr) {
            result += buffer.data();
        }
        return result;
    }

    bool readable() {
        return input_pipe.is_open() && input_pipe.good();
    }

    bool writable() {
        return false;  // This class is not designed for writing
    }

    bool seekable() {
        return false;  // This class is not designed for seeking
    }
    class iterator {
    public:
        iterator(FILE* process) : process(process), done(false) {
            ++(*this);
        }

        iterator& operator++() {
            if (fgets(buffer.data(), buffer.size(), process) != nullptr) {
                current_line = buffer.data();
            } else {
                done = true;
            }
            return *this;
        }

        bool operator!=(const iterator& other) const {
            return !done || !other.done;
        }

        const std::string& operator*() const {
            return current_line;
        }

    private:
        FILE* process;
        std::array<char, 128> buffer;
        std::string current_line;
        bool done;
    };

    iterator begin() {
        return iterator(process);
    }

    iterator end() {
        return iterator(nullptr);
    }



};

class Format {
public:
    virtual ~Format() = default;

    static void pipe_reader(std::fstream& input_pipe) {
        throw std::logic_error("Not implemented");
    }

    static void pipe_writer(std::fstream& output_pipe) {
        throw std::logic_error("Not implemented");
    }

    friend Format operator>>(Format& a, Format& b) {
        return ChainFormat(a, b);
    }
};
# include <vector>

class ChainFormat : public Format {
private:
    std::vector<Format*> args;
    std::string input;
    std::string output;

public:
    ChainFormat(std::vector<Format*> args, bool check_consistency = true) : args(args) {
        try {
            input = args[0]->getInput();
        } catch (std::exception&) {
            // Ignore exception
        }
        try {
            output = args.back()->getOutput();
        } catch (std::exception&) {
            // Ignore exception
        }
        if (!check_consistency) {
            return;
        }
        for (size_t i = 0; i < args.size() - 1; ++i) {
            if (args[i]->getOutput() != args[i + 1]->getInput()) {
                throw std::logic_error(
                        "The format chaining is not valid, " + args[i + 1]->getName() +
                        " expects " + args[i + 1]->getInput() +
                        " but " + args[i]->getName() +
                        " provides " + args[i]->getOutput()
                );
            }
        }
    }

    static void pipe_reader(std::fstream& input_pipe) {
        for (auto it = args.rbegin(); it != args.rend(); ++it) {
            (*it)->pipe_reader(input_pipe);
        }
    }

    static void pipe_writer(std::fstream& output_pipe) {
        for (auto it = args.rbegin(); it != args.rend(); ++it) {
            (*it)->pipe_writer(output_pipe);
        }
    }
};

