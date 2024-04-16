class CancelPolicy {
public:
    virtual bool should_cancel(int event) = 0;  // Pure virtual function
};

class EODCancel : public CancelPolicy {
public:
    EODCancel(bool warn_on_cancel = true) : warn_on_cancel(warn_on_cancel) {}

    bool should_cancel(int event) override {
        return event == SESSION_END;
    }

private:
    bool warn_on_cancel;
};

class NeverCancel : public CancelPolicy {
public:
    NeverCancel() : warn_on_cancel(false) {}

    bool should_cancel(int event) override {
        return false;
    }

private:
    bool warn_on_cancel;
};