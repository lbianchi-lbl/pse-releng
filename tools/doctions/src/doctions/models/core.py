from pathlib import Path

import oyaml as yaml
from pydantic import BaseModel, validator
from pydantic.dataclasses import dataclass
from urlpath import URL


class Model(BaseModel):

    @classmethod
    def from_yaml(cls, path):
        text = Path(path).read_text()
        data = yaml.safe_load(text)
        return cls(**data)

    @classmethod
    def _property_fields(cls):
        for name, val in vars(cls).items():
            if isinstance(val, property):
                yield name

    def property_data(self):
        return {
            name: getattr(self, name)
            for name in type(self)._property_fields()
        }

    def dict(self, **kwargs):
        return dict(
            super().dict(**kwargs),
            **self.property_data()
        )
