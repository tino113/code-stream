import React, { useMemo, useState } from "react";

export type TimelineMarker = {
  markerId: string;
  timestampMs: number;
  label: string;
};

export type NarrationSegment = {
  segmentId: string;
  markerId?: string;
  text: string;
  durationMs?: number;
  previewClipUrl?: string;
};

type NarrationEditorPanelProps = {
  markers: TimelineMarker[];
  segments: NarrationSegment[];
  onUpdateSegment: (segmentId: string, patch: Partial<NarrationSegment>) => void;
  onRegenerateSegment: (segmentId: string) => Promise<void> | void;
};

export function NarrationEditorPanel({
  markers,
  segments,
  onUpdateSegment,
  onRegenerateSegment,
}: NarrationEditorPanelProps) {
  const markerById = useMemo(() => new Map(markers.map((m) => [m.markerId, m])), [markers]);
  const [pendingSegmentId, setPendingSegmentId] = useState<string | null>(null);

  return (
    <aside className="narration-editor-panel" aria-label="Narration editor panel">
      <h2>Narration Segments</h2>
      {segments.map((segment) => {
        const marker = segment.markerId ? markerById.get(segment.markerId) : undefined;
        const isPending = pendingSegmentId === segment.segmentId;

        return (
          <section key={segment.segmentId} className="narration-segment-row">
            <header>
              <strong>{segment.segmentId}</strong>
              <span>
                {marker ? `${marker.label} (${marker.timestampMs}ms)` : "Unmapped marker"}
              </span>
            </header>

            <textarea
              value={segment.text}
              onChange={(event) =>
                onUpdateSegment(segment.segmentId, { text: event.currentTarget.value })
              }
              aria-label={`Narration text for ${segment.segmentId}`}
            />

            <div className="narration-segment-controls">
              <label>
                Duration (ms)
                <input
                  type="number"
                  min={100}
                  step={50}
                  value={segment.durationMs ?? ""}
                  onChange={(event) =>
                    onUpdateSegment(segment.segmentId, {
                      durationMs: Number(event.currentTarget.value) || undefined,
                    })
                  }
                />
              </label>

              {segment.previewClipUrl ? (
                <audio controls preload="none" src={segment.previewClipUrl}>
                  Your browser does not support audio preview playback.
                </audio>
              ) : (
                <span>No preview clip generated yet.</span>
              )}

              <button
                type="button"
                disabled={isPending}
                onClick={async () => {
                  setPendingSegmentId(segment.segmentId);
                  try {
                    await onRegenerateSegment(segment.segmentId);
                  } finally {
                    setPendingSegmentId(null);
                  }
                }}
              >
                {isPending ? "Regenerating…" : "Regenerate segment"}
              </button>
            </div>
          </section>
        );
      })}
    </aside>
  );
}

export default NarrationEditorPanel;
