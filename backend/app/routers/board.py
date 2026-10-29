"""Board analysis: many images in, distinct aesthetics plus matching catalog items out."""

from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.deps import FocusFilter, get_catalog, get_embedder, get_focus
from app.models import Aesthetic, BoardAnalysis, StyleTag
from app.routers.search import _scored
from app.services.aesthetics import bank_for, style_tags
from app.services.board import choose_clusters
from app.services.catalog import Catalog
from app.services.embedder import Embedder
from app.services.upload_pipeline import process_upload
from app.uploads import read_image

router = APIRouter(prefix="/board", tags=["board"])

MIN_IMAGES, MAX_IMAGES = 3, 20


@router.post("/analyze", response_model=BoardAnalysis)
async def analyze_board(
    images: Annotated[list[UploadFile], File(description="3–20 outfit images (JPEG, PNG, WebP; 10 MB each)")],
    catalog: Annotated[Catalog, Depends(get_catalog)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    focus: Annotated[FocusFilter, Depends(get_focus)],
    k: Annotated[int, Query(ge=1, le=50, description="catalog items per aesthetic")] = 12,
) -> BoardAnalysis:
    """Embed the board, split it into 1–3 aesthetics by silhouette score, and match each to the catalog."""
    if not MIN_IMAGES <= len(images) <= MAX_IMAGES:
        raise HTTPException(status_code=422, detail=f"Upload between {MIN_IMAGES} and {MAX_IMAGES} images.")
    # Each upload: provenance read from the original bytes, then GPS stripped, before any processing.
    decoded = [process_upload((await read_image(u))[0], u.content_type or "image/jpeg").image for u in images]
    vectors = embedder.embed_images(decoded)

    clustering = choose_clusters(vectors)
    bank = bank_for(embedder)
    aesthetics = []
    for j, centroid in enumerate(clustering.centroids):
        hits = catalog.search(centroid, k=k, exclude_ids=focus.excluded)
        aesthetics.append(
            Aesthetic(
                index=j,
                image_indices=[int(i) for i in np.flatnonzero(clustering.labels == j)],
                style_tags=[StyleTag(word=w, score=round(s, 4)) for w, s in style_tags(centroid, bank)],
                results=_scored(hits),
                centroid=[round(float(v), 6) for v in centroid],
            )
        )
    return BoardAnalysis(
        k=clustering.k,
        silhouette=None if clustering.silhouette is None else round(clustering.silhouette, 4),
        silhouette_by_k={kk: round(s, 4) for kk, s in clustering.candidates.items()},
        aesthetics=aesthetics,
    )
