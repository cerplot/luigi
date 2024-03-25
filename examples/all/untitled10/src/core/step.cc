#include "step.h"
#include <sstream>

namespace te {

    std::vector<Step *> Step::getRequirements() const {
        // The Steps that this Step depends on.
        // A Step will only run if all the Steps that it requires are completed.
        // If your Step does not require any other Steps, then you don't need to
        // override this method. Otherwise, a subclass can override this method
        // to return vector of Step instances

        // This is a default implementation that returns an empty vector.
        // Replace it with your actual implementation.
        return std::vector<Step *>();
    }

    void Step::run() {
        // The step run method, to be overridden in a subclass.

        // This is a default implementation that does nothing.
    }

    std::string Step::on_failure(const std::exception &e) {
        // Override for custom error handling.
        // This method gets called if an exception is raised in run().

        // Default behavior is to return a string representation of the stack trace.

        std::stringstream ss;
        ss << "Runtime error:\n" << e.what();
        return ss.str();
    }

    std::string Step::on_success() {
        // This method gets called when run() completes without raising any exceptions.
        // This is a default implementation that does nothing.
        return "";
    }

    std::vector<std::shared_ptr<Target>> Step::input() const {
        // Returns the targets of the Steps returned by requires()

        // This is a default implementation that returns the outputs of the required Steps.
        // Replace it with your actual implementation.
        return requires();
    }

    std::vector<Target> Step::output() const {
        // The output of the Step determines if the Step needs to be run--the step
        // is considered finished iff the outputs all exist. Subclasses should
        // override this method to return a single Target or a list of
        // Target instances.

        // Implementation note
        // If running multiple workers, the output must be a resource that is accessible
        // by all workers, such as a file or database. Otherwise, workers might compute
        // the same output since they don't see the work done by other workers.

        // This is a default implementation that returns an empty vector of targets.
        // Replace it with your actual implementation.
        return std::vector<Target>();
    }

    bool Step::complete() {
        // This method should return true if all the requirements of the step are complete
        // This is a placeholder implementation and should be replaced with the actual logic
        return true;
    }

    int Step::retry_count() {
        // Implement logic to override retry_count at step level
        return 0;
    }


    int Step::disable_hard_timeout() {
        // Implement logic to override disable_hard_timeout at step level
        return 0;
    }

    int Step::disable_window() {
        // Implement logic to override disable_window at step level
        return 0;
    }

    bool Step::batchable() {
        // Implement logic to check if instance can be run as part of a batch
        return false;
    }

    std::string Step::step_namespace() {
        // Implement logic to return the step namespace for the given class
        return "";
    }

    bool Step::use_cmdline_section() {
        // expose in cooamd line with/without section = className
        return true;
    }

}