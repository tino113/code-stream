from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from enum import Enum
from statistics import mean
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


app = FastAPI(title="Code Stream Analytics")


class EventType(str, Enum):
    RUN_SUCCESS = "run_success"
    ERROR_SYNTAX = "error_syntax"
    ERROR_RUNTIME = "error_runtime"
    ERROR_LOGIC = "error_logic"
    ERROR_TIMEOUT = "error_timeout"
    HINT_OPENED = "hint_opened"
    HINT_APPLIED = "hint_applied"
    CHECKPOINT_RETRY = "checkpoint_retry"


ERROR_TYPES = {
    EventType.ERROR_SYNTAX,
    EventType.ERROR_RUNTIME,
    EventType.ERROR_LOGIC,
    EventType.ERROR_TIMEOUT,
}


class HintStage(str, Enum):
    NONE = "none"
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    FULL_SOLUTION = "full_solution"


class LearningEvent(BaseModel):
    student_id: str
    lesson_id: str
    lesson_segment_id: str
    timeline_marker_id: str
    timestamp: datetime
    event_type: EventType
    concept_tags: List[str] = Field(default_factory=list)
    hint_stage: HintStage = HintStage.NONE
    checkpoint_id: Optional[str] = None
    misconception_cluster: Optional[str] = None


class IngestRequest(BaseModel):
    events: List[LearningEvent]


EVENT_STORE: List[LearningEvent] = []


@app.post("/analytics/events", status_code=201)
def ingest_events(payload: IngestRequest) -> Dict[str, int]:
    EVENT_STORE.extend(payload.events)
    return {"ingested": len(payload.events)}


@app.delete("/analytics/events", status_code=204)
def clear_events() -> None:
    EVENT_STORE.clear()


@app.get("/analytics/taxonomy")
def get_event_taxonomy() -> Dict[str, List[str]]:
    return {
        "run_outcomes": [EventType.RUN_SUCCESS],
        "error_family": sorted(e.value for e in ERROR_TYPES),
        "hint_stages": [stage.value for stage in HintStage],
        "checkpoint_behavior": [EventType.CHECKPOINT_RETRY],
        "concept_tagging": ["concept_tags"],
    }


@app.get("/analytics/confusion-hotspots")
def confusion_hotspots(lesson_id: Optional[str] = None) -> Dict[str, List[Dict[str, object]]]:
    relevant_events = [e for e in EVENT_STORE if lesson_id is None or e.lesson_id == lesson_id]
    if not relevant_events:
        return {"hotspots": []}

    concept_segment_bucket: Dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "errors": 0,
            "runs": 0,
            "hint_usage": 0,
            "checkpoint_retries": 0,
            "timeline_marker_id": None,
        }
    )

    for event in relevant_events:
        if not event.concept_tags:
            continue
        for concept in event.concept_tags:
            bucket = concept_segment_bucket[(concept, event.lesson_segment_id)]
            bucket["timeline_marker_id"] = event.timeline_marker_id
            if event.event_type in ERROR_TYPES:
                bucket["errors"] += 1
            if event.event_type == EventType.RUN_SUCCESS:
                bucket["runs"] += 1
            if event.event_type in {EventType.HINT_OPENED, EventType.HINT_APPLIED}:
                bucket["hint_usage"] += 1
            if event.event_type == EventType.CHECKPOINT_RETRY:
                bucket["checkpoint_retries"] += 1

    hotspots = []
    for (concept, segment), metrics in concept_segment_bucket.items():
        pressure = metrics["errors"] + metrics["hint_usage"] + metrics["checkpoint_retries"]
        denominator = max(1, metrics["runs"])
        hotspots.append(
            {
                "concept": concept,
                "lesson_segment_id": segment,
                "confusion_score": round(pressure / denominator, 2),
                "errors": metrics["errors"],
                "hint_usage": metrics["hint_usage"],
                "checkpoint_retries": metrics["checkpoint_retries"],
                "timeline_marker": {
                    "id": metrics["timeline_marker_id"],
                    "revision_url": f"/teacher/lessons/{lesson_id or 'all'}/segments/{segment}/edit",
                },
            }
        )

    hotspots.sort(key=lambda item: item["confusion_score"], reverse=True)
    return {"hotspots": hotspots}


@app.get("/analytics/teacher-trends")
def teacher_trends(lesson_id: str) -> Dict[str, object]:
    lesson_events = [e for e in EVENT_STORE if e.lesson_id == lesson_id]
    if not lesson_events:
        raise HTTPException(status_code=404, detail="No events found for lesson")

    attempts: Dict[tuple[str, str], List[LearningEvent]] = defaultdict(list)
    for event in lesson_events:
        attempts[(event.student_id, event.lesson_segment_id)].append(event)

    segment_time_to_success: Dict[str, List[float]] = defaultdict(list)
    segment_hint_ratio: Dict[str, List[float]] = defaultdict(list)
    misconception_counts: Dict[str, int] = defaultdict(int)

    for (_, segment), events in attempts.items():
        ordered = sorted(events, key=lambda e: e.timestamp)
        started = ordered[0].timestamp
        success_event = next((e for e in ordered if e.event_type == EventType.RUN_SUCCESS), None)
        if success_event:
            segment_time_to_success[segment].append((success_event.timestamp - started).total_seconds())

        hints = sum(1 for e in ordered if e.event_type in {EventType.HINT_OPENED, EventType.HINT_APPLIED})
        runs = sum(1 for e in ordered if e.event_type == EventType.RUN_SUCCESS)
        if runs:
            segment_hint_ratio[segment].append(hints / runs)

        for event in ordered:
            if event.misconception_cluster and event.event_type in ERROR_TYPES:
                misconception_counts[event.misconception_cluster] += 1

    trend_lines = {
        "time_to_first_success": [
            {
                "lesson_segment_id": segment,
                "seconds": round(mean(values), 2),
            }
            for segment, values in sorted(segment_time_to_success.items())
            if values
        ],
        "hint_dependency_ratio": [
            {
                "lesson_segment_id": segment,
                "ratio": round(mean(values), 2),
            }
            for segment, values in sorted(segment_hint_ratio.items())
            if values
        ],
        "repeated_misconception_clusters": [
            {"cluster": cluster, "count": count}
            for cluster, count in sorted(misconception_counts.items(), key=lambda item: item[1], reverse=True)
            if count > 1
        ],
    }

    timeline_markers = [
        {
            "lesson_segment_id": item["lesson_segment_id"],
            "marker_id": next(
                (
                    e.timeline_marker_id
                    for e in lesson_events
                    if e.lesson_segment_id == item["lesson_segment_id"]
                ),
                None,
            ),
            "recommendation": "Revise explanation and add worked example",
        }
        for item in trend_lines["time_to_first_success"]
        if item["seconds"] > 60
    ]

    return {"lesson_id": lesson_id, "trend_lines": trend_lines, "timeline_markers": timeline_markers}


@app.get("/teacher/analytics", response_class=HTMLResponse)
def teacher_analytics_view() -> str:
    return """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\"/>
    <title>Teacher Analytics</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }
      .panel { border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
      .title { font-size: 18px; margin-bottom: 8px; }
      .metric { margin: 4px 0; }
      .sparkline { height: 10px; background: linear-gradient(90deg, #93c5fd, #2563eb); border-radius: 999px; }
      .marker { background: #fef3c7; border: 1px solid #f59e0b; padding: 8px; border-radius: 6px; margin-top: 6px; }
    </style>
  </head>
  <body>
    <h1>Teacher Analytics Dashboard</h1>
    <div class=\"panel\">
      <div class=\"title\">Trend lines</div>
      <div id=\"trend-lines\"></div>
    </div>
    <div class=\"panel\">
      <div class=\"title\">Timeline revision markers</div>
      <div id=\"timeline-markers\"></div>
    </div>
    <script>
      async function load() {
        const resp = await fetch('/analytics/teacher-trends?lesson_id=lesson-demo');
        if (!resp.ok) {
          document.getElementById('trend-lines').innerText = 'No analytics yet.';
          return;
        }
        const data = await resp.json();
        const trendLines = data.trend_lines;
        const trendsEl = document.getElementById('trend-lines');

        trendLines.time_to_first_success.forEach((point) => {
          const row = document.createElement('div');
          row.className = 'metric';
          row.innerHTML = `<strong>${point.lesson_segment_id}</strong>: ${point.seconds}s to first success <div class=\"sparkline\" style=\"width:${Math.min(100, point.seconds)}%\"></div>`;
          trendsEl.appendChild(row);
        });

        trendLines.hint_dependency_ratio.forEach((point) => {
          const row = document.createElement('div');
          row.className = 'metric';
          row.innerHTML = `<strong>${point.lesson_segment_id}</strong>: hint dependency ${point.ratio}`;
          trendsEl.appendChild(row);
        });

        trendLines.repeated_misconception_clusters.forEach((cluster) => {
          const row = document.createElement('div');
          row.className = 'metric';
          row.textContent = `Cluster ${cluster.cluster}: ${cluster.count} repeats`;
          trendsEl.appendChild(row);
        });

        const markerEl = document.getElementById('timeline-markers');
        data.timeline_markers.forEach((marker) => {
          const div = document.createElement('div');
          div.className = 'marker';
          div.innerHTML = `<strong>${marker.lesson_segment_id}</strong> → marker ${marker.marker_id}<br/>${marker.recommendation}`;
          markerEl.appendChild(div);
        });
      }
      load();
    </script>
  </body>
</html>
    """
