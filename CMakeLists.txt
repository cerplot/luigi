cmake_minimum_required(VERSION  3.22)

project(trunc
    VERSION 0.0
    DESCRIPTION "A simple C++ project"
    HOMEPAGE_URL https://github.com/PacktPublishing/CMake-Best-Practices
    LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(hello_world)
target_sources(hello_world PRIVATE src/main.cpp)
