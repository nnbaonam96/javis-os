"""Antigravity mang được danh tính của lượt lên hub, mà không lượt nào đọc được mã của lượt khác.

    python tests/python/test_agy_ma_luot.py      (KHÔNG mạng, KHÔNG cần cài agy; chỉ POSIX)

Canh hai đầu của cùng một rủi ro: thiếu mã thì plugin từ chối oan chủ shop trên dashboard, còn mã
rò vào file dùng chung thì lượt của nhân viên có thể gọi công cụ bằng quyền của chủ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-agyluot-")

import antigravity_cli as agy   # noqa: E402
import turn_context   # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


# `agy` giả: ghi lại HOME và mcp_config nó thấy, đọc token qua symlink, rồi làm mới token bằng rename.
AGY_GIA = r"""
import json, os, sys, time
h = os.environ["HOME"]
token = h + "/.gemini/antigravity-cli/antigravity-oauth-token"
with open(sys.argv[1], "w") as f:
    json.dump({"home": h, "cfg": json.load(open(h + "/.gemini/config/mcp_config.json")),
               "token": open(token).read(),
               "duong_cu": os.path.exists(h + "/.gemini/antigravity-cli/mcp_config.json"),
               "khac": os.path.exists(h + "/.config/app.txt")}, f)
time.sleep(float(sys.argv[2]))
if sys.argv[3] == "1":
    open(token + ".new", "w").write("token-moi")
    os.replace(token + ".new", token)
print("xong")
"""


def dung_home(goc: Path, co_hub=True):
    g = goc / ".gemini"
    (g / "config").mkdir(parents=True)
    (g / "antigravity-cli").mkdir()
    (goc / ".config").mkdir()
    (goc / ".config" / "app.txt").write_text("x")
    (g / "antigravity-cli" / "antigravity-oauth-token").write_text("token-cu")
    servers = {"nguoi-dung": {"serverUrl": "http://khac"}}
    if co_hub:
        servers["javis"] = agy.hub_entry("http://hub", {"Authorization": "Bearer h", "X-Javis-Vault": "/home-chung"})
    cfg = json.dumps({"mcpServers": servers})
    (g / "config" / "mcp_config.json").write_text(cfg)
    (g / "antigravity-cli" / "mcp_config.json").write_text(cfg)


def cli_gia(cwd, dump, ngu=0.0, doi_token="0"):
    c = agy.AntigravityCLI(cwd=str(cwd), tag="chat:maluot")
    c.cli_path = sys.executable
    c.timeout = 20
    c._build_args = lambda *a, **kw: [sys.executable, "-c", AGY_GIA, str(dump), str(ngu), doi_token]
    c._chon_duong = lambda full: "argv"
    return c


async def mot_luot(cli, turn, dump):
    """Chạy trọn lượt, giải mã NGAY TRONG lượt vì mã chết khi lượt kết thúc."""
    tok = turn_context.bind(turn)
    try:
        async for _e in cli.query("hoi"):
            pass
        v = json.loads(dump.read_text())
        ma = v["cfg"]["mcpServers"]["javis"]["headers"].get(turn_context.HEADER)
        v["luot"] = turn_context.resolve_key(ma)
        return v
    finally:
        turn_context.reset(tok)


async def tao_trong_luot(turn):
    tok = turn_context.bind(turn)
    try:
        return agy.tao_home_luot()
    finally:
        turn_context.reset(tok)


def main():
    goc = Path(tempfile.mkdtemp(prefix="agyluot-home-"))
    dung_home(goc)
    file_chung = goc / ".gemini" / "config" / "mcp_config.json"
    chung_truoc = file_chung.read_text()
    chu = turn_context.make("dashboard", chat_id="s1", la_chu=True)
    nv = turn_context.make("zalo_personal", "ma-nhan-vien")
    with patch.object(agy, "_home_dir", lambda: goc), patch.dict(os.environ, {"HOME": str(goc)}):
        rieng = goc / "rieng.json"
        rieng.write_text(json.dumps({"mcpServers": {"javis": agy.hub_entry(
            "http://hub", {"Authorization": "Bearer h", "X-Javis-Vault": "/dung-brain"})}}))

        # 1. Lượt của chủ: mã nằm trong file riêng, giải ra đúng lượt có la_chu.
        d1 = goc / "d1.json"
        cli = cli_gia(goc, d1, doi_token="1")
        cli.mcp_config = str(rieng)
        v = asyncio.run(mot_luot(cli, chu, d1))
        check("HOME của lượt khác HOME thật", v["home"] != str(goc))
        check("mã giải ra đúng lượt của chủ", (v["luot"] or {}).get("la_chu") is True, v["luot"])
        check("vault lấy từ file per-brain",
              v["cfg"]["mcpServers"]["javis"]["headers"]["X-Javis-Vault"] == "/dung-brain")
        check("giữ server của người dùng", "nguoi-dung" in v["cfg"]["mcpServers"])
        check("đọc được token qua symlink", v["token"] == "token-cu")
        check("thư mục HOME khác vẫn thấy", v["khac"] is True)
        check("không để lọt mcp_config đường cũ", v["duong_cu"] is False)
        check("file dùng chung không chứa mã", file_chung.read_text() == chung_truoc)
        check("token làm mới được chép về HOME thật",
              (goc / ".gemini/antigravity-cli/antigravity-oauth-token").read_text() == "token-moi")
        check("không còn file tạm cạnh token", not list((goc / ".gemini/antigravity-cli").glob("*.tmp")))
        check("HOME của lượt đã dọn", not Path(v["home"]).exists())
        check("dọn không đụng file thật", (goc / ".config" / "app.txt").read_text() == "x")

        # 2. Hai lượt cùng lúc: mỗi người đúng mã của mình.
        d2, d3 = goc / "d2.json", goc / "d3.json"

        async def song_song():
            return await asyncio.gather(mot_luot(cli_gia(goc, d2, ngu=0.5), chu, d2),
                                        mot_luot(cli_gia(goc, d3, ngu=0.5), nv, d3))
        a, b = asyncio.run(song_song())
        check("hai lượt hai HOME", a["home"] != b["home"])
        check("lượt chủ ra chủ", a["luot"]["la_chu"] is True)
        check("lượt nhân viên ra nhân viên, không phải chủ",
              b["luot"]["sender_id"] == "ma-nhan-vien" and b["luot"]["la_chu"] is False, b["luot"])

        # 3. Không có lượt: không mã, HOME thật.
        check("không có lượt thì không tạo HOME", agy.tao_home_luot() is None)
        d4 = goc / "d4.json"
        v = asyncio.run(mot_luot(cli_gia(goc, d4), None, d4))
        check("không có lượt thì chạy HOME thật", v["home"] == str(goc))
        check("không có lượt thì không có header mã", v["luot"] is None)

        # 4. Lỗi giữa chừng không để lại gì và không chặn lượt.
        with patch.object(agy.os, "symlink", side_effect=OSError("cam")):
            check("lỗi symlink về None", asyncio.run(tao_trong_luot(chu)) is None)
        check("lỗi symlink không để rác", not list(agy._goc_home_luot().glob("luot-*")))

    # 5. Hub tắt: không có entry `javis` thì không tạo gì.
    goc2 = Path(tempfile.mkdtemp(prefix="agyluot-home2-"))
    dung_home(goc2, co_hub=False)
    with patch.object(agy, "_home_dir", lambda: goc2):
        check("hub tắt thì không tạo HOME", asyncio.run(tao_trong_luot(chu)) is None)

    if _fails:
        print(f"FAIL - test_agy_ma_luot: {len(_fails)} assertion hỏng")
        sys.exit(1)
    print("OK - test_agy_ma_luot: tất cả assertion pass")


if __name__ == "__main__":
    if os.name == "nt":
        print("OK - test_agy_ma_luot: bỏ qua trên Windows (không dùng HOME riêng)")
    else:
        main()
