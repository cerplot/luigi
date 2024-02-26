
import os.path
from configparser import ConfigParser

try:
    import toml
except ImportError:
    toml = False

from .base_parser import BaseParser
from ..freezing import recursively_freeze


class TrunTomlParser(BaseParser, ConfigParser):
    NO_DEFAULT = object()
    enabled = bool(toml)
    data = dict()
    _instance = None
    _config_paths = [
        '/etc/trun/trun.toml',
        'trun.toml',
    ]

    @staticmethod
    def _update_data(data, new_data):
        if not new_data:
            return data
        if not data:
            return new_data
        for section, content in new_data.items():
            if section not in data:
                data[section] = dict()
            data[section].update(content)
        return data

    def read(self, config_paths):
        self.data = dict()
        for path in config_paths:
            if os.path.isfile(path):
                self.data = self._update_data(self.data, toml.load(path))

        # freeze dict params
        for section, content in self.data.items():
            for key, value in content.items():
                if isinstance(value, dict):
                    self.data[section][key] = recursively_freeze(value)

        return self.data

    def get(self, section, option, default=NO_DEFAULT, **kwargs):
        try:
            return self.data[section][option]
        except KeyError:
            if default is self.NO_DEFAULT:
                raise
            return default

    def getboolean(self, section, option, default=NO_DEFAULT):
        return self.get(section, option, default)

    def getint(self, section, option, default=NO_DEFAULT):
        return self.get(section, option, default)

    def getfloat(self, section, option, default=NO_DEFAULT):
        return self.get(section, option, default)

    def getintdict(self, section):
        return self.data.get(section, {})

    def set(self, section, option, value=None):
        if section not in self.data:
            self.data[section] = {}
        self.data[section][option] = value

    def has_option(self, section, option):
        return section in self.data and option in self.data[section]

    def __getitem__(self, name):
        return self.data[name]
