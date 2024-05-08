#include <vector>
#include <functional>

class EventRule {
public:
    virtual bool should_trigger(int dt) = 0; // Pure virtual function
};

class Event {
public:
    EventRule* rule;
    std::function<void(int, int, int)> callback;

    Event(EventRule* rule, std::function<void(int, int, int)> callback)
            : rule(rule), callback(callback) {}

    void handle_data(int context, int data, int dt) {
        if (rule->should_trigger(dt)) {
            callback(context, data);
        }
    }
};

class EventManager {
private:
    std::vector<Event> events;

public:
    void add_event(Event event) {
        events.push_back(event);
    }

    void handle_data(int context, int data, int dt) {
        for (auto& event : events) {
            event.handle_data(context, data, dt);
        }
    }
};