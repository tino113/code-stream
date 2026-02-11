from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Voiceover Service")


class EmphasisLevel(str, Enum):
    reduced = "reduced"
    moderate = "moderate"
    strong = "strong"


class PauseStyle(str, Enum):
    silent = "silent"
    breath = "breath"


class EmphasisSpan(BaseModel):
    start: int = Field(ge=0, description="Start character index in the full narration text")
    end: int = Field(gt=0, description="End character index in the full narration text")
    level: EmphasisLevel = EmphasisLevel.moderate

    @field_validator("end")
    @classmethod
    def validate_end(cls, value: int, info):
        start = info.data.get("start")
        if start is not None and value <= start:
            raise ValueError("end must be greater than start")
        return value


class PausePoint(BaseModel):
    index: int = Field(ge=0, description="Character index where pause should be inserted")
    duration_ms: int = Field(ge=50, le=5000)
    style: PauseStyle = PauseStyle.silent


class SpeakingRatePoint(BaseModel):
    index: int = Field(ge=0, description="Character index where this rate starts")
    rate: float = Field(ge=0.5, le=2.0, description="Relative speaking rate")


class SSMLControls(BaseModel):
    emphasis_spans: List[EmphasisSpan] = Field(default_factory=list)
    pause_points: List[PausePoint] = Field(default_factory=list)
    speaking_rate_curve: List[SpeakingRatePoint] = Field(default_factory=list)


class NarrationSegment(BaseModel):
    segment_id: str
    text: str = Field(min_length=1)
    duration_ms: Optional[int] = Field(default=None, ge=100)
    marker_id: Optional[str] = None


DEFAULT_PRONUNCIATION_DICTIONARY: Dict[str, str] = {
    "api": "A P I",
    "ui": "U I",
    "db": "D B",
    "jwt": "J W T",
    "_": "underscore",
    "-": "dash",
    "->": "arrow",
    "==": "equals equals",
    "!=": "not equals",
    "&&": "and and",
    "||": "or or",
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    segments: List[NarrationSegment] = Field(default_factory=list)
    ssml_controls: SSMLControls = Field(default_factory=SSMLControls)
    pronunciation_dictionary: Dict[str, str] = Field(default_factory=dict)


class Marker(BaseModel):
    marker_id: str
    timestamp_ms: int = Field(ge=0)


class AutoSyncNarrationSegment(BaseModel):
    segment_id: str
    text: str = Field(min_length=1)
    duration_ms: int = Field(ge=100)
    marker_id: Optional[str] = None


class AutoSyncRequest(BaseModel):
    timeline_markers: List[Marker] = Field(default_factory=list)
    narration_segments: List[AutoSyncNarrationSegment] = Field(default_factory=list)


class SyncPlanSegment(BaseModel):
    segment_id: str
    marker_id: Optional[str] = None
    start_ms: int
    end_ms: int


def _pronounce_token(token: str, dictionary: Dict[str, str]) -> str:
    lowered = token.lower()
    if lowered in dictionary:
        return dictionary[lowered]

    if "_" in token and token.strip("_"):
        expanded = " underscore ".join(part for part in token.split("_") if part)
        return expanded

    if token.isupper() and len(token) > 1:
        return " ".join(token)

    if all(ch in "_-=!&|>" for ch in token):
        return " ".join(dictionary.get(ch, ch) for ch in token)

    return token


def build_pronunciation_map(text: str, custom_dictionary: Dict[str, str]) -> Dict[str, str]:
    pronunciation_dictionary = {**DEFAULT_PRONUNCIATION_DICTIONARY, **{k.lower(): v for k, v in custom_dictionary.items()}}
    tokens = re.findall(r"[A-Za-z0-9_]+|[-_=!&|>]+", text)
    return {token: _pronounce_token(token, pronunciation_dictionary) for token in tokens}


@app.post("/api/voiceover/tts")
def synthesize_tts(payload: TTSRequest):
    pronunciation_map = build_pronunciation_map(payload.text, payload.pronunciation_dictionary)

    return {
        "text": payload.text,
        "segments": [segment.model_dump() for segment in payload.segments],
        "ssml_controls": payload.ssml_controls.model_dump(),
        "pronunciation_map": pronunciation_map,
        "preview_clip_urls": [
            f"/api/voiceover/preview/{segment.segment_id}.mp3" for segment in payload.segments
        ],
    }


@app.post("/api/voiceover/auto-sync")
def auto_sync(payload: AutoSyncRequest):
    marker_map = {marker.marker_id: marker.timestamp_ms for marker in payload.timeline_markers}

    current_start = min(marker_map.values(), default=0)
    sync_plan: List[SyncPlanSegment] = []
    for segment in payload.narration_segments:
        marker_start = marker_map.get(segment.marker_id)
        if marker_start is not None:
            current_start = marker_start

        segment_plan = SyncPlanSegment(
            segment_id=segment.segment_id,
            marker_id=segment.marker_id,
            start_ms=current_start,
            end_ms=current_start + segment.duration_ms,
        )
        sync_plan.append(segment_plan)
        current_start = segment_plan.end_ms

    return {"sync_plan": [entry.model_dump() for entry in sync_plan]}
