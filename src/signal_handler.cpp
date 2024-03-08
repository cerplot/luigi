class SignalHandler {
public:
    static void registerSignalHandler() {
        signal(SIGINT, handle);
    }

private:
    static void handle(int signum) {
        std::cout << "Interrupt signal (" << signum << ") received.\n";
        terminate_te = true;
    }
};
