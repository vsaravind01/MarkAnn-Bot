from pydantic import BaseModel


class OutputSchema(BaseModel):
    seq_id: str
    symbol: str


class Poller:
    @classmethod
    def default_config(cls) -> dict:
        return {"base_interval": 7.0}
