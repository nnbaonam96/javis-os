"""Ari patches: per-reminder model override (with its effort) and the trusted Haravan reads.

    python tests/python/test_ari_reminder_haravan.py      (no network)
"""
from _paths import ROOT, SERVER  # noqa: F401
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-ari-")

import aux_engine   # noqa: E402
import main   # noqa: E402
import mcp_catalog   # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


SPEC = {"provider": aux_engine.CODEX, "model": "gpt-x", "reasoning": "medium"}


def override(raw, tag):
    with patch.dict(os.environ, {"JAVIS_REMINDER_MODEL_OVERRIDES": raw}):
        return main._reminder_model_override(tag)


check("configured reminder", override(json.dumps({"reminder:r_1": SPEC}), "reminder:r_1") == SPEC)
check("other reminder", override(json.dumps({"reminder:r_1": SPEC}), "reminder:r_2") is None)
check("not a reminder", override(json.dumps({"chat:1": SPEC}), "chat:1") is None)
check("bad JSON", override("{", "reminder:r_1") is None)
check("bad effort", override(json.dumps({"reminder:r_1": {**SPEC, "reasoning": "x"}}), "reminder:r_1") is None)


def swap_args(raw, aux_tag):
    with patch.dict(os.environ, {"JAVIS_REMINDER_MODEL_OVERRIDES": raw}), \
            patch.object(main.aux_engine, "swap", side_effect=lambda cli, **kw: kw):
        return main._aux_swap(SimpleNamespace(tag="reminder:r_1"), tag=aux_tag)


raw = json.dumps({"reminder:r_1": SPEC})
kw = swap_args(raw, "reminder")
check("override reaches the engine", kw["spec"] == SPEC and kw["tag"] == "reminder:r_1")
check("other background work untouched", swap_args(raw, "loop")["spec"] is None)


def codex_config(tag):
    engine = SimpleNamespace(extra_config=[])
    with patch.object(aux_engine, "availability", lambda *a, **k: (True, "")), \n            patch.object(aux_engine, "_build_codex", lambda *a, **k: engine), \
            patch.object(aux_engine, "_per_account", lambda prov, first, settings, build: [first]):
        links = aux_engine._links_for_step(SPEC, SimpleNamespace(), "suggest", tag, None, {}, None)
    return engine.extra_config if links else None


check("reminder effort is sent", codex_config("reminder:r_1") == ["model_reasoning_effort=medium"])
check("other tags keep their own effort", codex_config("loop") == [])

conn = {"id": "c1", "connector_id": "custom"}
with patch.dict(os.environ, {"JAVIS_HARAVAN_READ_CONNECTION_ID": "c1"}):
    cat = mcp_catalog.for_connection(conn)
    check("trusted read", mcp_catalog.classify(cat, "haravan_orders_list", {}) == "read")
    check("other connection", mcp_catalog.for_connection({**conn, "id": "c2"}) == mcp_catalog.get("custom"))
    check("a write stays a write", mcp_catalog.classify(cat, "haravan_orders_create", {}) != "read")
with patch.dict(os.environ):
    os.environ.pop("JAVIS_HARAVAN_READ_CONNECTION_ID", None)
    check("off by default", mcp_catalog.for_connection(conn) == mcp_catalog.get("custom"))

sys.exit(1 if _fails else 0)
