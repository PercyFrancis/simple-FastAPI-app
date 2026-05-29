from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class Item(BaseModel):
    name: str
    number: int