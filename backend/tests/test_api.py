"""End-to-end API tests (inline jobs, mock providers)."""
from __future__ import annotations


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ok"
    assert body["status"] in ("ok", "degraded")


def test_provider_settings_visible(client):
    resp = client.get("/api/v1/settings/providers")
    assert resp.status_code == 200
    providers = {p["name"]: p for p in resp.json()}
    assert set(providers) == {"asr", "llm", "translation"}
    for p in providers.values():
        assert p["mode"] == "mock"
        assert p["detail"]


def test_app_settings_and_languages(client):
    resp = client.get("/api/v1/settings")
    body = resp.json()
    keys = {l["key"] for l in body["languages"]}
    assert keys == {"en", "hi", "kn", "ta", "te", "ml"}
    assert body["limits"]["max_upload_bytes"] > 0


def test_full_upload_to_results_flow(client, upload_lecture):
    result = upload_lecture(title="OS Basics", source="kn", target="hi",
                            translate=True)
    lecture, job = result["lecture"], result["job"]
    assert job["status"] == "COMPLETED"
    assert job["progress"] == 1.0
    assert lecture["status"] == "COMPLETED"
    lid = lecture["id"]

    # stages reflect actual work
    stages = job["stages"]
    assert stages[0] == "QUEUED"
    assert "TRANSLATING_INPUT" in stages
    assert "TRANSLATING_OUTPUT" in stages
    assert stages[-1] == "COMPLETED"

    # transcript
    tr = client.get(f"/api/v1/lectures/{lid}/transcript").json()
    assert tr["language"] == "kn"
    assert tr["is_mock"] is True
    assert tr["segments"]
    assert tr["segments"][0]["segment_index"] == 1
    assert tr["segments"][0]["start_time"] >= 0
    assert client.get(f"/api/v1/lectures/{lid}/audio").status_code == 200

    # notes (canonical English)
    notes = client.get(f"/api/v1/lectures/{lid}/notes").json()
    assert notes["language"] == "en"
    content = notes["content"]
    assert content["title"] == "OS Basics"
    assert len(content["sections"]) >= 1
    for s in content["sections"]:
        assert s["source_segments"]

    # quiz: exactly 5
    quiz = client.get(f"/api/v1/lectures/{lid}/quiz").json()
    assert len(quiz["questions"]) == 5
    for q in quiz["questions"]:
        assert len(q["options"]) == 4
        assert q["correct_option"] in ("A", "B", "C", "D")
        assert q["explanation"]
        assert q["source_segments"]

    # attempt
    answers = {q["id"]: q["options"][0]["id"] for q in quiz["questions"]}
    attempt = client.post(f"/api/v1/lectures/{lid}/quiz/attempt",
                          json={"answers": answers})
    assert attempt.status_code == 201
    body = attempt.json()
    assert body["total_questions"] == 5
    assert 0 <= body["score"] <= 5

    # cached translation for notes in target language
    notes_hi = client.get(f"/api/v1/lectures/{lid}/notes",
                          params={"language": "hi"}).json()
    assert notes_hi["language"] == "hi"
    quiz_hi = client.get(f"/api/v1/lectures/{lid}/quiz",
                         params={"language": "hi"}).json()
    assert quiz_hi["language"] == "hi"
    # structural IDs unchanged after translation
    assert [q["id"] for q in quiz_hi["questions"]] == \
           [q["id"] for q in quiz["questions"]]
    assert [q["correct_option"] for q in quiz_hi["questions"]] == \
           [q["correct_option"] for q in quiz["questions"]]

    # export
    export = client.get(f"/api/v1/lectures/{lid}/export",
                        params={"format": "markdown"})
    assert export.status_code == 200
    assert "OS Basics" in export.text
    transcript_export = client.get(
        f"/api/v1/lectures/{lid}/export", params={"format": "transcript"})
    assert transcript_export.status_code == 200
    assert "Transcript" in transcript_export.text

    # detail endpoint reflects capabilities
    detail = client.get(f"/api/v1/lectures/{lid}").json()
    assert detail["has_transcript"] and detail["has_notes"] and detail["has_quiz"]
    assert "hi" in detail["available_translation_languages"]

    # delete
    assert client.delete(f"/api/v1/lectures/{lid}").status_code == 204
    assert client.get(f"/api/v1/lectures/{lid}").status_code == 404


def test_upload_rejects_non_audio(client):
    resp = client.post(
        "/api/v1/lectures",
        data={"title": "Bad", "source_language": "en"},
        files={"audio": ("notes.wav", b"not audio at all", "audio/wav")},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] in ("unsupported_media", "audio_error")


def test_upload_rejects_bad_extension(client, demo_wav_bytes):
    resp = client.post(
        "/api/v1/lectures",
        data={"title": "Bad ext", "source_language": "en"},
        files={"audio": ("lecture.exe", demo_wav_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_upload_rejects_unsupported_language(client, demo_wav_bytes):
    resp = client.post(
        "/api/v1/lectures",
        data={"title": "Bad lang", "source_language": "xx"},
        files={"audio": ("a.wav", demo_wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 422


def test_translation_requires_target_language(client, demo_wav_bytes):
    # translate_content without a target language must be rejected
    resp = client.post(
        "/api/v1/lectures",
        data={"title": "T2", "source_language": "en",
              "translate_content": "true"},
        files={"audio": ("a.wav", demo_wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_translate_endpoint_queues_and_caches(client, upload_lecture):
    result = upload_lecture(title="Lang Switch", source="en")
    lid = result["lecture"]["id"]
    assert result["job"]["status"] == "COMPLETED"

    resp = client.post(f"/api/v1/lectures/{lid}/translate",
                       json={"content_types": ["notes", "quiz"],
                             "language": "ta"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["kind"] == "TRANSLATION"

    notes_ta = client.get(f"/api/v1/lectures/{lid}/notes",
                          params={"language": "ta"}).json()
    assert notes_ta["language"] == "ta"
    # requesting again hits cache (still fine)
    resp2 = client.post(f"/api/v1/lectures/{lid}/translate",
                        json={"content_types": ["notes"], "language": "ta"})
    assert resp2.status_code == 202


def test_quiz_attempt_rejects_unknown_questions(client, upload_lecture):
    lid = upload_lecture()["lecture"]["id"]
    resp = client.post(f"/api/v1/lectures/{lid}/quiz/attempt",
                       json={"answers": {"question-99": "A"}})
    assert resp.status_code == 422


def test_quiz_attempt_rejects_bad_option(client, upload_lecture):
    lid = upload_lecture()["lecture"]["id"]
    resp = client.post(f"/api/v1/lectures/{lid}/quiz/attempt",
                       json={"answers": {"question-1": "Z"}})
    assert resp.status_code == 422


def test_list_lectures_and_404s(client, upload_lecture):
    lid = upload_lecture()["lecture"]["id"]
    listing = client.get("/api/v1/lectures").json()
    assert any(l["id"] == lid for l in listing)
    assert client.get("/api/v1/lectures/nope").status_code == 404
    assert client.get("/api/v1/jobs/nope").status_code == 404
    assert client.get(f"/api/v1/lectures/{lid}/transcript").status_code == 200


def test_failed_job_is_marked_failed(client, demo_wav_bytes, monkeypatch):
    """A pipeline failure must surface as FAILED with a readable message."""
    from app.services import pipeline as pipeline_mod

    def boom(*_args, **_kwargs):
        from app.core.errors import ModelLoadError
        raise ModelLoadError(
            "IndicConformer checkpoint not configured. Set "
            "INDICCONFORMER_CHECKPOINT=... or use ASR_PROVIDER=mock.")

    monkeypatch.setattr(pipeline_mod, "get_asr_provider", boom)
    # create a lecture directly (bypasses the API so we can force the failure)
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.entities import Job, JobKind, JobStatus, Lecture, LectureStatus

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    wav = settings.uploads_dir / "fail_case.wav"
    wav.write_bytes(demo_wav_bytes)
    db = SessionLocal()
    lecture = Lecture(title="Fail case",
                      audio_path=str(wav.relative_to(settings.storage_root)),
                      audio_original_name="fail_case.wav",
                      source_language="en", status=LectureStatus.QUEUED)
    db.add(lecture)
    db.flush()
    job = Job(lecture_id=lecture.id, kind=JobKind.PROCESSING,
              status=JobStatus.QUEUED, current_stage=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    lid, jid = lecture.id, job.id
    db.close()

    import pytest
    from app.core.errors import ModelLoadError
    with pytest.raises(ModelLoadError):
        pipeline_mod.run_processing_pipeline(lid)

    db = SessionLocal()
    job = db.get(Job, jid)
    lecture = db.get(Lecture, lid)
    assert job.status == JobStatus.FAILED
    assert "INDICCONFORMER_CHECKPOINT" in job.error_message
    assert lecture.status == LectureStatus.FAILED
    db.delete(lecture)  # cascade cleans job
    db.commit()
    db.close()
