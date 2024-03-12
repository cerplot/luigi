#pragma once
#include <iostream>
using namespace std::string_view_literals;
static constexpr auto source = R"(
str = "hello world"

numbers = [ 1, 2, 3, "four", 5.0 ]
vegetables = [ "tomato", "onion", "mushroom", "lettuce" ]
minerals = [ "quartz", "iron", "copper", "diamond" ]

[animals]
cats = [ "tiger", "lion", "puma" ]
birds = [ "macaw", "pigeon", "canary" ]
fish = [ "salmon", "trout", "carp" ]
)"sv;
