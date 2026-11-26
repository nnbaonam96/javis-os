"""Per-turn isolated HOME for Antigravity CLI so each agy process carries its own turn key."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

_TURN_HOME_TTL_S = 24 * 3600


def turn_home_root() -> Path:
    return Path(os.environ.get("JAVIS_STATE_DIR") or Path(__file__).parent) / ".agy_luot"


def _turn_mcp_config(key: str, mcp_home_paths, custom_mcp: Optional[str] = None) -> Optional[dict]:
    """Return HOME mcp_config merged with the current turn key, or None when hub is off."""
    base_cfg: dict = {}
    for p in mcp_home_paths():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(loaded, dict):
            base_cfg = loaded
            break
    servers = base_cfg.get("mcpServers")
    hub = servers.get("javis") if isinstance(servers, dict) else None
    if not isinstance(hub, dict):
        return None
    if custom_mcp:
        try:
            brain_hub = json.loads(Path(custom_mcp).read_text(encoding="utf-8"))["mcpServers"]["javis"]
            if isinstance(brain_hub, dict):
                hub = brain_hub
        except Exception:
            pass
    import turn_context
    hub = {**hub, "headers": {**(hub.get("headers") or {}), turn_context.HEADER: key}}
    return {**base_cfg, "mcpServers": {**servers, "javis": hub}}


def _link_entries(src_dir: Path, target_dir: Path, exclude: frozenset = frozenset()) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    if src_dir.is_dir():
        for entry in src_dir.iterdir():
            if entry.name not in exclude:
                os.symlink(entry, target_dir / entry.name)


def _cleanup_old_homes(root: Path) -> None:
    """Best-effort cleanup for turn homes orphaned by killed processes."""
    try:
        stale = [d for d in root.iterdir() if d.stat().st_mtime < time.time() - _TURN_HOME_TTL_S]
    except OSError:
        return
    for d in stale:
        shutil.rmtree(d, ignore_errors=True)


def make_turn_home(custom_mcp: Optional[str] = None, *, home_dir, mcp_home_paths) -> Optional[str]:
    """Create an isolated per-turn HOME carrying the current turn key, or None to fall back safely."""
    if os.name == "nt":
        return None
    home = None
    try:
        import turn_context
        key = turn_context.issue_key()
        config = _turn_mcp_config(key, mcp_home_paths, custom_mcp) if key else None
        if not config:
            return None
        root = turn_home_root()
        root.mkdir(parents=True, exist_ok=True)
        _cleanup_old_homes(root)
        home = Path(tempfile.mkdtemp(prefix="luot-", dir=root))
        real_home = home_dir()
        _link_entries(real_home, home, frozenset({".gemini"}))
        _link_entries(real_home / ".gemini", home / ".gemini", frozenset({"config", "antigravity-cli"}))
        for subdir in ("config", "antigravity-cli"):
            _link_entries(real_home / ".gemini" / subdir, home / ".gemini" / subdir,
                          frozenset({"mcp_config.json"}))
        cfg_file = home / ".gemini" / "config" / "mcp_config.json"
        cfg_file.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        os.chmod(cfg_file, 0o600)
        return str(home)
    except Exception as exc:
        print(f"[antigravity] failed to build turn HOME: {type(exc).__name__}: {exc}", file=sys.stderr)
        if home:
            shutil.rmtree(home, ignore_errors=True)
        return None


def remove_turn_home(home: Optional[str], *, home_dir) -> None:
    """Sync refreshed auth files back to real HOME and delete the temporary turn HOME."""
    if not home:
        return
    try:
        real_gemini = home_dir() / ".gemini"
        for subdir in ("config", "antigravity-cli"):
            src_sub = Path(home) / ".gemini" / subdir
            if not src_sub.is_dir():
                continue
            for entry in src_sub.iterdir():
                if entry.is_symlink() or entry.name == "mcp_config.json":
                    continue
                target = real_gemini / subdir / entry.name
                if entry.is_dir():
                    if not target.exists():
                        shutil.move(str(entry), str(target))
                    continue
                staged = target.with_name(target.name + f".{uuid.uuid4().hex[:8]}.tmp")
                shutil.copy2(entry, staged)
                os.replace(staged, target)
    except Exception as exc:
        print(f"[antigravity] failed to sync turn HOME files: {type(exc).__name__}: {exc}", file=sys.stderr)
    shutil.rmtree(home, ignore_errors=True)
