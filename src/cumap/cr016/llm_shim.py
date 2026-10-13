"""CR-016: a local OpenAI-compatible chat endpoint that forwards every HippoRAG model call through the project's `LLMClient` (rule 4: Structured Outputs, disk cache keyed by
(model, prompt_version, input hash), call log with tokens, run_id and cost). HippoRAG runs in an isolated environment and only ever talks to this server.

The model is asked for HippoRAG's own text answer through a one-field schema, `{"content": "<answer exactly as the task requests>"}`; HippoRAG's prompts are forwarded unchanged and one
system note is appended to say where the answer goes. Task names separate the cost of OpenIE indexing (ner / triples) from query-time fact filtering (filter).

    uv run python -m cumap.cr016.llm_shim --port 18765 --run-id cr016_s2_hipporag"""

from __future__ import annotations

import argparse
import http.server
import json
import threading
import time

from cumap.concepts_v4.schema import _Strict
from cumap.config import get_settings
from cumap.llm.client import LLMClient

PROMPT_VERSION = "hipporag-d5c83294-shim1"
NOTE = "Return your complete answer, formatted exactly as the task above requests, as the value of the single field `content`."


class RawTextLLM(_Strict):
    content: str


def task_of(system: str) -> str:
    if "extract named entities" in system:
        return "cr016_hipporag_ner"
    if "RDF" in system:
        return "cr016_hipporag_triples"
    return "cr016_hipporag_filter"


class Handler(http.server.BaseHTTPRequestHandler):
    client: LLMClient
    stats = {"requests": 0, "errors": 0}  # noqa: RUF012
    max_usd = 3.5
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def _send(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"stats": self.stats, "spent_usd": round(self.client.spent_usd, 4)})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = [m for m in body.get("messages", []) if m.get("content")]
        system = next((m["content"] for m in msgs if m["role"] == "system"), "")
        task = task_of(system)
        if self.client.spent_usd > self.max_usd:
            self._send(
                429,
                {
                    "error": {
                        "message": f"shim budget ${self.max_usd} exhausted",
                        "type": "insufficient_quota",
                    }
                },
            )
            return
        try:
            r = self.client.parse(
                task=task,
                prompt_version=PROMPT_VERSION,
                messages=[*msgs, {"role": "system", "content": NOTE}],
                schema=RawTextLLM,
                model_tier="bulk",
                allow_escalation=False,
            )
            out = r.output.content
            u = r.usage
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.stats["errors"] += 1
            self._send(
                500,
                {
                    "error": {
                        "message": f"{type(e).__name__}: {str(e)[:200]}",
                        "type": "server_error",
                    }
                },
            )
            return
        with self.lock:
            self.stats["requests"] += 1
        self._send(200, {"id": "shim", "object": "chat.completion", "created": int(time.time()), "model": body.get("model", "shim"), "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": out}}],
                         "usage": {"prompt_tokens": u.get("input_tokens", 0), "completion_tokens": u.get("output_tokens", 0), "total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0)}})  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--run-id", default="cr016_s2_hipporag")
    ap.add_argument("--max-usd", type=float, default=3.5)
    a = ap.parse_args()
    settings = get_settings()
    for t in ("cr016_hipporag_ner", "cr016_hipporag_triples", "cr016_hipporag_filter"):
        settings.llm.max_output_tokens[t] = 6000
    Handler.client = LLMClient(settings, run_id=a.run_id)
    Handler.max_usd = a.max_usd
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"shim listening on {a.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
