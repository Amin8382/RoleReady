from copy import deepcopy
from io import BytesIO
import json

import pytest

from roleready_ai.acquisition import fetch, load_registry, verify_snapshots


def test_existing_snapshot_is_verified_without_network(source_fixture):
    f = source_fixture
    f.add([f.row()])
    def forbidden(*args, **kwargs):
        raise AssertionError("No network is permitted in this test")
    assert fetch(f.registry, f.raw, opener=forbidden)["verified_existing_files"] == 1


def test_download_requires_pinned_size_and_hash_and_never_overwrites(source_fixture):
    f = source_fixture
    source = f.add([f.row()])
    data = (f.raw / source["source_id"] / source["revision"] / "questions.jsonl").read_bytes()
    calls = []
    def good(url, timeout):
        calls.append(url)
        return BytesIO(data)
    destination = f.tmp / "fresh"
    assert fetch(f.registry, destination, opener=good)["downloaded_files"] == 1
    assert "/resolve/" + "a" * 40 + "/" in calls[0]
    target = destination / source["source_id"] / source["revision"] / "questions.jsonl"
    target.write_bytes(b"unique work")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        fetch(f.registry, destination, opener=good)
    assert target.read_bytes() == b"unique work"


def test_corrupt_download_does_not_create_snapshot(source_fixture):
    f = source_fixture
    f.add([f.row()])
    with pytest.raises(ValueError, match="checksum"):
        fetch(f.registry, f.tmp / "fresh", opener=lambda *a, **k: BytesIO(b"bad"))
    assert not list((f.tmp / "fresh").glob("**/*.jsonl"))


@pytest.mark.parametrize("mutation", ["revision", "traversal", "absolute", "windows", "oversize", "hash", "duplicate"])
def test_registry_rejects_unpinned_or_unsafe_files(source_fixture, mutation):
    f = source_fixture
    f.add([f.row()])
    config = json.loads(f.registry.read_text())
    source = config["sources"][0]
    if mutation == "revision": source["revision"] = "main"
    elif mutation == "traversal": source["files"][0]["path"] = "../private.txt"
    elif mutation == "absolute": source["files"][0]["path"] = "/private.txt"
    elif mutation == "windows": source["files"][0]["path"] = "C:\\private.txt"
    elif mutation == "oversize": source["files"][0]["bytes"] = 1_000_000_000
    elif mutation == "hash": source["files"][0]["sha256"] = "unknown"
    else: config["sources"].append(deepcopy(source))
    f.registry.write_text(json.dumps(config))
    with pytest.raises(ValueError): load_registry(f.registry)


def test_revision_mismatch_fails_before_processing(source_fixture):
    f = source_fixture
    f.add([f.row()])
    config = load_registry(f.registry)
    config["sources"][0]["revision"] = "b" * 40
    with pytest.raises(ValueError, match="revision/checksum"):
        verify_snapshots(config, f.raw)


def test_string_license_approval_cannot_be_treated_as_boolean_true(source_fixture):
    f = source_fixture
    f.add([f.row()], license_verified="false")
    with pytest.raises(ValueError, match="license decision"):
        load_registry(f.registry)
