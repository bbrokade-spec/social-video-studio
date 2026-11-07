from app.storage import LocalStore


def test_export_job_lifecycle_and_restart_recovery(tmp_path):
    store = LocalStore(tmp_path / "studio")
    project = store.create_project("project-1", "Test project")
    job = store.create_export_job({
        "id": "job-1",
        "project_id": project["id"],
        "asset_ids": ["asset-1"],
        "profile": "vertical",
        "fps": 30,
    })
    assert job["status"] == "queued"
    assert job["asset_ids"] == ["asset-1"]

    claimed = store.claim_next_export_job()
    assert claimed["id"] == "job-1"
    assert claimed["status"] == "running"
    assert claimed["progress"] == 5

    recovered = LocalStore(tmp_path / "studio")
    assert recovered.recover_interrupted_jobs() == 1
    queued = recovered.get_export_job("job-1")
    assert queued["status"] == "queued"
    assert queued["progress"] == 0

    recovered.claim_next_export_job()
    recovered.update_export_job(
        "job-1", status="completed", progress=100, result_asset_id="asset-result"
    )
    completed = recovered.get_export_job("job-1")
    assert completed["status"] == "completed"
    assert completed["result_asset_id"] == "asset-result"
