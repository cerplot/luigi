import argparse
import sys

from trun.retcodes import run_with_retcodes
from trun.setup_logging import DaemonLogging


def trun_run(argv=sys.argv[1:]):
    run_with_retcodes(argv)


def trund(argv=sys.argv[1:]):
    import trun.server
    import trun.process
    import trun.configuration
    parser = argparse.ArgumentParser(description='Central trun server')
    parser.add_argument('--background', help='Run in background mode', action='store_true')
    parser.add_argument('--pidfile', help='Write pidfile')
    parser.add_argument('--logdir', help='log directory')
    parser.add_argument('--state-path', help='Pickled state file')
    parser.add_argument('--address', help='Listening interface')
    parser.add_argument('--unix-socket', help='Unix socket path')
    parser.add_argument('--port', default=8082, help='Listening port')

    opts = parser.parse_args(argv)

    if opts.state_path:
        config = trun.configuration.get_config()
        config.set('scheduler', 'state_path', opts.state_path)

    DaemonLogging.setup(opts)
    if opts.background:
        trun.process.daemonize(trun.server.run, api_port=opts.port,
                                address=opts.address, pidfile=opts.pidfile,
                                logdir=opts.logdir, unix_socket=opts.unix_socket)
    else:
        trun.server.run(api_port=opts.port, address=opts.address, unix_socket=opts.unix_socket)
