"""CR-014 U4 compact span proposer (GLiNER). Standalone: runs in an ephemeral env, reads only section text (never gold), writes spans.

    uv run --no-project --python 3.11 --with gliner python src/cumap/cr014/gliner_proposer.py IN.jsonl OUT.json [threshold]
Proposer only: its output is a candidate source, never a final concept decision."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

MODEL = "urchade/gliner_medium-v2.1"
LABELS = ["concept", "technical term", "protocol", "mechanism", "data structure", "algorithm"]
WINDOW_WORDS = 200


def windows(text: str) -> list[tuple[int, str]]:
    """Consecutive word windows (start char offset, text) that fit the model's ~384-token limit."""
    spans = [m.span() for m in re.finditer(r"\S+", text)]
    out = []
    for i in range(0, len(spans), WINDOW_WORDS):
        a, b = spans[i][0], spans[min(i + WINDOW_WORDS, len(spans)) - 1][1]
        out.append((a, text[a:b]))
    return out


def main() -> None:
    from gliner import GLiNER

    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    t0 = time.time()
    model = GLiNER.from_pretrained(MODEL)
    load_s = time.time() - t0
    t1 = time.time()
    result: dict[str, list[dict]] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        sec = json.loads(line)
        spans = []
        for off, chunk in windows(sec["text"]):
            for e in model.predict_entities(chunk, LABELS, threshold=threshold):
                spans.append(
                    {
                        "surface": e["text"],
                        "start": off + e["start"],
                        "end": off + e["end"],
                        "label": e["label"],
                        "score": round(float(e["score"]), 4),
                    }
                )
        result[sec["section_id"]] = spans
    meta = {
        "model": MODEL,
        "threshold": threshold,
        "labels": LABELS,
        "load_seconds": round(load_s, 1),
        "predict_seconds": round(time.time() - t1, 1),
    }
    dst.write_text(json.dumps({"meta": meta, "sections": result}), encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
