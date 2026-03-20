from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from knowledge_cache import (
    compute_stable_knowledge_fingerprint,
    discover_stable_knowledge_files,
    prepare_run_scoped_knowledge_cache,
)
from prompt_loader import PromptTemplate
from tests.test_support import make_workspace_temp_dir


def _template(
    section_id: str, body: str, knowledge_files: list[Path]
) -> PromptTemplate:
    return PromptTemplate(
        section_id=section_id,
        path=Path(f"prompts/{section_id}.md"),
        body=body,
        knowledge_files=knowledge_files,
    )


def test_discover_stable_knowledge_files_deduplicates_and_sorts() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-discovery")
    file_b = tmp_path / "b.md"
    file_a = tmp_path / "a.md"
    file_a.write_text("A", encoding="utf-8")
    file_b.write_text("B", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [file_b, file_a],
        ),
        "section_skills_alignment": _template(
            "section_skills_alignment",
            "skills",
            [file_a],
        ),
    }

    discovered = discover_stable_knowledge_files(templates)

    assert [item.path.name for item in discovered] == ["a.md", "b.md"]


def test_cache_fingerprint_changes_when_knowledge_content_changes() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-fingerprint-content")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("first", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }

    first = compute_stable_knowledge_fingerprint(
        input_profile="role_a",
        model_name="gemini-test",
        knowledge_files=discover_stable_knowledge_files(templates),
    )
    knowledge_file.write_text("second", encoding="utf-8")
    second = compute_stable_knowledge_fingerprint(
        input_profile="role_a",
        model_name="gemini-test",
        knowledge_files=discover_stable_knowledge_files(templates),
    )

    assert first != second


def test_cache_fingerprint_does_not_change_when_prompt_body_changes_only() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-fingerprint-body")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    first_templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "first body",
            [knowledge_file],
        )
    }
    second_templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "second body",
            [knowledge_file],
        )
    }

    first = compute_stable_knowledge_fingerprint(
        input_profile="role_a",
        model_name="gemini-test",
        knowledge_files=discover_stable_knowledge_files(first_templates),
    )
    second = compute_stable_knowledge_fingerprint(
        input_profile="role_a",
        model_name="gemini-test",
        knowledge_files=discover_stable_knowledge_files(second_templates),
    )

    assert first == second


class _FakeFilesApi:
    def __init__(self) -> None:
        self.upload_calls: list[str] = []
        self._records: dict[str, SimpleNamespace] = {}
        self._counter = 0

    def upload(self, *, file: str) -> SimpleNamespace:
        self._counter += 1
        remote_name = f"files/upload-{self._counter}"
        record = SimpleNamespace(
            name=remote_name,
            uri=f"https://example.test/{remote_name}",
            mime_type="text/markdown",
        )
        self._records[remote_name] = record
        self.upload_calls.append(file)
        return record

    def get(self, *, name: str) -> SimpleNamespace:
        return self._records[name]


class _FakeCachesApi:
    def __init__(self) -> None:
        self.create_calls: list[SimpleNamespace] = []
        self._records: dict[str, SimpleNamespace] = {}
        self._counter = 0

    def create(self, *, model: str, config: object) -> SimpleNamespace:
        self._counter += 1
        remote_name = f"cachedContents/test-{self._counter}"
        record = SimpleNamespace(
            name=remote_name,
            create_time=datetime.now(timezone.utc),
            expire_time=datetime.now(timezone.utc) + timedelta(hours=1),
            model=model,
            config=config,
        )
        self._records[remote_name] = record
        self.create_calls.append(record)
        return record

    def get(self, *, name: str) -> SimpleNamespace:
        return self._records[name]


class _FakeClient:
    def __init__(self) -> None:
        self.files = _FakeFilesApi()
        self.caches = _FakeCachesApi()


def test_prepare_run_scoped_knowledge_cache_reuses_existing_remote_file() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-reuse")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    job_description_path = tmp_path / "job_description.md"
    job_description_path.write_text("Need Python", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }
    client = _FakeClient()
    existing_remote = client.files.upload(file=str(knowledge_file))
    discovered = discover_stable_knowledge_files(templates)

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        f"""{{
  \"knowledge_files\": [
    {{
      \"path\": \"{discovered[0].relative_path}\",
      \"sha256\": \"{discovered[0].sha256}\",
      \"remote_file_name\": \"{existing_remote.name}\",
      \"remote_file_uri\": \"{existing_remote.uri}\",
      \"mime_type\": \"{existing_remote.mime_type}\"
    }}
  ],
  \"run_caches\": []
}}""",
        encoding="utf-8",
    )

    cache = prepare_run_scoped_knowledge_cache(
        api_key="test-key",
        run_id="run-1",
        input_profile="role_a",
        model_name="gemini-test",
        prompt_templates=templates,
        job_description_path=job_description_path,
        registry_path=registry_path,
        ttl_seconds=300,
        invalidate_cache=False,
        force_reupload=False,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        client_factory=lambda _: client,
    )

    assert client.files.upload_calls == [str(knowledge_file), str(job_description_path)]
    assert cache.stable_fingerprint


def test_prepare_run_scoped_knowledge_cache_force_reupload_uploads_again() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-force-reupload")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    job_description_path = tmp_path / "job_description.md"
    job_description_path.write_text("Need Python", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }
    client = _FakeClient()
    existing_remote = client.files.upload(file=str(knowledge_file))
    discovered = discover_stable_knowledge_files(templates)

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        f"""{{
  \"knowledge_files\": [
    {{
      \"path\": \"{discovered[0].relative_path}\",
      \"sha256\": \"{discovered[0].sha256}\",
      \"remote_file_name\": \"{existing_remote.name}\",
      \"remote_file_uri\": \"{existing_remote.uri}\",
      \"mime_type\": \"{existing_remote.mime_type}\"
    }}
  ],
  \"run_caches\": []
}}""",
        encoding="utf-8",
    )

    prepare_run_scoped_knowledge_cache(
        api_key="test-key",
        run_id="run-1",
        input_profile="role_a",
        model_name="gemini-test",
        prompt_templates=templates,
        job_description_path=job_description_path,
        registry_path=registry_path,
        ttl_seconds=300,
        invalidate_cache=False,
        force_reupload=True,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        client_factory=lambda _: client,
    )

    assert len(client.files.upload_calls) == 3
    assert Path(client.files.upload_calls[0]).resolve() == knowledge_file.resolve()
    assert Path(client.files.upload_calls[1]).resolve() == knowledge_file.resolve()
    assert (
        Path(client.files.upload_calls[2]).resolve() == job_description_path.resolve()
    )


def test_prepare_run_scoped_knowledge_cache_reuses_existing_run_cache_when_jd_matches() -> (
    None
):
    tmp_path = make_workspace_temp_dir("knowledge-cache-run-reuse")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    job_description_path = tmp_path / "job_description.md"
    job_description_path.write_text("Need Python", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }
    client = _FakeClient()
    stable_remote = client.files.upload(file=str(knowledge_file))
    discovered = discover_stable_knowledge_files(templates)
    stable_fingerprint = compute_stable_knowledge_fingerprint(
        input_profile="role_a",
        model_name="gemini-test",
        knowledge_files=discovered,
    )
    cached_content = client.caches.create(model="gemini-test", config=object())
    job_description_sha256 = sha256(job_description_path.read_bytes()).hexdigest()

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        f"""{{
  "knowledge_files": [
    {{
      "path": "{discovered[0].relative_path}",
      "sha256": "{discovered[0].sha256}",
      "remote_file_name": "{stable_remote.name}",
      "remote_file_uri": "{stable_remote.uri}",
      "mime_type": "{stable_remote.mime_type}"
    }}
  ],
  "run_caches": [
    {{
      "run_id": "run-1",
      "input_profile": "role_a",
      "model_name": "gemini-test",
      "job_description_sha256": "{job_description_sha256}",
      "stable_fingerprint": "{stable_fingerprint}",
      "cache": {{
        "remote_cache_name": "{cached_content.name}"
      }}
    }}
  ]
}}""",
        encoding="utf-8",
    )

    cache = prepare_run_scoped_knowledge_cache(
        api_key="test-key",
        run_id="run-1",
        input_profile="role_a",
        model_name="gemini-test",
        prompt_templates=templates,
        job_description_path=job_description_path,
        registry_path=registry_path,
        ttl_seconds=300,
        invalidate_cache=False,
        force_reupload=False,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        client_factory=lambda _: client,
    )

    assert client.files.upload_calls == [str(knowledge_file)]
    assert len(client.caches.create_calls) == 1
    assert cache.remote_cache_name == cached_content.name
    assert cache.stable_fingerprint == stable_fingerprint


def test_prepare_run_scoped_knowledge_cache_recreates_run_cache_when_jd_changes() -> (
    None
):
    tmp_path = make_workspace_temp_dir("knowledge-cache-run-jd-change")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    job_description_path = tmp_path / "job_description.md"
    job_description_path.write_text("Need Python", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }
    client = _FakeClient()
    stable_remote = client.files.upload(file=str(knowledge_file))
    discovered = discover_stable_knowledge_files(templates)
    cached_content = client.caches.create(model="gemini-test", config=object())

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        f"""{{
  "knowledge_files": [
    {{
      "path": "{discovered[0].relative_path}",
      "sha256": "{discovered[0].sha256}",
      "remote_file_name": "{stable_remote.name}",
      "remote_file_uri": "{stable_remote.uri}",
      "mime_type": "{stable_remote.mime_type}"
    }}
  ],
  "run_caches": [
    {{
      "run_id": "run-1",
      "input_profile": "role_a",
      "model_name": "gemini-test",
      "job_description_sha256": "stale-hash",
      "stable_fingerprint": "stale-fingerprint",
      "cache": {{
        "remote_cache_name": "{cached_content.name}"
      }}
    }}
  ]
}}""",
        encoding="utf-8",
    )

    cache = prepare_run_scoped_knowledge_cache(
        api_key="test-key",
        run_id="run-1",
        input_profile="role_a",
        model_name="gemini-test",
        prompt_templates=templates,
        job_description_path=job_description_path,
        registry_path=registry_path,
        ttl_seconds=300,
        invalidate_cache=False,
        force_reupload=False,
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        client_factory=lambda _: client,
    )

    assert client.files.upload_calls == [str(knowledge_file), str(job_description_path)]
    assert len(client.caches.create_calls) == 2
    assert cache.remote_cache_name != cached_content.name
    assert cache.stable_fingerprint != "stale-fingerprint"
