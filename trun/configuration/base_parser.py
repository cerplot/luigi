
import logging


# IMPORTANT: don't inherit from `object`!
# ConfigParser have some troubles in this case.
# More info: https://stackoverflow.com/a/19323238
class BaseParser:
    @classmethod
    def instance(cls, *args, **kwargs):
        """ Singleton getter """
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
            loaded = cls._instance.reload()
            logging.getLogger('trun-interface').info('Loaded %r', loaded)

        return cls._instance

    @classmethod
    def add_config_path(cls, path):
        cls._config_paths.append(path)
        cls.reload()

    @classmethod
    def reload(cls):
        return cls.instance().read(cls._config_paths)
