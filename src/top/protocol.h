enum class DATASOURCE_TYPE {
    AS_TRADED_EQUITY,
    MERGER,
    SPLIT,
    DIVIDEND,
    TRADE,
    TRANSACTION,
    ORDER,
    EMPTY,
    DONE,
    CUSTOM,
    BENCHMARK,
    COMMISSION,
    CLOSE_POSITION
};



class Position {
private:
    std::string underlying_position;
    // Add other attributes as needed

public:
    Position(std::string underlying_position) {
        this->underlying_position = underlying_position;
    }

    std::string getUnderlyingPosition() {
        return underlying_position;
    }

    // Add other getter methods as needed

    void print() {
        std::cout << "Position(" << underlying_position << ")" << std::endl;
    }
};


class Positions {
private:
    std::map<std::string, Position> positions;

public:
    Position& operator[](const std::string& key) {
        if (positions.find(key) == positions.end()) {
            if (isAsset(key)) {
                positions[key] = Position(InnerPosition(key));
            } else {
                throw std::invalid_argument("Position lookup expected a value of type Asset but got " + key);
            }
        }
        return positions[key];
    }

    bool isAsset(const std::string& key) {
        // Implement this function to check if the key is an Asset.
        // This is a placeholder implementation.
        return true;
    }
};
