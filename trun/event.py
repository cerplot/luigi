
""" Definitions needed for events. See :ref:`Events` for info on how to use it."""


class Event:
    # TODO nice descriptive subclasses of Event instead of strings? pass their instances to the callback instead of an undocumented arg list?
    DEPENDENCY_DISCOVERED = "event.core.dependency.discovered"  # triggered for every (step, upstream step) pair discovered in a jobflow
    DEPENDENCY_MISSING = "event.core.dependency.missing"
    DEPENDENCY_PRESENT = "event.core.dependency.present"
    BROKEN_STEP = "event.core.step.broken"
    START = "event.core.start"
    #: This event can be fired by the step itself while running. The purpose is
    #: for the step to report progress, metadata or any generic info so that
    #: event handler listening for this can keep track of the progress of running step.
    PROGRESS = "event.core.progress"
    FAILURE = "event.core.failure"
    SUCCESS = "event.core.success"
    PROCESSING_TIME = "event.core.processing_time"
    TIMEOUT = "event.core.timeout"  # triggered if a step times out
    PROCESS_FAILURE = "event.core.process_failure"  # triggered if the process a step is running in dies unexpectedly
