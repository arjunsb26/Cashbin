"""Step 0 creates the routers. Lanes fill the handlers for their own resources."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status


def not_implemented(owner: str, what: str) -> NoReturn:
    """Every route exists from step 0 so the frontend can be built against it.

    The body names the lane that will fill it, so a 501 in the network tab is self explaining.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{what} is not built yet. {owner} owns it.",
    )
