"""Contract tests for StorageManager, run against the in-memory implementation.
The same assertions define the behaviour any concrete StorageManager must honour."""

from datetime import timedelta

import pytest

from agentic_webapp.storage.base import AssetNotFoundError


def test_put_get_roundtrip(storage, run):
    run(storage.put("k1", b"hello", content_type="text/plain"))
    assert run(storage.get("k1")) == b"hello"
    assert run(storage.exists("k1")) is True


def test_get_missing_raises(storage, run):
    with pytest.raises(AssetNotFoundError):
        run(storage.get("nope"))


def test_list_prefix_is_filtered_and_sorted(storage, run):
    run(storage.put("a/1", b"x"))
    run(storage.put("a/2", b"y"))
    run(storage.put("b/1", b"z"))
    assert [a.key for a in run(storage.list("a/"))] == ["a/1", "a/2"]


def test_delete_is_idempotent(storage, run):
    run(storage.put("k", b"x"))
    run(storage.delete("k"))
    assert run(storage.exists("k")) is False
    run(storage.delete("k"))  # no-op, must not raise


def test_download_to_temp_writes_a_real_file(storage, run):
    run(storage.put("img.png", b"PNGDATA", content_type="image/png"))
    path = run(storage.download_to_temp("img.png"))
    assert path.exists()
    assert path.read_bytes() == b"PNGDATA"


def test_download_to_temp_missing_raises(storage, run):
    with pytest.raises(AssetNotFoundError):
        run(storage.download_to_temp("missing"))


def test_signed_url_returns_a_fetchable_reference(storage, run):
    run(storage.put("assets/x.png", b"d"))
    url = run(storage.signed_url("assets/x.png", expires_in=timedelta(seconds=60)))
    assert "assets/x.png" in url
