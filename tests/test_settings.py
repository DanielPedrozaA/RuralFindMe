import json

import pytest

from app.config.settings import ConfigurationError, load_json_config


def test_load_json_config_reports_missing_bundle_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.resource_path", lambda _relative: tmp_path / "missing.json")
    with pytest.raises(ConfigurationError, match="configuración interna"):
        load_json_config("missing.json")


def test_load_json_config_reports_malformed_json(tmp_path, monkeypatch):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr("app.config.settings.resource_path", lambda _relative: path)
    with pytest.raises(ConfigurationError, match="broken.json"):
        load_json_config("broken.json")


def test_load_json_config_requires_object_root(tmp_path, monkeypatch):
    path = tmp_path / "list.json"
    path.write_text(json.dumps(["unexpected"]), encoding="utf-8")
    monkeypatch.setattr("app.config.settings.resource_path", lambda _relative: path)
    with pytest.raises(ConfigurationError, match="formato esperado"):
        load_json_config("list.json")
