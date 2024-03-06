# Define the source files
set(SOURCES
        config_parser.cpp
        trade_engine.cpp
        config_parser.h
        trun/target.h
        trun/target.cpp
        trun/scheduler.h
        trun/scheduler.cpp
        trun/worker.cpp
        DataLayer.cpp
        wrahhper.cpp
)

# Add the library
add_library(${PROJECT_NAME}_lib  ${SOURCES})

# Specify the include directories for the target
target_include_directories(${PROJECT_NAME}_lib PRIVATE "../tomlplusplus-3.4.0/include/toml++")
add_subdirectory(pybind11)
pybind11_add_module(DataLayer main.cpp)
