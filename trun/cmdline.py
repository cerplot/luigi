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
    parser = argparse.ArgumentParser(description=u'Central trun server')
    parser.add_argument(u'--background', help=u'Run in background mode', action='store_true')
    parser.add_argument(u'--pidfile', help=u'Write pidfile')
    parser.add_argument(u'--logdir', help=u'log directory')
    parser.add_argument(u'--state-path', help=u'Pickled state file')
    parser.add_argument(u'--address', help=u'Listening interface')
    parser.add_argument(u'--unix-socket', help=u'Unix socket path')
    parser.add_argument(u'--port', default=8082, help=u'Listening port')

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
