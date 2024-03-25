# src/core/CMakeLists.txt
set(SOURCE_FILES
        external_program_step.cc
)

add_library(steps ${SOURCE_FILES})

target_include_directories(steps PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
