from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from simple_fastapi_app.item.models import Item
from simple_fastapi_app.item import service


router = APIRouter()


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: Annotated[str, Path(max_length=10)]):
    item = service.get_item(item_id=item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return item

# UPdate + inSERT
@router.put("/{item_id}", response_model=Item)
def upsert_item(
    item_id: Annotated[str, Path(max_length=10)],
    other: Annotated[int, Query(ge=1144)],
):
    return service.upsert_item(item_id=item_id, number=other)


@router.get("", response_model=dict[str, Item])
def get_all_items():
    return service.get_all_items()