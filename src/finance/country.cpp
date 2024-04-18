#include <map>
#include <string>

class CountryCode {
public:
    static std::map<std::string, std::string> codes;

    static void initialize() {
        codes["ARGENTINA"] = "AR";
        codes["AUSTRALIA"] = "AU";
        codes["AUSTRIA"] = "AT";
        codes["BELGIUM"] = "BE";
        codes["BRAZIL"] = "BR";
        codes["CANADA"] = "CA";
        codes["CHILE"] = "CL";
        codes["CHINA"] = "CN";
        codes["COLOMBIA"] = "CO";
        codes["CZECH_REPUBLIC"] = "CZ";
        codes["DENMARK"] = "DK";
        codes["FINLAND"] = "FI";
        codes["FRANCE"] = "FR";
        codes["GERMANY"] = "DE";
        codes["GREECE"] = "GR";
        codes["HONG_KONG"] = "HK";
        codes["HUNGARY"] = "HU";
        codes["INDIA"] = "IN";
        codes["INDONESIA"] = "ID";
        codes["IRELAND"] = "IE";
        codes["ISRAEL"] = "IL";
        codes["ITALY"] = "IT";
        codes["JAPAN"] = "JP";
        codes["MALAYSIA"] = "MY";
        codes["MEXICO"] = "MX";
        codes["NETHERLANDS"] = "NL";
        codes["NEW_ZEALAND"] = "NZ";
        codes["NORWAY"] = "NO";
        codes["PAKISTAN"] = "PK";
        codes["PERU"] = "PE";
        codes["PHILIPPINES"] = "PH";
        codes["POLAND"] = "PL";
        codes["PORTUGAL"] = "PT";
        codes["RUSSIA"] = "RU";
        codes["SINGAPORE"] = "SG";
        codes["SOUTH_AFRICA"] = "ZA";
        codes["SOUTH_KOREA"] = "KR";
        codes["SPAIN"] = "ES";
        codes["SWEDEN"] = "SE";
        codes["SWITZERLAND"] = "CH";
        codes["TAIWAN"] = "TW";
        codes["THAILAND"] = "TH";
        codes["TURKEY"] = "TR";
    }

    static std::string code(const std::string& name) {
        return codes[name];
    }
};

// Initialize the static member
std::map<std::string, std::string> CountryCode::codes = {};
