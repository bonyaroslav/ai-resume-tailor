from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from prompt_loader import PromptTemplate

DEFAULT_KNOWLEDGE_CACHE_TTL_SECONDS = 3600
DEFAULT_KNOWLEDGE_CACHE_REGISTRY_PATH = Path(
    "runs/_cache/role_wide_knowledge_cache_registry.json"
)


class KnowledgeCacheError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeFileDescriptor:
    path: Path
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class RoleWideKnowledgeCache:
    remote_cache_name: str
    fingerprint: str
    expires_at: str | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso8601(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_path_for_registry(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def discover_role_wide_knowledge_files(
    prompt_templates: dict[str, PromptTemplate],
) -> list[KnowledgeFileDescriptor]:
    unique_paths: dict[str, Path] = {}
    for template in prompt_templates.values():
        for knowledge_file in template.knowledge_files:
            relative_path = _normalize_path_for_registry(knowledge_file)
            unique_paths[relative_path] = knowledge_file.resolve()

    descriptors: list[KnowledgeFileDescriptor] = []
    for relative_path in sorted(unique_paths):
        path = unique_paths[relative_path]
        descriptors.append(
            KnowledgeFileDescriptor(
                path=path,
                relative_path=relative_path,
                sha256=_sha256_file(path),
            )
        )
    return descriptors


def compute_role_wide_knowledge_cache_fingerprint(
    *,
    role_name: str,
    model_name: str,
    knowledge_files: list[KnowledgeFileDescriptor],
) -> str:
    payload = {
        "role_name": role_name,
        "model_name": model_name,
        "knowledge_files": [
            {"path": item.relative_path, "sha256": item.sha256}
            for item in knowledge_files
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"entries": []}
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise KnowledgeCacheError("Knowledge cache registry must be a JSON object.")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise KnowledgeCacheError("Knowledge cache registry must contain 'entries'.")
    return data


def _write_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _find_matching_cache_entry(
    entries: list[dict[str, Any]],
    *,
    role_name: str,
    model_name: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    for entry in entries:
        if (
            entry.get("role_name") == role_name
            and entry.get("model_name") == model_name
            and entry.get("fingerprint") == fingerprint
        ):
            return entry
    return None


def _find_reusable_file_record(
    entries: list[dict[str, Any]],
    *,
    relative_path: str,
    content_sha256: str,
) -> dict[str, Any] | None:
    for entry in entries:
        knowledge_files = entry.get("knowledge_files", [])
        if not isinstance(knowledge_files, list):
            continue
        for record in knowledge_files:
            if not isinstance(record, dict):
                continue
            if (
                record.get("path") == relative_path
                and record.get("sha256") == content_sha256
                and record.get("remote_file_name")
                and record.get("remote_file_uri")
            ):
                return record
    return None


def _cache_is_expired(expire_time: datetime | None) -> bool:
    if expire_time is None:
        return False
    return expire_time <= _utc_now()


def _confirm_remote_cache(client: Any, remote_cache_name: str) -> Any | None:
    try:
        remote_cache = client.caches.get(name=remote_cache_name)
    except Exception:
        return None
    if _cache_is_expired(getattr(remote_cache, "expire_time", None)):
        return None
    return remote_cache


def _confirm_remote_file(client: Any, remote_file_name: str) -> Any | None:
    try:
        remote_file = client.files.get(name=remote_file_name)
    except Exception:
        return None
    if not getattr(remote_file, "uri", None):
        return None
    return remote_file


def _build_file_record(
    descriptor: KnowledgeFileDescriptor, remote_file: Any
) -> dict[str, Any]:
    return {
        "path": descriptor.relative_path,
        "sha256": descriptor.sha256,
        "remote_file_name": getattr(remote_file, "name", None),
        "remote_file_uri": getattr(remote_file, "uri", None),
        "mime_type": getattr(remote_file, "mime_type", None),
        "uploaded_at": _to_iso8601(_utc_now()),
    }


def _create_genai_client_factory() -> Callable[[str], Any]:
    def _factory(api_key: str) -> Any:
        from google import genai

        return genai.Client(api_key=api_key)

    return _factory


def prewarm_role_wide_knowledge_cache(
    *,
    api_key: str,
    role_name: str,
    model_name: str,
    prompt_templates: dict[str, PromptTemplate],
    registry_path: Path,
    ttl_seconds: int,
    invalidate_cache: bool,
    logger: logging.Logger,
    client_factory: Callable[[str], Any] | None = None,
) -> RoleWideKnowledgeCache:
    knowledge_files = discover_role_wide_knowledge_files(prompt_templates)
    fingerprint = compute_role_wide_knowledge_cache_fingerprint(
        role_name=role_name,
        model_name=model_name,
        knowledge_files=knowledge_files,
    )
    logger.info(
        "Knowledge cache prewarm role_name=%s model_name=%s active_prompt_count=%s unique_knowledge_file_count=%s fingerprint=%s invalidate_cache=%s",
        role_name,
        model_name,
        len(prompt_templates),
        len(knowledge_files),
        fingerprint,
        invalidate_cache,
    )
    for item in knowledge_files:
        logger.info(
            "Knowledge cache file path=%s sha256=%s",
            item.relative_path,
            item.sha256,
        )

    registry = _load_registry(registry_path)
    entries = registry["entries"]
    matching_entry = None
    if not invalidate_cache:
        matching_entry = _find_matching_cache_entry(
            entries,
            role_name=role_name,
            model_name=model_name,
            fingerprint=fingerprint,
        )

    factory = client_factory or _create_genai_client_factory()
    client = factory(api_key)

    if matching_entry is not None:
        cached = matching_entry.get("cache", {})
        remote_cache_name = cached.get("remote_cache_name")
        if isinstance(remote_cache_name, str) and remote_cache_name:
            remote_cache = _confirm_remote_cache(client, remote_cache_name)
            if remote_cache is not None:
                expires_at = _to_iso8601(getattr(remote_cache, "expire_time", None))
                logger.info(
                    "Knowledge cache reuse remote_cache_name=%s expires_at=%s",
                    remote_cache_name,
                    expires_at or "-",
                )
                return RoleWideKnowledgeCache(
                    remote_cache_name=remote_cache_name,
                    fingerprint=fingerprint,
                    expires_at=expires_at,
                )
        logger.info(
            "Knowledge cache rebuild required because remote cache was unavailable."
        )

    uploaded_records: list[dict[str, Any]] = []
    for item in knowledge_files:
        reusable_record = _find_reusable_file_record(
            entries,
            relative_path=item.relative_path,
            content_sha256=item.sha256,
        )
        if reusable_record is not None:
            remote_file_name = reusable_record.get("remote_file_name")
            if isinstance(remote_file_name, str) and remote_file_name:
                remote_file = _confirm_remote_file(client, remote_file_name)
                if remote_file is not None:
                    logger.info(
                        "Knowledge cache file reuse path=%s remote_file_name=%s",
                        item.relative_path,
                        remote_file_name,
                    )
                    uploaded_records.append(_build_file_record(item, remote_file))
                    continue

        remote_file = client.files.upload(file=str(item.path))
        logger.info(
            "Knowledge cache file upload path=%s remote_file_name=%s",
            item.relative_path,
            getattr(remote_file, "name", "-"),
        )
        uploaded_records.append(_build_file_record(item, remote_file))

    from google.genai import types

    contents = [
        types.Part.from_uri(
            file_uri=record["remote_file_uri"],
            mime_type=record.get("mime_type") or "text/markdown",
        )
        for record in uploaded_records
    ]
    display_name = f"{role_name}-knowledge-cache"
    remote_cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            display_name=display_name,
            contents=contents,
            ttl=f"{ttl_seconds}s",
        ),
    )
    confirmed_cache = _confirm_remote_cache(client, getattr(remote_cache, "name", ""))
    if confirmed_cache is None or not getattr(confirmed_cache, "name", None):
        raise KnowledgeCacheError("Knowledge cache creation could not be confirmed.")

    expires_at = _to_iso8601(getattr(confirmed_cache, "expire_time", None))
    logger.info(
        "Knowledge cache created remote_cache_name=%s expires_at=%s",
        confirmed_cache.name,
        expires_at or "-",
    )

    new_entry = {
        "role_name": role_name,
        "model_name": model_name,
        "fingerprint": fingerprint,
        "knowledge_files": uploaded_records,
        "cache": {
            "remote_cache_name": confirmed_cache.name,
            "created_at": _to_iso8601(getattr(confirmed_cache, "create_time", None))
            or _to_iso8601(_utc_now()),
            "expires_at": expires_at,
            "model_name": model_name,
            "fingerprint": fingerprint,
        },
    }
    preserved_entries = [
        entry
        for entry in entries
        if not (
            entry.get("role_name") == role_name
            and entry.get("model_name") == model_name
            and entry.get("fingerprint") == fingerprint
        )
    ]
    registry["entries"] = preserved_entries + [new_entry]
    _write_registry(registry_path, registry)

    return RoleWideKnowledgeCache(
        remote_cache_name=confirmed_cache.name,
        fingerprint=fingerprint,
        expires_at=expires_at,
    )
