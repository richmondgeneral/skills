from __future__ import annotations
import os
from typing import Dict, Optional, Tuple
from ..models import Channel, ChannelObservation

SquareIndex = Dict[str, Tuple[int, bool]]   # sku -> (price_cents, sold_out)


def observe_square(sku: str, index: SquareIndex) -> ChannelObservation:
    """Pure mapper: SKU + prebuilt index -> ChannelObservation."""
    if sku not in index:
        return ChannelObservation(channel=Channel.SQUARE, present=False)
    price_cents, sold_out = index[sku]
    return ChannelObservation(
        channel=Channel.SQUARE, present=True,
        price=round(price_cents / 100, 2), sold=bool(sold_out),
    )


def build_square_index(client=None, location_id: Optional[str] = None) -> SquareIndex:
    """Pull live catalog once into {sku: (price_cents, sold_out)}. Read-only.

    Verified against squareup==44.0.1.20260122:
      - ``Square(token=...)``                          (keyword-only ctor)
      - ``client.catalog.search_items(cursor=...)``    -> SearchCatalogItemsResponse
      - ``resp.items`` (CatalogObject union) / ``resp.cursor``
      - ``CatalogObject_Item.item_data`` -> CatalogItem.variations
      - variation ``v.item_variation_data`` -> CatalogItemVariation
        (.sku, .price_money.amount, .location_overrides)
      - ``ItemVariationLocationOverrides`` (.location_id, .sold_out)
    ``resp.items`` is a discriminated union, so ``item_data`` is read via getattr
    to skip any non-ITEM union member defensively.
    """
    from square.client import Square  # lazy import so unit tests need no SDK/network
    if client is None:
        token = os.environ.get("SQUARE_ACCESS_TOKEN") or os.environ.get("SQUARE_TOKEN")
        client = Square(token=token)
    location_id = location_id or os.environ.get("SQUARE_LOCATION_ID")

    index: SquareIndex = {}
    cursor = None
    while True:
        resp = client.catalog.search_items(cursor=cursor) if cursor \
            else client.catalog.search_items()
        for item in (resp.items or []):
            item_data = getattr(item, "item_data", None)
            if item_data is None:
                continue
            for v in (item_data.variations or []):
                vd = getattr(v, "item_variation_data", None)
                if vd is None:
                    continue
                sku = getattr(vd, "sku", None)
                if not sku:
                    continue
                price_cents = getattr(getattr(vd, "price_money", None), "amount", None)
                sold_out = False
                for ov in (getattr(vd, "location_overrides", None) or []):
                    if location_id is None or ov.location_id == location_id:
                        sold_out = bool(getattr(ov, "sold_out", False)) or sold_out
                index[sku] = (price_cents or 0, sold_out)
        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break
    return index
