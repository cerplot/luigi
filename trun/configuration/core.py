import logging
import os
import warnings

from .cfg_parser import TrunConfigParser
from .toml_parser import TrunTomlParser


logger = logging.getLogger('trun-interface')


PARSERS = {
    'cfg': TrunConfigParser,
    'conf': TrunConfigParser,
    'ini': TrunConfigParser,
    'toml': TrunTomlParser,
}

DEFAULT_PARSER = 'toml'


def _get_default_parser():
    parser = os.environ.get('TRUN_CONFIG_PARSER', DEFAULT_PARSER)
    if parser not in PARSERS:
        warnings.warn("Invalid parser: {parser}".format(parser=DEFAULT_PARSER))
        parser = DEFAULT_PARSER
    return parser


def _check_parser(parser_class, parser):
    if not parser_class.enabled:
        msg = (
            "Parser not installed yet. "
            "Please, install trun with required parser:\n"
            "pip install trun[{parser}]"
        )
        raise ImportError(msg.format(parser=parser))


def get_config(parser=None):
    """Get configs singleton for parser
    """
    if parser is None:
        parser = _get_default_parser()
    parser_class = PARSERS[parser]
    _check_parser(parser_class, parser)
    return parser_class.instance()


def add_config_path(path):
    """Select config parser by file extension and add path into parser.
    """
    if not os.path.isfile(path):
        warnings.warn("Config file does not exist: {path}".format(path=path))
        return False

    # select parser by file extension
    default_parser = _get_default_parser()
    _base, ext = os.path.splitext(path)
    if ext and ext[1:] in PARSERS:
        parser = ext[1:]
    else:
        parser = default_parser
    parser_class = PARSERS[parser]

    _check_parser(parser_class, parser)
    if parser != default_parser:
        msg = (
            "Config for {added} parser added, but used {used} parser. "
            "Set up right parser via env var: "
            "export TRUN_CONFIG_PARSER={added}"
        )
        warnings.warn(msg.format(added=parser, used=default_parser))

    # add config path to parser
    parser_class.add_config_path(path)
    return True


if 'TRUN_CONFIG_PATH' in os.environ:
    add_config_path(os.environ['TRUN_CONFIG_PATH'])
