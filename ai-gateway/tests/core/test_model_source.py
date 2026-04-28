from __future__ import annotations

from app.core.model_source import resolve_model_source


def test_resolve_model_source_prefers_existing_local_directory(monkeypatch, tmp_path) -> None:
    model_dir = tmp_path / "models" / "bge-m3"
    model_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    resolved = resolve_model_source(
        model_name="BAAI/bge-m3",
        local_model_path="models/bge-m3",
    )

    assert resolved.source_kind == "local_path"
    assert resolved.source == str(model_dir.resolve())
    assert resolved.configured_path == "models/bge-m3"


def test_resolve_model_source_falls_back_when_local_directory_missing(tmp_path) -> None:
    missing_dir = tmp_path / "missing-bge-m3"

    resolved = resolve_model_source(
        model_name="BAAI/bge-m3",
        local_model_path=str(missing_dir),
    )

    assert resolved.source_kind == "model_name"
    assert resolved.source == "BAAI/bge-m3"
    assert resolved.configured_path == str(missing_dir)
