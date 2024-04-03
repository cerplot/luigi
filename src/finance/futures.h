#pragma once

#include <map>

std::map<char, int> CMES_CODE_TO_MONTH = {
        {'F', 1}, {'G', 2}, {'H', 3}, {'J', 4}, {'K', 5}, {'M', 6},
        {'N', 7}, {'Q', 8}, {'U', 9}, {'V', 10}, {'X', 11}, {'Z', 12}
};

std::map<int, char> MONTH_TO_CMES_CODE = {
        {1, 'F'}, {2, 'G'}, {3, 'H'}, {4, 'J'}, {5, 'K'}, {6, 'M'},
        {7, 'N'}, {8, 'Q'}, {9, 'U'}, {10, 'V'}, {11, 'X'}, {12, 'Z'}
};
