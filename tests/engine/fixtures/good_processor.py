from pydantic import BaseModel


class InputSchema(BaseModel):
    seq_id: str


class Processor:
    @classmethod
    def default_config(cls) -> dict:
        return {"pool_size": 4}
