"""Explicit, bounded downloads of public revision/hash-pinned dataset files.

No credentials, model downloads, code execution or automatic license approval.
License/use decisions belong to the reviewed source registry.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote
from urllib.request import urlopen

MAX_FILE_BYTES = 50_000_000


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_registry(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "source-registry-1.0" or not isinstance(value.get("sources"), list):
        raise ValueError("Unsupported source registry")
    limit = value.get("max_download_bytes", MAX_FILE_BYTES)
    if type(limit) is not int or not 0 < limit <= MAX_FILE_BYTES:
        raise ValueError("Invalid approved download bound")
    seen = set()
    for source in value["sources"]:
        if not re.fullmatch(r"[a-z0-9_-]+", source["source_id"]) or source["source_id"] in seen:
            raise ValueError("Invalid or duplicate source ID")
        seen.add(source["source_id"])
        if not re.fullmatch(r"[0-9a-f]{40}", source["revision"]):
            raise ValueError("Source revision must be an immutable 40-character commit")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repo_id"]):
            raise ValueError("Invalid public Hugging Face dataset ID")
        if source["usage"] not in {"retrieval_corpus", "quarantine", "evaluation_only"}:
            raise ValueError("Unknown source usage")
        if type(source.get("license_verified")) is not bool or not isinstance(source.get("license"), str):
            raise ValueError("Explicit license decision and evidence are required")
        paths = set()
        for item in source["files"]:
            name = PurePosixPath(item["path"])
            if name.is_absolute() or ".." in name.parts or "\\" in str(name) or ":" in str(name) or str(name) in paths:
                raise ValueError("Unsafe or duplicate source path")
            paths.add(str(name))
            if type(item["bytes"]) is not int or not 0 < item["bytes"] <= limit:
                raise ValueError("File exceeds the approved small-download bound")
            if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                raise ValueError("Expected SHA-256 is required")
    return value


def snapshot_path(root: Path, source: dict, filename: str) -> Path:
    return root / source["source_id"] / source["revision"] / filename


def verify_snapshots(registry: dict, root: Path) -> None:
    for source in registry["sources"]:
        for item in source["files"]:
            path = snapshot_path(root, source, item["path"])
            if not path.is_file() or path.stat().st_size != item["bytes"] or file_sha256(path) != item["sha256"]:
                raise ValueError(f"Snapshot/revision/checksum mismatch: {source['source_id']}/{item['path']}")


def fetch(registry_path: Path, root: Path, *, opener=None) -> dict:
    registry = load_registry(registry_path)
    opener = opener or urlopen
    result = {"downloaded_files": 0, "verified_existing_files": 0, "bytes_downloaded": 0}
    for source in registry["sources"]:
        for item in source["files"]:
            target = snapshot_path(root, source, item["path"])
            if target.exists():
                if target.stat().st_size != item["bytes"] or file_sha256(target) != item["sha256"]:
                    raise ValueError("Immutable snapshot differs; refusing to overwrite " + str(target))
                result["verified_existing_files"] += 1
                continue
            url = ("https://huggingface.co/datasets/" + source["repo_id"] + "/resolve/"
                   + source["revision"] + "/" + quote(item["path"]))
            with opener(url, timeout=90) as response:
                data = response.read(item["bytes"] + 1)
            if len(data) != item["bytes"] or sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("Downloaded size/checksum mismatch: " + item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            result["downloaded_files"] += 1
            result["bytes_downloaded"] += len(data)
    verify_snapshots(registry, root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify_snapshots(load_registry(args.registry), args.raw)
        print("All source snapshots match pinned revisions, sizes and SHA-256 hashes")
    else:
        print(json.dumps(fetch(args.registry, args.raw), indent=2))


if __name__ == "__main__":
    main()
