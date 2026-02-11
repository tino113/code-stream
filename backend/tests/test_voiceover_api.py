from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_tts_payload_supports_ssml_controls_and_pronunciation_dictionary():
    payload = {
        "text": "Call my_api and parse JWT with == check",
        "segments": [
            {
                "segment_id": "seg-1",
                "text": "Call my_api",
                "duration_ms": 1200,
                "marker_id": "m1",
            }
        ],
        "ssml_controls": {
            "emphasis_spans": [{"start": 5, "end": 11, "level": "strong"}],
            "pause_points": [{"index": 12, "duration_ms": 300, "style": "breath"}],
            "speaking_rate_curve": [{"index": 0, "rate": 0.9}, {"index": 18, "rate": 1.1}],
        },
        "pronunciation_dictionary": {"my_api": "my A P I"},
    }

    response = client.post("/api/voiceover/tts", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["ssml_controls"]["emphasis_spans"][0]["level"] == "strong"
    assert body["ssml_controls"]["pause_points"][0]["duration_ms"] == 300
    assert body["ssml_controls"]["speaking_rate_curve"][1]["rate"] == 1.1
    assert body["pronunciation_map"]["my_api"] == "my A P I"
    assert body["pronunciation_map"]["JWT"] == "J W T"
    assert body["preview_clip_urls"] == ["/api/voiceover/preview/seg-1.mp3"]


def test_auto_sync_builds_segment_level_plan_from_durations_and_markers():
    payload = {
        "timeline_markers": [
            {"marker_id": "m1", "timestamp_ms": 500},
            {"marker_id": "m2", "timestamp_ms": 3000},
        ],
        "narration_segments": [
            {"segment_id": "seg-1", "text": "Intro", "duration_ms": 1200, "marker_id": "m1"},
            {"segment_id": "seg-2", "text": "Middle", "duration_ms": 900},
            {"segment_id": "seg-3", "text": "Transition", "duration_ms": 1500, "marker_id": "m2"},
        ],
    }

    response = client.post("/api/voiceover/auto-sync", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["sync_plan"] == [
        {"segment_id": "seg-1", "marker_id": "m1", "start_ms": 500, "end_ms": 1700},
        {"segment_id": "seg-2", "marker_id": None, "start_ms": 1700, "end_ms": 2600},
        {"segment_id": "seg-3", "marker_id": "m2", "start_ms": 3000, "end_ms": 4500},
    ]


def test_auto_sync_requires_segment_duration():
    payload = {
        "timeline_markers": [{"marker_id": "m1", "timestamp_ms": 500}],
        "narration_segments": [
            {"segment_id": "seg-1", "text": "Intro", "marker_id": "m1"},
        ],
    }

    response = client.post("/api/voiceover/auto-sync", json=payload)

    assert response.status_code == 422
