import pytest

from app.storage import LocalStore, StorageError


def test_local_store_persists_projects_and_assets(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    project = store.create_project("project-1", "FINOMICS launch")

    assert project["id"] == "project-1"
    assert store.get_project("project-1")["title"] == "FINOMICS launch"
    assert store.list_projects()[0]["id"] == "project-1"

    asset = {
        "id": "asset-1",
        "project_id": "project-1",
        "original_name": "scene.mp4",
        "stored_name": "asset-1.mp4",
        "media_type": "video/mp4",
        "size_bytes": 1024,
        "sha256": "a" * 64,
    }
    stored = store.register_asset(asset)
    assert stored["sha256"] == "a" * 64
    assert store.get_asset("asset-1")["stored_name"] == "asset-1.mp4"
    assert store.list_assets("project-1")[0]["id"] == "asset-1"

    reopened = LocalStore(tmp_path / "studio-data")
    assert reopened.get_project("project-1")["title"] == "FINOMICS launch"
    assert reopened.get_asset("asset-1")["original_name"] == "scene.mp4"


def test_local_store_rejects_asset_for_unknown_project(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    asset = {
        "id": "asset-1",
        "project_id": "missing",
        "original_name": "scene.mp4",
        "stored_name": "asset-1.mp4",
        "media_type": "video/mp4",
        "size_bytes": 10,
        "sha256": "b" * 64,
    }
    with pytest.raises(StorageError, match="Project does not exist"):
        store.register_asset(asset)


def test_local_store_uses_parameterized_project_values(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    title = "Project'); DROP TABLE projects; --"
    store.create_project("project-1", title)
    assert store.get_project("project-1")["title"] == title
    assert len(store.list_projects()) == 1
