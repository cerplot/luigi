

#include <string>

class core : public Config {
public:
    bool local_scheduler;
    std::string scheduler_host;
    int scheduler_port;
    std::string scheduler_url;
    int lock_size;
    bool no_lock;
    std::string lock_pid_dir;
    bool take_lock;
    int workers;
    std::string logging_conf_file;
    std::string log_level;
    std::string module;
    bool parallel_scheduling;
    int parallel_scheduling_processes;
    bool assistant;
    bool help;
    bool help_all;

    core() {
        local_scheduler = BoolParameter(false, "Use an in-memory central scheduler. Useful for testing.", true);
        scheduler_host = Parameter("localhost", "Hostname of machine running remote scheduler",
                std::map<std::string, std::strinf> = {"section": "core", "name": "default-scheduler-host"});
        scheduler_port = IntParameter(8082,
                "Port of remote scheduler api process",
                config_path=dict(section='core', name='default-scheduler-port'));
        scheduler_url = Parameter("",
                "Full path to remote scheduler",
                config_path=dict(section='core', name='default-scheduler-url'),
        );
        lock_size = IntParameter(1, "Maximum number of workers running the same command");
        no_lock = BoolParameter(false, "Ignore if similar process is already running");
        lock_pid_dir = Parameter("/tmp/trun", "Directory to store the pid file");
        take_lock = BoolParameter(false,
                "Signal other processes to stop getting work if already running");
        workers = IntParameter(1,
                "Maximum number of parallel steps to run");
        logging_conf_file = Parameter("",
                "Configuration file for logging");
        log_level = ChoiceParameter("DEBUG",
                                    {'NOTSET', 'DEBUG', 'INFO', WARNING, ERROR, CRITICAL},
        description="Default log level to use when logging_conf_file is not set");
        module = Parameter("", 'Used for dynamic loading of modules', true);
        parallel_scheduling = BoolParameter(false,
                "Use multiprocessing to do scheduling in parallel.");
        parallel_scheduling_processes = IntParameter(0,
                "The number of processes to use for scheduling in parallel."
                " By default the number of available CPUs will be used");
        assistant = BoolParameter(false, "Run any step from the scheduler.");
        help = BoolParameter(false, "Show most common flags and all step-specific flags", true);
        help_all = BoolParameter(false, "Show all command line flags", true);
    }
};

class WorkerSchedulerFactory {
public:
    Scheduler create_local_scheduler() {
        return Scheduler(true, false);
    }

    RemoteScheduler create_remote_scheduler(std::string url) {
        return RemoteScheduler(url);
    }

    Worker create_worker(Scheduler scheduler, int worker_processes, bool assistant = false) {
        return Worker(scheduler, worker_processes, assistant);
    }
};


TrunRunResult _schedule_and_run(std::vector<Step> steps, WorkerSchedulerFactory* worker_scheduler_factory = nullptr, std::map<std::string, std::string> override_defaults = {}) {
    if (worker_scheduler_factory == nullptr) {
        worker_scheduler_factory = new WorkerSchedulerFactory();
    }
    EnvParams env_params = core(override_defaults);

    InterfaceLogging::setup(env_params);

    if (!env_params.no_lock && !lock::acquire_for(env_params.lock_pid_dir, env_params.lock_size)) {
        throw PidLockAlreadyTakenExit();
    }

    Scheduler* sch;
    if (env_params.local_scheduler) {
        sch = worker_scheduler_factory->create_local_scheduler();
    } else {
        std::string url = env_params.scheduler_url != "" ? env_params.scheduler_url : "http://" + env_params.scheduler_host + ":" + std::to_string(env_params.scheduler_port) + "/";
        sch = worker_scheduler_factory->create_remote_scheduler(url);
    }

    Worker* worker = worker_scheduler_factory->create_worker(sch, env_params.workers, env_params.assistant);

    bool success = true;
    Logger logger = Logger::getLogger("trun-interface");
    for (Step& t : steps) {
        success &= worker->add(t, env_params.parallel_scheduling, env_params.parallel_scheduling_processes);
    }
    logger.info("Done scheduling steps");
    success &= worker->run();
    TrunRunResult trun_run_result(worker, success);
    logger.info(trun_run_result.summary_text);
    if (dynamic_cast<Closable*>(sch) != nullptr) {
        dynamic_cast<Closable*>(sch)->close();
    }
    return trun_run_result;
}


class PidLockAlreadyTakenExit : public std::runtime_error {
public:
    PidLockAlreadyTakenExit() : std::runtime_error("The lock file is inaccessible") {}
};


RunResult run(std::vector<std::string> args, std::map<std::string, bool> kwargs) {
    // Please don't use. Instead use `trun` binary.
    // Run from cmdline using argparse.

    RunResult trun_run_result = _run(args, kwargs);
    if (kwargs["detailed_summary"]) {
        return trun_run_result;
    } else {
        return trun_run_result.scheduling_succeeded;
    }


bool _run(std::vector<std::string> cmdline_args = {}, std::string main_step_cls = "",
          std::string worker_scheduler_factory = "", bool use_dynamic_argparse = false,
          bool local_scheduler = false, bool detailed_summary = false) {
    if (use_dynamic_argparse) {
        std::cerr << "use_dynamic_argparse is deprecated, don't set it." << std::endl;
    }
    if (cmdline_args.empty()) {
        // Get command line arguments
    }
    if (!main_step_cls.empty()) {
        cmdline_args.insert(cmdline_args.begin(), main_step_cls);
    }
    if (local_scheduler) {
        cmdline_args.push_back("--local-scheduler");
    }
    CmdlineParser* cp = CmdlineParser::global_instance(cmdline_args);
    bool result = _schedule_and_run({cp->get_step_obj()}, worker_scheduler_factory);
    delete cp;
    return result;
}


bool build(std::vector<Step> steps, Scheduler (*worker_scheduler_factory)() = nullptr, bool detailed_summary = false, std::map<std::string, bool> env_params = {}) {
    if (env_params.find("no_lock") == env_params.end()) {
        env_params["no_lock"] = true;
    }

    TrunRunResult trun_run_result = _schedule_and_run(steps, worker_scheduler_factory, env_params);
    return detailed_summary ? trun_run_result : trun_run_result.scheduling_succeeded;
}
