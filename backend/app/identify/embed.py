"""The Embedder interface from PLAN.md section 9. Step 0 owns it, lane C writes the embedders.

An embedder turns a crop into an L2-normalised vector. The baseline and any later encoder
satisfy the same Protocol, so memory kNN never learns which one it is talking to.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class Embedder(Protocol):
    """Embed one image. The result is L2-normalised, so cosine distance is 1 minus the dot."""

    name: str
    dim: int

    def embed(self, image: bytes) -> NDArray[np.float32]: ...
