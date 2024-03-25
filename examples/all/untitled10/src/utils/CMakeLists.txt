add_library(utils logger.cc config.cc)
target_include_directories(utils PUBLIC .)
target_include_directories(utils PUBLIC "../../lib/tomlpp/include/toml++")