cmake_minimum_required(VERSION 3.24)
project(
        untitled7
        VERSION 0.1
        DESCRIPTION "A simple C++ project with CMake"
        LANGUAGES CXX
)
set(CMAKE_CXX_STANDARD 20)

# Add the executable
add_executable(${PROJECT_NAME} main.cpp)

# Specify the include directories for the target
target_include_directories(${PROJECT_NAME} PRIVATE "tomlplusplus-3.4.0/include/toml++")
target_include_directories(${PROJECT_NAME} PRIVATE "src")

# Enable testing
enable_testing()

# Add the subdirectories
add_subdirectory(src)
add_subdirectory(test)

# Link the libraries
target_link_libraries(${PROJECT_NAME} PRIVATE ${PROJECT_NAME}_lib)