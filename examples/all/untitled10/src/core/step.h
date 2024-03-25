#pragma once

#include <vector>
#include <string>
#include <memory>
#include <exception>

#include "target.h"

namespace te {

    class Step {
    public:
        virtual std::vector<Step*> getRequirements() const;
        virtual void run();
        virtual std::string on_failure(const std::exception &e);
        virtual std::string on_success();
        std::vector<std::shared_ptr<Target>> input() const;
        std::vector<Target> output() const;
        virtual bool complete();
        virtual int retry_count();
        virtual int disable_hard_timeout();
        virtual int disable_window();
        virtual bool batchable();
        virtual std::string step_namespace();
        virtual bool use_cmdline_section();
    };
}