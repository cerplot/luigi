
"""
These are the unit tests for the BigQueryLoadAvro class.
"""

import unittest
import avro
import avro.schema
from trun.contrib.bigquery_avro import BigQueryLoadAvro


class BigQueryAvroTest(unittest.TestCase):

    def test_writer_schema_method_existence(self):
        schema_json = """
        {
            "namespace": "example.avro",
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "favorite_number",  "type": ["int", "null"]},
                {"name": "favorite_color", "type": ["string", "null"]}
            ]
        }
        """
        avro_schema = avro.schema.Parse(schema_json)
        reader = avro.io.DatumReader(avro_schema, avro_schema)
        actual_schema = BigQueryLoadAvro._get_writer_schema(reader)
        self.assertEqual(actual_schema, avro_schema,
                         "writer(s) avro_schema attribute not found")
        # otherwise AttributeError is thrown
