from typing import Annotated

from fastapi import FastAPI, Path, Query, HTTPException
from pydantic import BaseModel

data = {}

class HealthResponse(BaseModel):
    status: str

class Item(BaseModel):
    name: str
    number: int


app = FastAPI()

@app.get("/health/", response_model=HealthResponse)
async def get_health():
    return {"status": "ok"}

@app.get("/getitem/{item_id}", response_model=Item)
async def get_item(item_id: Annotated[str, Path(max_length=10)]):

    if item_id not in data:
        raise HTTPException(status_code=404, detail="Item not found")

    i = data[item_id]
    return {"name": i.name, "number": i.number}

@app.post("/postitem/{item_id}", response_model=Item)
async def post_item(item_id: Annotated[str, Path(max_length=10)],
                     other: Annotated[int, Query(ge=1144)]):
    i = Item(name=item_id, number=other)
    data[item_id] = i
    return {"name": item_id, "number": other}

@app.get("/all", response_model=dict[str, Item])
async def get_all():
    return data