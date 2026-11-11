"""JSON Schema validation tests for CognitiveOS product-specs."""

import json
import glob
import unittest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class TestJSONSchemas(unittest.TestCase):
    """Test that all JSON schemas in schemas/ are valid Draft 7 schemas."""

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_all_schemas_are_valid_draft7(self):
        """Every JSON schema file must be a valid JSON Schema Draft 7."""
        schema_files = glob.glob("schemas/*.json")
        self.assertGreater(len(schema_files), 0, "No schema files found")

        for schema_file in schema_files:
            with self.subTest(schema=schema_file):
                with open(schema_file) as f:
                    schema = json.load(f)
                jsonschema.Draft7Validator.check_schema(schema)


class TestCognitiveSchema(unittest.TestCase):
    """Test the cognitive.json manifest schema specifically."""

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_cognitive_schema_has_required_fields(self):
        """cognitive.schema.json must define required manifest fields."""
        with open("schemas/cognitive.schema.json") as f:
            schema = json.load(f)
        self.assertIn("properties", schema)
        self.assertIn("required", schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema package not installed")
    def test_cognitive_schema_validates_valid_manifest(self):
        """cognitive.schema.json must accept a valid manifest."""
        with open("schemas/cognitive.schema.json") as f:
            schema = json.load(f)
        validator = jsonschema.Draft7Validator(schema)
        valid_manifest = {
            "cognitiveos": "1.0.0",
            "name": "test-patch",
            "version": "1.0.0",
        }
        errors = list(validator.iter_errors(valid_manifest))
        self.assertEqual(len(errors), 0, f"Valid manifest should pass: {errors}")


if __name__ == "__main__":
    unittest.main()
