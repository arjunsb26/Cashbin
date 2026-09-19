"""The Embedder interface from PLAN.md section 9. Step 0 owns it, lane C writes the embedders.

An embedder turns a crop into an L2-normalised vector. The baseline and any later encoder
satisfy the same Protocol, so memory kNN never learns which one it is talking to.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import cv2
import numpy as np
from numpy.typing import NDArray


@runtime_checkable
class Embedder(Protocol):
    """Embed one image. The result is L2-normalised, so cosine distance is 1 minus the dot."""

    name: str
    dim: int

    def embed(self, image: bytes) -> NDArray[np.float32]: ...


HIST_BINS = 8
THUMB_SIDE = 16
BASELINE_DIM = HIST_BINS**3 + THUMB_SIDE**2

_EPS = 1e-8


def _unit(vector: NDArray[np.float32]) -> NDArray[np.float32]:
    """L2 normalise, and leave an all-zero block alone rather than dividing by nothing."""
    norm = float(np.linalg.norm(vector))
    if norm < _EPS:
        return vector
    return (vector / norm).astype(np.float32)


def decode_jpeg(image: bytes) -> NDArray[np.uint8]:
    """JPEG bytes to a BGR array. A frame that will not decode is an error, not an empty vector."""
    if not image:
        raise ValueError("image is empty")
    buffer = np.frombuffer(image, dtype=np.uint8)
    decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError("image did not decode")
    return decoded.astype(np.uint8)


class BaselineEmbedder:
    """PLAN.md section 9: an HSV histogram beside a small grayscale thumbnail.

    Two blocks, each L2 normalised before they are joined, so neither one drowns the other
    whatever the picture looks like. The thumbnail has its own mean removed first, because
    raw brightness is the same for every crop under the same lamp and carries no signal;
    what is left is the shape. The whole vector is L2 normalised, so cosine distance between
    two crops is one minus their dot product.

    Deterministic: the same bytes always give the same vector, on any machine.
    """

    name = "baseline-hsv-thumb"
    dim = BASELINE_DIM

    def embed(self, image: bytes) -> NDArray[np.float32]:
        bgr = decode_jpeg(image)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist(
            [hsv],
            [0, 1, 2],
            None,
            [HIST_BINS, HIST_BINS, HIST_BINS],
            [0, 180, 0, 256, 0, 256],
        )
        colour = _unit(hist.flatten().astype(np.float32))

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        thumb = cv2.resize(gray, (THUMB_SIDE, THUMB_SIDE), interpolation=cv2.INTER_AREA)
        flat = thumb.flatten().astype(np.float32) / 255.0
        shape = _unit(flat - float(flat.mean()))

        return _unit(np.concatenate([colour, shape]).astype(np.float32))


def to_bytes(vector: NDArray[np.float32]) -> bytes:
    """How an embedding is stored in the exemplar table: little-endian float32, no header."""
    return np.ascontiguousarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> NDArray[np.float32]:
    """Read an embedding back out of the exemplar table."""
    return np.frombuffer(blob, dtype=np.float32).astype(np.float32)


def get_embedder() -> Embedder:
    """The embedder the pipeline uses. One setting swaps it once a second one exists."""
    return BaselineEmbedder()
