
from trun.configuration import TrunTomlParser, get_config, add_config_path


from helpers import TrunTestCase


class TomlConfigParserTest(TrunTestCase):
    @classmethod
    def setUpClass(cls):
        add_config_path('test/testconfig/trun.toml')
        add_config_path('test/testconfig/trun_local.toml')

    def setUp(self):
        TrunTomlParser._instance = None
        super(TomlConfigParserTest, self).setUp()

    def test_get_config(self):
        config = get_config('toml')
        self.assertIsInstance(config, TrunTomlParser)

    def test_file_reading(self):
        config = get_config('toml')
        self.assertIn('hdfs', config.data)

    def test_get(self):
        config = get_config('toml')

        # test getting
        self.assertEqual(config.get('hdfs', 'client'), 'hadoopcli')
        self.assertEqual(config.get('hdfs', 'client', 'test'), 'hadoopcli')

        # test default
        self.assertEqual(config.get('hdfs', 'test', 'check'), 'check')
        with self.assertRaises(KeyError):
            config.get('hdfs', 'test')

        # test override
        self.assertEqual(config.get('hdfs', 'namenode_host'), 'localhost')
        # test non-string values
        self.assertEqual(config.get('hdfs', 'namenode_port'), 50030)

    def test_set(self):
        config = get_config('toml')

        self.assertEqual(config.get('hdfs', 'client'), 'hadoopcli')
        config.set('hdfs', 'client', 'test')
        self.assertEqual(config.get('hdfs', 'client'), 'test')
        config.set('hdfs', 'check', 'test me')
        self.assertEqual(config.get('hdfs', 'check'), 'test me')

    def test_has_option(self):
        config = get_config('toml')
        self.assertTrue(config.has_option('hdfs', 'client'))
        self.assertFalse(config.has_option('hdfs', 'nope'))
        self.assertFalse(config.has_option('nope', 'client'))


class HelpersTest(TrunTestCase):
    def test_add_without_install(self):
        enabled = TrunTomlParser.enabled
        TrunTomlParser.enabled = False
        with self.assertRaises(ImportError):
            add_config_path('test/testconfig/trun.toml')
        TrunTomlParser.enabled = enabled

    def test_get_without_install(self):
        enabled = TrunTomlParser.enabled
        TrunTomlParser.enabled = False
        with self.assertRaises(ImportError):
            get_config('toml')
        TrunTomlParser.enabled = enabled
