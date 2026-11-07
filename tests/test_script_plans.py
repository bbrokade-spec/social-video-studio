from app.storage import LocalStore


def sample_plan():
    return {
        "id": "plan-1",
        "project_id": "project-1",
        "title": "Inflation explained",
        "full_script": "Inflation reduces purchasing power over time.",
        "output_profile": "vertical",
        "scenes": [
            {
                "id": "scene-1",
                "position": 0,
                "narration_text": "Prices rise over time.",
                "visual_prompt": "A supermarket price tag changing over time, cinematic documentary style",
                "negative_prompt": "blurry, watermark",
                "duration_seconds": 5.0,
            },
            {
                "id": "scene-2",
                "position": 1,
                "narration_text": "The same money buys less.",
                "visual_prompt": "A person comparing a small grocery basket with an older larger basket",
                "negative_prompt": "",
                "duration_seconds": 6.0,
            },
        ],
    }


def test_script_plan_and_scenes_persist_and_keep_order(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    store.create_project("project-1", "FINOMICS test")

    created = store.create_script_plan(sample_plan())
    assert created["id"] == "plan-1"
    assert [scene["position"] for scene in created["scenes"]] == [0, 1]
    assert created["scenes"][1]["narration_text"] == "The same money buys less."

    reopened = LocalStore(tmp_path / "studio-data")
    loaded = reopened.get_script_plan("plan-1")
    assert loaded["full_script"] == "Inflation reduces purchasing power over time."
    assert [scene["id"] for scene in loaded["scenes"]] == ["scene-1", "scene-2"]
    assert reopened.list_script_plans("project-1")[0]["id"] == "plan-1"


def test_script_plan_update_replaces_scenes_and_profile(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    store.create_project("project-1", "FINOMICS test")
    store.create_script_plan(sample_plan())

    updated = sample_plan()
    updated["title"] = "Inflation, revised"
    updated["output_profile"] = "landscape"
    updated["scenes"] = [dict(updated["scenes"][0], id="scene-3", position=0)]
    result = store.update_script_plan("plan-1", updated)

    assert result["title"] == "Inflation, revised"
    assert result["output_profile"] == "landscape"
    assert len(result["scenes"]) == 1
    assert result["scenes"][0]["id"] == "scene-3"


def test_script_plan_delete_cascades_to_scenes(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    store.create_project("project-1", "FINOMICS test")
    store.create_script_plan(sample_plan())

    assert store.delete_script_plan("plan-1") is True
    assert store.get_script_plan("plan-1") is None
    assert store.delete_script_plan("plan-1") is False


def test_script_plan_rejects_unknown_project(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    plan = sample_plan()
    plan["project_id"] = "missing-project"

    try:
        store.create_script_plan(plan)
    except Exception as exc:
        assert "Project does not exist" in str(exc)
    else:
        raise AssertionError("Expected missing project to be rejected")



def test_scene_image_asset_assignment_persists_across_reopen_and_update(tmp_path):
    store = LocalStore(tmp_path / "studio-data")
    store.create_project("project-1", "FINOMICS test")
    store.register_asset({
        "id": "image-1",
        "project_id": "project-1",
        "original_name": "scene-one.png",
        "stored_name": "image-1.png",
        "media_type": "image/png",
        "size_bytes": 128,
        "sha256": "a" * 64,
    })
    plan = sample_plan()
    plan["scenes"][0]["asset_id"] = "image-1"
    created = store.create_script_plan(plan)
    assert created["scenes"][0]["asset_id"] == "image-1"

    reopened = LocalStore(tmp_path / "studio-data")
    loaded = reopened.get_script_plan("plan-1")
    assert loaded["scenes"][0]["asset_id"] == "image-1"

    updated = sample_plan()
    updated["scenes"][0]["asset_id"] = "image-1"
    result = reopened.update_script_plan("plan-1", updated)
    assert result["scenes"][0]["asset_id"] == "image-1"
