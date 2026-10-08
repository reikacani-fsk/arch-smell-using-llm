"""LLM clients and the run log (every call is stored, so every number in the thesis is reproducible)."""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, run_id TEXT, project TEXT, release TEXT,
  package TEXT, config TEXT, model TEXT, repeat INTEGER, prompt_hash TEXT,
  system TEXT, user_msg TEXT, raw TEXT, parsed_ok INTEGER, error TEXT,
  input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER,
  latency_s REAL);
CREATE TABLE IF NOT EXISTS predictions (
  call_id INTEGER, run_id TEXT, project TEXT, release TEXT, package TEXT, config TEXT, model TEXT,
  repeat INTEGER, smell TEXT, present INTEGER, evidence TEXT);
"""


class ClaudeClient:
    """Claude Messages API with structured outputs and a cached system prompt."""

    def __init__(self, model, max_tokens=4000, temperature=0, client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY
        self.client, self.model = client, model
        self.max_tokens, self.temperature = max_tokens, temperature

    def complete(self, system: str, user: str, schema: dict):
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            # identical for every call -> prompt caching makes repeated calls cheaper
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        u = resp.usage
        usage = {"input_tokens": getattr(u, "input_tokens", None),
                 "output_tokens": getattr(u, "output_tokens", None),
                 "cache_read_tokens": getattr(u, "cache_read_input_tokens", None),
                 "cache_write_tokens": getattr(u, "cache_creation_input_tokens", None)}
        return text, usage


class DryRunClient:
    """Offline stand-in for pipeline testing: answers 'no smell' for everything, never calls an API."""
    model = "dry-run"

    def complete(self, system, user, schema):
        smells = schema["properties"]["smells"]["items"]["properties"]["smell"]["enum"]
        pkg = user.split("\n", 1)[0].replace("Target package:", "").strip()
        out = {"package": pkg, "smells": [{"smell": s, "present": False, "evidence": "dry-run"} for s in smells]}
        return json.dumps(out), {"input_tokens": len(system + user) // 4, "output_tokens": 50,
                                 "cache_read_tokens": 0, "cache_write_tokens": 0}


class RunLog:
    def __init__(self, path: Path):
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA_SQL)

    def record(self, meta: dict, system, user, phash, call):
        """Execute `call()` -> (text, usage), store raw + parsed result. Returns parsed dict or None."""
        t0, text, usage, parsed, err = time.time(), None, {}, None, None
        try:
            text, usage = call()
            parsed = json.loads(text)
        except Exception as e:  # keep failures in the log; they are data too
            err = f"{type(e).__name__}: {e}"
        cur = self.con.execute(
            "INSERT INTO calls (ts, run_id, project, release, package, config, model, repeat, prompt_hash,"
            " system, user_msg, raw, parsed_ok, error, input_tokens, output_tokens, cache_read_tokens,"
            " cache_write_tokens, latency_s) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), meta["run_id"], meta["project"], meta["release"],
             meta["package"], meta["config"], meta["model"], meta["repeat"], phash, system, user, text,
             int(parsed is not None), err, usage.get("input_tokens"), usage.get("output_tokens"),
             usage.get("cache_read_tokens"), usage.get("cache_write_tokens"), round(time.time() - t0, 2)))
        if parsed:
            for s in parsed.get("smells", []):
                self.con.execute(
                    "INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (cur.lastrowid, meta["run_id"], meta["project"], meta["release"], meta["package"],
                     meta["config"], meta["model"], meta["repeat"], s["smell"], int(bool(s["present"])),
                     s.get("evidence", "")))
        self.con.commit()
        return parsed, err
