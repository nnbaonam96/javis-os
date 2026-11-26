"""Ari-specific runtime overrides kept out of upstream core files to minimize rebase conflicts."""
from __future__ import annotations

import json
import os
import sys
import time

import aux_engine


def reminder_model_override(engine_tag: str, provider_exists, levels):
    """Return a per-reminder {provider, model, reasoning} override from JAVIS_REMINDER_MODEL_OVERRIDES."""
    if not str(engine_tag or "").startswith("reminder:r_"):
        return None
    raw = os.getenv("JAVIS_REMINDER_MODEL_OVERRIDES")
    if not raw:
        return None
    try:
        overrides = json.loads(raw)
    except ValueError:
        print("[reminders] Invalid JAVIS_REMINDER_MODEL_OVERRIDES JSON", file=sys.stderr)
        return None
    spec = overrides.get(engine_tag) if isinstance(overrides, dict) else None
    if not isinstance(spec, dict):
        return None
    provider, model, reasoning = (spec.get(key) for key in ("provider", "model", "reasoning"))
    if (not isinstance(provider, str) or not provider_exists(provider)
            or not isinstance(model, str) or not model.strip()
            or reasoning not in levels):
        return None
    return {"provider": provider, "model": model.strip(), "reasoning": reasoning}


def aux_swap(cli, *, mode=None, tag=None, codex_profile=None, provider_exists=None, levels=()):
    """Swap a background Claude engine, honoring per-reminder model overrides."""
    engine_tag = str(getattr(cli, "tag", "") or "")
    spec = reminder_model_override(engine_tag, provider_exists, levels) if tag == "reminder" else None
    return aux_engine.swap(cli, mode=mode, tag=engine_tag if spec else tag, spec=spec,
                           codex_profile=codex_profile)


def haravan_read_catalog(conn: dict, default_catalog):
    """Return trusted read-only Haravan catalog metadata when configured for this custom connection."""
    haravan_id = os.getenv("JAVIS_HARAVAN_READ_CONNECTION_ID")
    if haravan_id and conn.get("id") == haravan_id and conn.get("connector_id") == "custom":
        return {"tool_meta": {"read": ["haravan_orders_list", "haravan_transactions_list"]}}
    return default_catalog


async def try_reply_hook(bot_id: str, cfg: dict, text: str, meta: dict, chat_id: str, channel: str,
                         *, brain_root, running: dict, stuck_counts: dict, chatbot_log, record_bot_message):
    """Ask plugin `truoc_tra_loi` hooks before calling the model; return reply dict or None."""
    reply = ""
    try:
        import plugins_host
        import turn_context
        vault = str(brain_root(cfg.get("brain") or "brain"))
        if plugins_host.has_reply_hooks(vault):
            turn_info = turn_context.from_meta(channel, meta, la_chu=False)
            reply = await plugins_host.fire_reply_hooks(vault, {
                "text": text, "turn": turn_info, "bot_id": bot_id, "bot_slug": cfg.get("slug") or ""}) or ""
    except Exception as exc:  # noqa: BLE001 - fail-open so the model still answers
        print(f"[chatbot {bot_id}] truoc_tra_loi: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    if not reply:
        return None
    run = running.get(bot_id)
    if run:
        run["answered"] = run.get("answered", 0) + 1
        run["last_at"] = time.time()
    stuck_counts[(bot_id, chat_id)] = 0
    chatbot_log.ghi(bot_id, {
        "chat_id": chat_id, "chat_type": meta.get("chat_type"), "user_name": meta.get("user_name"),
        "hoi": text, "dap": reply, "loi": "", "co_tai_lieu": False, "nguon": "plugin",
        "chuyen_nguoi": False, "bi": False, "muc_quyen": cfg.get("muc_quyen") or "suggest",
    })
    record_bot_message(cfg, meta, reply)
    return {"text": reply, "files": []}
