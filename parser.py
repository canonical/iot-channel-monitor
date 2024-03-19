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
                                "job": {"type": "string"}
                            },
                            "required": [
                                "name",
                                "assginee",
                                "job"
                            ],
                        }
                    }
                }
            },
            "required": [
                "arch",
                "channel",
                "name",
                "jira_id",
                "projects"
            ],
        }
    }
}


class DataParser:
    def __init__(self, file):
        _, ext = os.path.splitext(file)
        with open(file, "r") as fp:
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
        return self._data

    def validate_data(self):
        try:
            validate(instance=self._data, schema=DATA_SCHEMA)
            print("the JSON data is valid")
        except jsonschema.exceptions.ValidationError as err:
            raise ValueError("the JSON data is invalid, err {}".format(err))
