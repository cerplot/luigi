# src/core/CMakeLists.txt
set(SOURCE_FILES
        step.cc
        step.h
        target.h
        parm.cc
        parm.h
        step_factory.cc
        step_factory.h
        step_register.cc
        step_register.h
)

add_library(core ${SOURCE_FILES})

target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
