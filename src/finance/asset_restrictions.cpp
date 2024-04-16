#include <set>
#include <map>
#include <vector>
#include <algorithm>
#include <stdexcept>

enum class RestrictionStates {
    ALLOWED,
    FROZEN
};

struct Restriction {
    std::string asset;
    std::string effective_date;
    RestrictionStates state;
};

class Restrictions {
public:
    virtual bool is_restricted(std::string asset, std::string dt) = 0;
};

class _UnionRestrictions : public Restrictions {
public:
    _UnionRestrictions(std::vector<Restrictions*> sub_restrictions) {
        for (auto r : sub_restrictions) {
            if (dynamic_cast<NoRestrictions*>(r) == nullptr) {
                this->sub_restrictions.push_back(r);
            }
        }
    }

    bool is_restricted(std::string asset, std::string dt) override {
        for (auto r : sub_restrictions) {
            if (r->is_restricted(asset, dt)) {
                return true;
            }
        }
        return false;
    }

    _UnionRestrictions operator|(_UnionRestrictions& other) {
        std::vector<Restrictions*> new_sub_restrictions = this->sub_restrictions;
        new_sub_restrictions.insert(new_sub_restrictions.end(), other.sub_restrictions.begin(), other.sub_restrictions.end());
        return _UnionRestrictions(new_sub_restrictions);
    }

private:
    std::vector<Restrictions*> sub_restrictions;
};

class NoRestrictions : public Restrictions {
public:
    bool is_restricted(std::string asset, std::string dt) override {
        return false;
    }
};

class StaticRestrictions : public Restrictions {
public:
    StaticRestrictions(std::set<std::string> restricted_list) : restricted_list(restricted_list) {}

    bool is_restricted(std::string asset, std::string dt) override {
        return restricted_list.find(asset) != restricted_list.end();
    }

private:
    std::set<std::string> restricted_list;
};

class HistoricalRestrictions : public Restrictions {
public:
    HistoricalRestrictions(std::vector<Restriction> restrictions) {
        for (const auto& restriction : restrictions) {
            restrictions_by_asset[restriction.asset].push_back(restriction);
        }
    }

    bool is_restricted(std::string asset, std::string dt) override {
        auto it = restrictions_by_asset.find(asset);
        if (it == restrictions_by_asset.end()) {
            return false;
        }

        RestrictionStates state = RestrictionStates::ALLOWED;
        for (const auto& restriction : it->second) {
            if (restriction.effective_date > dt) {
                break;
            }
            state = restriction.state;
        }
        return state == RestrictionStates::FROZEN;
    }

private:
    std::map<std::string, std::vector<Restriction>> restrictions_by_asset;
};