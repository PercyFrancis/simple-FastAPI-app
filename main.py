from typing import Annotated

from fastapi import FastAPI, Path, Query
from pydantic import BaseModel

data = {}

class Item(BaseModel):
    name: str
    number: int

app = FastAPI()

@app.get("/health/")
async def get_health():
    return {"status": "ok"}

@app.get("/getitem/{item_id}")
async def get_item(item_id: Annotated[str, Path(max_length=10)]):
    i = data[item_id]
    return {"item_id": i.name, "number": i.number}

@app.post("/postitem/{item_id}")
async def post_item(item_id: Annotated[str, Path(max_length=10)],
                     other: Annotated[int, Query(ge=1144)]):
    i = Item(name=item_id, number=other)
    data[item_id] = i
    return {"item_id": item_id, "other": other}

@app.get("/all")
async def get_all():
    return data