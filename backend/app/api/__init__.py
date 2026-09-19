"""Step 0 creates the routers. Lanes fill the handlers for their own resources."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status


def not_implemented(owner: str, what: str) -> NoReturn:
    """Every route exists from step 0 so the other lanes can build against it.

    The body stays plain, because a person could see it. Which lane fills the route goes in a
    header instead, where the person building the client can read it and a user never does.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{what} is not built yet.",
        headers={"X-Binbooks-Owner": owner},
    )
