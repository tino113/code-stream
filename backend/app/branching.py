from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional


def _event_lookup(recording: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {event["id"]: event for event in recording.get("events", [])}


def resolve_branch_path(
    recording: Dict[str, Any],
    *,
    branch_name: str = "main",
    terminal_event_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Resolve a deterministic event replay path for a branch.

    The path includes ancestor events from parent branches through the
    selected branch tip. If terminal_event_id is provided, replay stops there.
    """

    branches = recording.get("branch_events", {})
    if branch_name not in branches:
        raise ValueError(f"Unknown branch: {branch_name}")

    events_by_id = _event_lookup(recording)
    branch_parents = recording.get("branch_parents", {})

    # Build branch lineage from root -> selected branch.
    lineage = []
    current = branch_name
    seen = set()
    while current:
        if current in seen:
            raise ValueError("Branch cycle detected")
        seen.add(current)
        lineage.append(current)
        current = branch_parents.get(current)
    lineage.reverse()

    replay_ids: List[str] = []
    for name in lineage:
        for event_id in branches.get(name, []):
            if event_id not in replay_ids:
                replay_ids.append(event_id)
            if terminal_event_id and event_id == terminal_event_id:
                return [events_by_id[eid] for eid in replay_ids if eid in events_by_id]

    return [events_by_id[eid] for eid in replay_ids if eid in events_by_id]


def branch_event_index(recording: Dict[str, Any]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for branch_name, event_ids in recording.get("branch_events", {}).items():
        for event_id in event_ids:
            index[event_id] = branch_name
    return index


def materialize_branch_events(events: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for event in events:
        grouped[event.get("branch_name", "main")].append(event["id"])
    return dict(grouped)
