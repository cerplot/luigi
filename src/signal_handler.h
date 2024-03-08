#pragma once
#include <csignal>
#include <iostream>

class SignalHandler {
public:
    static void registerSignalHandler();

private:
    static void handle(int signum);
};
