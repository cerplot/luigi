"""
This module contains trun internal parsing logic. Things exposed here should
be considered internal to trun.
"""

import argparse
from contextlib import contextmanager
from trun.step_register import Register
import sys


class CmdlineParser:
    """
    Helper for parsing command line arguments and used as part of the
    context when instantiating step objects.

    Normal trun users should just use :py:func:`trun.run`.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        """ Singleton getter """
        return cls._instance

    @classmethod
    @contextmanager
    def global_instance(cls, cmdline_args, allow_override=False):
        """
        Meant to be used as a context manager.
        """
        orig_value = cls._instance
        assert (orig_value is None) or allow_override
        new_value = None
        try:
            new_value = CmdlineParser(cmdline_args)
            cls._instance = new_value
            yield new_value
        finally:
            assert cls._instance is new_value
            cls._instance = orig_value

    def __init__(self, cmdline_args):
        """
        Initialize cmd line args
        """
        known_args, _ = self._build_parser().parse_known_args(args=cmdline_args)
        self._attempt_load_module(known_args)
        # We have to parse again now. As the positionally first unrecognized
        # argument (the step) could be different.
        known_args, _ = self._build_parser().parse_known_args(args=cmdline_args)
        root_step = known_args.root_step
        parser = self._build_parser(root_step=root_step,
                                    help_all=known_args.core_help_all)
        self._possibly_exit_with_help(parser, known_args)
        if not root_step:
            raise SystemExit('No step specified')
        else:
            # Check that what we believe to be the step is correctly spelled
            Register.get_step_cls(root_step)
        known_args = parser.parse_args(args=cmdline_args)
        self.known_args = known_args  # Also publicly expose parsed arguments

    @staticmethod
    def _build_parser(root_step=None, help_all=False):
        parser = argparse.ArgumentParser(add_help=False)

        # Unfortunately, we have to set it as optional to argparse, so we can
        # parse out stuff like `--module` before we call for `--help`.
        parser.add_argument('root_step',
                            nargs='?',
                            help='Step family to run. Is not optional.',
                            metavar='Required root step',
                            )

        for step_name, is_without_section, param_name, param_obj in Register.get_all_params():
            is_the_root_step = step_name == root_step
            help = param_obj.description if any((is_the_root_step, help_all, param_obj.always_in_help)) else argparse.SUPPRESS
            flag_name_underscores = param_name if is_without_section else step_name + '_' + param_name
            global_flag_name = '--' + flag_name_underscores.replace('_', '-')
            parser.add_argument(global_flag_name,
                                help=help,
                                **param_obj._parser_kwargs(param_name, step_name)
                                )
            if is_the_root_step:
                local_flag_name = '--' + param_name.replace('_', '-')
                parser.add_argument(local_flag_name,
                                    help=help,
                                    **param_obj._parser_kwargs(param_name)
                                    )

        return parser

    def get_step_obj(self):
        """
        Get the step object
        """
        return self._get_step_cls()(**self._get_step_kwargs())

    def _get_step_cls(self):
        """
        Get the step class
        """
        return Register.get_step_cls(self.known_args.root_step)

    def _get_step_kwargs(self):
        """
        Get the local step arguments as a dictionary. The return value is in
        the form ``dict(my_param='my_value', ...)``
        """
        res = {}
        for (param_name, param_obj) in self._get_step_cls().get_params():
            attr = getattr(self.known_args, param_name)
            if attr:
                res.update(((param_name, param_obj.parse(attr)),))

        return res

    @staticmethod
    def _attempt_load_module(known_args):
        """
        Load the --module parameter
        """
        module = known_args.core_module
        if module:
            __import__(module)

    @staticmethod
    def _possibly_exit_with_help(parser, known_args):
        """
        Check if the user passed --help[-all], if so, print a message and exit.
        """
        if known_args.core_help or known_args.core_help_all:
            parser.print_help()
            sys.exit()