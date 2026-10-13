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


def normalise(task: str, content: str) -> tuple[str, str | None]:
    """HippoRAG's triple parser accepts only a JSON object {"triples": [...]} while its NER parser also accepts a bare list. If the model returned the triples as a bare JSON list (or an empty
    answer), wrap it as the object HippoRAG expects. Same information, no content change; every use is counted and sampled in the shim stats."""
    if task != "cr016_hipporag_triples":
        return content, None
    t = content.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.startswith("json") else t
        t = t.strip()
    try:
        payload = json.loads(t) if t else []
    except json.JSONDecodeError:
        return content, None
    if isinstance(payload, list):
        return json.dumps({"triples": payload}), "bare_list_wrapped"
    if isinstance(payload, dict) and "triples" not in payload:
        named = [v for k, v in payload.items() if "triple" in k.lower() and isinstance(v, list)]
        if len(named) == 1:
            return json.dumps({"triples": named[0]}), "triple_field_renamed"
        lists = [v for v in payload.values() if isinstance(v, list)]
        if lists and not any(lists):
            return json.dumps({"triples": []}), "all_empty_lists"
        if len(lists) == 1:
            return json.dumps({"triples": lists[0]}), "single_list_field_renamed"
    return content, None


def valid(task: str, text: str) -> bool:
    if task == "cr016_hipporag_filter":
        return True
    try:
        p = json.loads(text)
    except json.JSONDecodeError:
        return False
    if task == "cr016_hipporag_triples":
        return isinstance(p, dict) and isinstance(p.get("triples"), list)
    return isinstance(p, list) or (
        isinstance(p, dict) and isinstance(p.get("named_entities"), list)
    )


class Handler(http.server.BaseHTTPRequestHandler):
    def answer(self, task: str, msgs: list, note: str):
        r = self.client.parse(
            task=task,
            prompt_version=PROMPT_VERSION,
            messages=[*msgs, {"role": "system", "content": note}],
            schema=RawTextLLM,
            model_tier="bulk",
            allow_escalation=False,
        )
        out, how = normalise(task, r.output.content)
        if how:
            with self.lock:
                self.stats["normalised"] += 1
                if len(self.stats["normalised_examples"]) < 5:
                    self.stats["normalised_examples"].append(r.output.content[:160])
        return out, {
            "input_tokens": r.usage.get("input_tokens", 0),
            "output_tokens": r.usage.get("output_tokens", 0),
        }

    client: LLMClient
    stats = {"requests": 0, "errors": 0, "normalised": 0, "normalised_examples": []}  # noqa: RUF012
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
            out, u = self.answer(task, msgs, NOTE)
            if not valid(
                task, out
            ):  # one deterministic retry with a validity reminder, then a counted empty fallback
                out2, u2 = self.answer(
                    task,
                    msgs,
                    NOTE + " The answer must be a single valid JSON value and nothing else.",
                )
                with self.lock:
                    self.stats["retried_invalid_json"] = (
                        self.stats.get("retried_invalid_json", 0) + 1
                    )
                u = {k: u.get(k, 0) + u2.get(k, 0) for k in ("input_tokens", "output_tokens")}
                if valid(task, out2):
                    out = out2
                else:
                    with self.lock:
                        self.stats["extraction_failures_empty_fallback"] = (
                            self.stats.get("extraction_failures_empty_fallback", 0) + 1
                        )
                        self.stats.setdefault("unparsed_examples", [])
                        if len(self.stats["unparsed_examples"]) < 5:
                            self.stats["unparsed_examples"].append(out2[:300])
                    out = (
                        json.dumps({"triples": []})
                        if task == "cr016_hipporag_triples"
                        else json.dumps({"named_entities": []})
                    )
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
