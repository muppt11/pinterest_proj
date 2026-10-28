"""Complete the look: complementary items for an anchor item, optionally tuned to a board aesthetic."""

from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_catalog
from app.models import CompleteLook, CompleteLookRequest, LookGroupOut
from app.routers.search import _scored
from app.services.catalog import Catalog
from app.services.complete_look import complete_look

router = APIRouter(tags=["complete the look"])


@router.post("/complete-look", response_model=CompleteLook)
def complete_look_endpoint(body: CompleteLookRequest, catalog: Annotated[Catalog, Depends(get_catalog)]) -> CompleteLook:
    """Bottoms/shoes/outerwear/etc. that go with an item, ranked by shared style (and the board's taste if given)."""
    centroid = None
    if body.centroid is not None:
        centroid = np.asarray(body.centroid, dtype=np.float32)
        if centroid.shape != (catalog.index.d,) or not np.isfinite(centroid).all() or np.linalg.norm(centroid) == 0:
            raise HTTPException(status_code=422, detail=f"centroid must be a non-zero vector of length {catalog.index.d}.")
    try:
        group, groups = complete_look(catalog, body.item_id, body.per_group, centroid, body.item_weight)
    except KeyError:
        raise HTTPException(status_code=404, detail="Item not found.") from None
    return CompleteLook(
        item_id=body.item_id,
        anchor_group=group,
        used_board=centroid is not None,
        groups=[LookGroupOut(group=g.group, results=_scored(g.hits)) for g in groups],
    )
