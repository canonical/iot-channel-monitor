""" This Module is for checking Monitor yaml data format"""
import os
import json
import yaml
import jsonschema
from jsonschema import validate


DATA_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "^.*$": {
            "type": "object",
            "properties": {
                "store": {"type": "string"},
                "arch": {
                    "type": "string",
                    "enum": ["arm64", "armhf", "x86"],
                },
                "channel": {"type": "string"},
                "name": {"type": "string"},
                "jira_id": {"type": "string"},
                "project": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "^.*$": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "assignee": {"type": "string"},
                                "job": {"type": "string"},
                            },
                            "required": ["name", "assginee", "job"],
                        }
                    },
                },
            },
            "required": [
                "store",
                "arch",
                "channel",
                "name",
                "jira_id",
                "projects",
            ],
        }
    },
}


class DataParser:
    """
    This parser is for reading the channal monitor job and
    ensure the data format is expected
    """

    def __init__(self, file):
        """Initial

        Args:
            file (str): the filename of the channal monitor job

        Raises:
            SystemExit: If file extension is not JSON or YAML
        """
        _, ext = os.path.splitext(file)
        with open(file, "r", encoding="utf-8") as fp:
            if ext == ".json":
                self._data = json.load(fp)
            elif ext in [".yaml", ".yml"]:
                self._data = yaml.load(fp, Loader=yaml.FullLoader)
            else:
                raise SystemExit(
                    "The tplan should has extend name in json or yaml."
                )

        self.validate_data()

    @property
    def data(self):
        """
        the data property of this module

        Returns:
            dict: the data about channel monitor jobs
        """
        return self._data

    def validate_data(self):
        """Validate data by JSON schema

        Raises:
            ValueError: If data format is invalid
        """
        try:
            validate(instance=self._data, schema=DATA_SCHEMA)
            print("the JSON data is valid")
        except jsonschema.exceptions.ValidationError as err:
            raise ValueError(f"the JSON data is invalid, err {err}") from err
