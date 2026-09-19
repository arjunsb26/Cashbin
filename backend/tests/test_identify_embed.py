"""The baseline embedder: deterministic, normalised, and able to tell two crops apart."""

from __future__ import annotations

import numpy as np
import pytest

from app.identify.embed import (
    BASELINE_DIM,
    BaselineEmbedder,
    Embedder,
    from_bytes,
    get_embedder,
    to_bytes,
)
from tests.test_identify_support import make_jpeg


def test_it_satisfies_the_protocol() -> None:
    assert isinstance(BaselineEmbedder(), Embedder)
    assert get_embedder().dim == BASELINE_DIM == 768


def test_the_vector_has_the_stated_width_and_is_normalised() -> None:
    vector = BaselineEmbedder().embed(make_jpeg(patch=(255, 255, 255)))
    assert vector.shape == (768,)
    assert vector.dtype == np.float32
    assert float(np.linalg.norm(vector)) == pytest.approx(1.0, abs=1e-5)


def test_the_same_bytes_always_give_the_same_vector() -> None:
    crop = make_jpeg(patch=(10, 200, 10))
    first = BaselineEmbedder().embed(crop)
    second = BaselineEmbedder().embed(crop)
    assert np.array_equal(first, second)


def test_two_different_items_sit_far_apart() -> None:
    embedder = BaselineEmbedder()
    bagel = embedder.embed(make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200)))
    keyboard = embedder.embed(make_jpeg(colour=(30, 30, 30), patch=(200, 200, 200)))
    assert 1.0 - float(bagel @ keyboard) > 0.35


def test_the_same_item_photographed_twice_sits_close() -> None:
    embedder = BaselineEmbedder()
    first = embedder.embed(make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200)))
    second = embedder.embed(make_jpeg(colour=(62, 178, 228), patch=(42, 122, 198)))
    assert 1.0 - float(first @ second) < 0.35


def test_bytes_round_trip_through_the_exemplar_column() -> None:
    vector = BaselineEmbedder().embed(make_jpeg())
    assert np.allclose(from_bytes(to_bytes(vector)), vector)


def test_an_unreadable_crop_is_an_error_not_an_empty_vector() -> None:
    with pytest.raises(ValueError, match="did not decode"):
        BaselineEmbedder().embed(b"this is not a jpeg")
    with pytest.raises(ValueError, match="empty"):
        BaselineEmbedder().embed(b"")
