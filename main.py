from typing import Annotated

from fastapi import FastAPI, Path, Query, HTTPException
from pydantic import BaseModel

import os
import psycopg
from psycopg.rows import dict_row

# data = {}

DATABASE_URL = "postgresql://percy:1144simplefast@localhost:5433/fastapi_app_db"

def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

class HealthResponse(BaseModel):
    status: str

class Item(BaseModel):
    name: str
    number: int


app = FastAPI()

@app.get("/health/", response_model=HealthResponse)
async def get_health():
    return {"status": "ok"}

@app.get("/getitem/{item_id}", response_model=Item, responses={404: {"description": "Item not found"}})
async def get_item(item_id: Annotated[str, Path(max_length=10)]):

    # if item_id not in data:
    #     raise HTTPException(status_code=404, detail="Item not found")

    # i = data[item_id]
    # return {"name": i.name, "number": i.number}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, number FROM items WHERE id = %s", 
                (item_id,) # prevents against SQL injection
            )
            row = cur.fetchone() # get one row
    if row is None:
         raise HTTPException(status_code=404, detail="Item not found")
    return row
        

@app.post("/postitem/{item_id}", response_model=Item)
async def post_item(item_id: Annotated[str, Path(max_length=10)],
                     other: Annotated[int, Query(ge=1144)]):
    # i = Item(name=item_id, number=other)
    # data[item_id] = i
    # return {"name": item_id, "number": other}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO items (id, name, number) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (id)
                DO UPDATE SET number = EXCLUDED.number
                """,
                (item_id, item_id, other)
            )
    
    return {"name": item_id, "number": other}

@app.get("/all", response_model=dict[str, Item])
async def get_all():

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, number FROM items"
            )
            rows = cur.fetchall()
    return {
        row["id"]: {
            "name": row["name"],
            "number": row["number"]
        }
        for row in rows
    }