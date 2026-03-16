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
class RunScopedKnowledgeCache:
    remote_cache_name: str
    expires_at: str | None
    stable_fingerprint: str
    job_description_sha256: str


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


def discover_stable_knowledge_files(
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


def compute_stable_knowledge_fingerprint(
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


def _default_registry() -> dict[str, Any]:
    return {"knowledge_files": [], "run_caches": []}


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_registry()

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise KnowledgeCacheError("Knowledge cache registry must be a JSON object.")

    if "entries" in data:
        legacy_entries = data.get("entries")
        if not isinstance(legacy_entries, list):
            raise KnowledgeCacheError("Knowledge cache registry must contain lists.")
        knowledge_files: list[dict[str, Any]] = []
        for entry in legacy_entries:
            if not isinstance(entry, dict):
                continue
            records = entry.get("knowledge_files", [])
            if not isinstance(records, list):
                continue
            for record in records:
                if isinstance(record, dict):
                    knowledge_files.append(record)
        return {"knowledge_files": knowledge_files, "run_caches": []}

    knowledge_files = data.get("knowledge_files")
    run_caches = data.get("run_caches")
    if not isinstance(knowledge_files, list) or not isinstance(run_caches, list):
        raise KnowledgeCacheError(
            "Knowledge cache registry must contain 'knowledge_files' and 'run_caches'."
        )
    return data


def _write_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _find_reusable_file_record(
    records: list[dict[str, Any]],
    *,
    relative_path: str,
    content_sha256: str,
) -> dict[str, Any] | None:
    for record in records:
        if (
            isinstance(record, dict)
            and record.get("path") == relative_path
            and record.get("sha256") == content_sha256
            and record.get("remote_file_name")
            and record.get("remote_file_uri")
        ):
            return record
    return None


def _find_run_cache_record(
    records: list[dict[str, Any]],
    *,
    run_id: str,
    role_name: str,
    model_name: str,
) -> dict[str, Any] | None:
    for record in records:
        if (
            isinstance(record, dict)
            and record.get("run_id") == run_id
            and record.get("role_name") == role_name
            and record.get("model_name") == model_name
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


def _build_job_description_record(
    *, path: Path, remote_file: Any, sha256_value: str
) -> dict[str, Any]:
    return {
        "path": _normalize_path_for_registry(path),
        "sha256": sha256_value,
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


def _resolve_stable_remote_files(
    *,
    client: Any,
    knowledge_files: list[KnowledgeFileDescriptor],
    registry_records: list[dict[str, Any]],
    force_reupload: bool,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    uploaded_records: list[dict[str, Any]] = []
    for item in knowledge_files:
        if not force_reupload:
            reusable_record = _find_reusable_file_record(
                registry_records,
                relative_path=item.relative_path,
                content_sha256=item.sha256,
            )
            if reusable_record is not None:
                remote_file_name = reusable_record.get("remote_file_name")
                if isinstance(remote_file_name, str) and remote_file_name:
                    remote_file = _confirm_remote_file(client, remote_file_name)
                    if remote_file is not None:
                        logger.info(
                            "Stable knowledge file reuse path=%s remote_file_name=%s",
                            item.relative_path,
                            remote_file_name,
                        )
                        uploaded_records.append(_build_file_record(item, remote_file))
                        continue

        remote_file = client.files.upload(file=str(item.path))
        logger.info(
            "Stable knowledge file upload path=%s remote_file_name=%s",
            item.relative_path,
            getattr(remote_file, "name", "-"),
        )
        uploaded_records.append(_build_file_record(item, remote_file))
    return uploaded_records


def _upload_job_description_file(
    *,
    client: Any,
    job_description_path: Path,
    job_description_sha256: str,
    logger: logging.Logger,
) -> dict[str, Any]:
    remote_file = client.files.upload(file=str(job_description_path))
    logger.info(
        "Job description upload path=%s remote_file_name=%s sha256=%s",
        _normalize_path_for_registry(job_description_path),
        getattr(remote_file, "name", "-"),
        job_description_sha256,
    )
    return _build_job_description_record(
        path=job_description_path,
        remote_file=remote_file,
        sha256_value=job_description_sha256,
    )


def _create_run_scoped_cached_content(
    *,
    client: Any,
    run_id: str,
    role_name: str,
    model_name: str,
    ttl_seconds: int,
    stable_records: list[dict[str, Any]],
    job_description_record: dict[str, Any],
) -> Any:
    from google.genai import types

    all_records = stable_records + [job_description_record]
    parts = [
        types.Part.from_uri(
            file_uri=record["remote_file_uri"],
            mime_type=record.get("mime_type") or "text/markdown",
        )
        for record in all_records
    ]
    display_name = f"{role_name}-{run_id}-run-cache"
    return client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            display_name=display_name,
            contents=[types.Content(role="user", parts=parts)],
            ttl=f"{ttl_seconds}s",
        ),
    )


def _upsert_knowledge_file_records(
    existing_records: list[dict[str, Any]], new_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    preserved: list[dict[str, Any]] = []
    keys_to_replace = {(record["path"], record["sha256"]) for record in new_records}
    for record in existing_records:
        if not isinstance(record, dict):
            continue
        key = (record.get("path"), record.get("sha256"))
        if key in keys_to_replace:
            continue
        preserved.append(record)
    return preserved + new_records


def _upsert_run_cache_record(
    existing_records: list[dict[str, Any]], new_record: dict[str, Any]
) -> list[dict[str, Any]]:
    preserved: list[dict[str, Any]] = []
    for record in existing_records:
        if not isinstance(record, dict):
            continue
        if (
            record.get("run_id") == new_record.get("run_id")
            and record.get("role_name") == new_record.get("role_name")
            and record.get("model_name") == new_record.get("model_name")
        ):
            continue
        preserved.append(record)
    return preserved + [new_record]


def prepare_run_scoped_knowledge_cache(
    *,
    api_key: str,
    run_id: str,
    role_name: str,
    model_name: str,
    prompt_templates: dict[str, PromptTemplate],
    job_description_path: Path,
    registry_path: Path,
    ttl_seconds: int,
    invalidate_cache: bool,
    force_reupload: bool,
    logger: logging.Logger,
    client_factory: Callable[[str], Any] | None = None,
) -> RunScopedKnowledgeCache:
    knowledge_files = discover_stable_knowledge_files(prompt_templates)
    stable_fingerprint = compute_stable_knowledge_fingerprint(
        role_name=role_name,
        model_name=model_name,
        knowledge_files=knowledge_files,
    )
    job_description_sha256 = _sha256_file(job_description_path)
    logger.info(
        "Run cache preparation run_id=%s role_name=%s model_name=%s stable_knowledge_file_count=%s stable_fingerprint=%s invalidate_cache=%s force_reupload=%s",
        run_id,
        role_name,
        model_name,
        len(knowledge_files),
        stable_fingerprint,
        invalidate_cache,
        force_reupload,
    )

    registry = _load_registry(registry_path)
    knowledge_file_records = registry["knowledge_files"]
    run_cache_records = registry["run_caches"]
    client = (client_factory or _create_genai_client_factory())(api_key)

    if not invalidate_cache:
        existing_run_cache = _find_run_cache_record(
            run_cache_records,
            run_id=run_id,
            role_name=role_name,
            model_name=model_name,
        )
        if existing_run_cache is not None:
            # Reuse is only safe when the run identity and the exact JD content
            # still match. This keeps reruns with a reused run_id from silently
            # binding to stale cached content after the JD changes.
            existing_job_description_sha256 = existing_run_cache.get(
                "job_description_sha256"
            )
            if existing_job_description_sha256 != job_description_sha256:
                logger.info(
                    "Run cache recreate required because job description changed. run_id=%s stored_job_description_sha256=%s current_job_description_sha256=%s",
                    run_id,
                    existing_job_description_sha256 or "-",
                    job_description_sha256,
                )
            else:
                remote_cache_name = existing_run_cache.get("cache", {}).get(
                    "remote_cache_name"
                )
                if isinstance(remote_cache_name, str) and remote_cache_name:
                    confirmed_cache = _confirm_remote_cache(client, remote_cache_name)
                    if confirmed_cache is not None:
                        expires_at = _to_iso8601(
                            getattr(confirmed_cache, "expire_time", None)
                        )
                        logger.info(
                            "Run cache reuse run_id=%s remote_cache_name=%s expires_at=%s",
                            run_id,
                            remote_cache_name,
                            expires_at or "-",
                        )
                        return RunScopedKnowledgeCache(
                            remote_cache_name=remote_cache_name,
                            expires_at=expires_at,
                            stable_fingerprint=str(
                                existing_run_cache.get("stable_fingerprint")
                                or stable_fingerprint
                            ),
                            job_description_sha256=job_description_sha256,
                        )
                logger.info(
                    "Run cache recreate required because cached content was unavailable. run_id=%s",
                    run_id,
                )

    stable_records = _resolve_stable_remote_files(
        client=client,
        knowledge_files=knowledge_files,
        registry_records=knowledge_file_records,
        force_reupload=force_reupload,
        logger=logger,
    )
    job_description_record = _upload_job_description_file(
        client=client,
        job_description_path=job_description_path,
        job_description_sha256=job_description_sha256,
        logger=logger,
    )

    remote_cache = _create_run_scoped_cached_content(
        client=client,
        run_id=run_id,
        role_name=role_name,
        model_name=model_name,
        ttl_seconds=ttl_seconds,
        stable_records=stable_records,
        job_description_record=job_description_record,
    )
    confirmed_cache = _confirm_remote_cache(client, getattr(remote_cache, "name", ""))
    if confirmed_cache is None or not getattr(confirmed_cache, "name", None):
        raise KnowledgeCacheError("Knowledge cache creation could not be confirmed.")

    expires_at = _to_iso8601(getattr(confirmed_cache, "expire_time", None))
    logger.info(
        "Run cache ready run_id=%s remote_cache_name=%s expires_at=%s",
        run_id,
        confirmed_cache.name,
        expires_at or "-",
    )

    registry["knowledge_files"] = _upsert_knowledge_file_records(
        knowledge_file_records,
        stable_records,
    )
    registry["run_caches"] = _upsert_run_cache_record(
        run_cache_records,
        {
            "run_id": run_id,
            "role_name": role_name,
            "model_name": model_name,
            "job_description_path": _normalize_path_for_registry(job_description_path),
            "job_description_sha256": job_description_sha256,
            "knowledge_files": [
                {"path": item.relative_path, "sha256": item.sha256}
                for item in knowledge_files
            ],
            "stable_fingerprint": stable_fingerprint,
            "cache": {
                "remote_cache_name": confirmed_cache.name,
                "created_at": _to_iso8601(getattr(confirmed_cache, "create_time", None))
                or _to_iso8601(_utc_now()),
                "expires_at": expires_at,
            },
        },
    )
    _write_registry(registry_path, registry)

    return RunScopedKnowledgeCache(
        remote_cache_name=confirmed_cache.name,
        expires_at=expires_at,
        stable_fingerprint=stable_fingerprint,
        job_description_sha256=job_description_sha256,
    )
