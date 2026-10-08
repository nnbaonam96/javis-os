"""Hook `truoc_tra_loi` (cửa nghe trước): plugin trả lời THAY bot chuyên trách, trước lượt model.

    python tests/run.py truoc_tra_loi      (KHÔNG mạng)

Canh đúng hợp đồng trong plugins_host.fire_truoc_tra_loi:
- plugin trả {"reply": câu} -> khách nhận đúng câu đó, model KHÔNG chạy, Hộp thư có cả tin khách
  lẫn câu bot, hook nhận câu NGUYÊN VĂN + turn của người gửi (không phải chủ).
- plugin trả None / ném lỗi / quá giờ -> model trả lời như chưa có hook (fail-open, bot không im).
- người thật đã Tiếp quản -> hook KHÔNG được hỏi (chốt quyền đứng trước cửa này).
- không plugin nào đăng ký -> không đổi gì.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401  - nạp server/ vào sys.path
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-truoc-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ["JAVIS_ENABLE_USER_PLUGINS"] = "true"
_LOG = Path(_STATE) / "hook-log.jsonl"
os.environ["TRUOC_TEST_LOG"] = str(_LOG)
os.environ["TRUOC_TEST_MODE"] = "reply"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chatbot_runtime  # noqa: E402
import chatbot_store  # noqa: E402
import conversations  # noqa: E402
import plugins_host  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


if _STATE not in str(plugins_host.GLOBAL_DIR):
    print(f"FAIL thư mục plugin không nằm trong thư mục tạm: {plugins_host.GLOBAL_DIR}. DỪNG.")
    sys.exit(1)

BRAIN = Path(tempfile.mkdtemp(prefix="javis-truoc-brain-"))
(BRAIN / "inbox" / "khach").mkdir(parents=True)
_goi_model = []


async def _answer_gia(text, meta=None, progress=None, channel="telegram", bot=None):
    _goi_model.append(text)
    return {"text": "câu của model", "files": []}


chatbot_runtime.wire(answer=_answer_gia, brain_root=lambda b: str(BRAIN),
                     read_agent=lambda b, s: ({"name": "Bống"}, ""))
bid, err = chatbot_store.create_bot({"name": "Bot Bống", "agent_slug": "bong", "brain": str(BRAIN),
                                     "token": "1:x", "channel": "zalo"})
check("tạo được bot test", bool(bid) and not err)
fn = chatbot_runtime._make_answer_fn(bid)
meta = {"chat_id": "77", "chat_type": "private", "user_name": "Lan", "user_id": "77",
        "message_id": 1, "platform": "zalo"}
_so = [1]


def hoi(text):
    _so[0] += 1
    _goi_model.clear()
    if _LOG.exists():
        _LOG.unlink()
    return asyncio.run(fn(text, {**meta, "message_id": _so[0]}))


def nhat_ky():
    if not _LOG.exists():
        return []
    return [json.loads(x) for x in _LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


# 1. Chưa có plugin nào: y như cũ
ra = hoi("chào")
check("không plugin: model trả lời", ra.get("text") == "câu của model" and _goi_model == ["chào"])
check("không plugin: has_reply_hooks False", plugins_host.has_reply_hooks(str(BRAIN)) is False)

# Cài plugin toàn cục có hook. Chế độ đọc từ env lúc GỌI, để một plugin phủ mọi ca.
pdir = Path(plugins_host.GLOBAL_DIR) / "demo-truoc"
pdir.mkdir(parents=True, exist_ok=True)
(pdir / "plugin.yaml").write_text("name: Demo truoc\nslug: demo-truoc\nenabled: true\nmin_mode: readonly\n",
                                  encoding="utf-8")
(pdir / "plugin.py").write_text('''
import asyncio, json, os, time

def _ghi(**kw):
    with open(os.environ["TRUOC_TEST_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"text": kw.get("text"), "turn": kw.get("turn"),
                            "bot_slug": kw.get("bot_slug")}, ensure_ascii=False) + "\\n")

def _dong_bo(**kw):
    _ghi(**kw)
    mode = os.environ["TRUOC_TEST_MODE"]
    if mode == "reply":
        return {"reply": "Hub: " + kw["text"]}
    if mode == "none":
        return None
    if mode == "loi":
        raise RuntimeError("plugin hỏng")
    if mode == "cham":
        time.sleep(1.0)
        return {"reply": "trễ quá"}
    if mode == "rong":
        return {"reply": "   "}
    return None

async def _bat_dong_bo(**kw):
    if os.environ["TRUOC_TEST_MODE"] != "async":
        return None
    await asyncio.sleep(0)
    return {"reply": "async: " + kw["text"]}

def register(ctx):
    ctx.register_hook("truoc_tra_loi", _bat_dong_bo)
    ctx.register_hook("truoc_tra_loi", _dong_bo)
''', encoding="utf-8")
plugins_host.invalidate()
check("có plugin: has_reply_hooks True", plugins_host.has_reply_hooks(str(BRAIN)) is True)

# 2. Plugin trả lời -> model không chạy, câu nguyên văn tới plugin, turn là người gửi
ra = hoi("ăn sáng 35k")
nk = nhat_ky()
check("plugin trả lời: khách nhận đúng câu plugin", ra.get("text") == "Hub: ăn sáng 35k")
check("plugin trả lời: model KHÔNG chạy", _goi_model == [])
check("hook nhận câu NGUYÊN VĂN", len(nk) == 1 and nk[0]["text"] == "ăn sáng 35k")
t = (nk[0]["turn"] if nk else None) or {}
check("turn: sender_id là người gửi, chat riêng, KHÔNG phải chủ",
      t.get("sender_id") == "77" and t.get("chat_type") == "private" and t.get("la_chu") is False)
check("hook nhận bot_slug của bot", nk and nk[0]["bot_slug"] == (chatbot_store.get_bot(bid) or {}).get("slug"))
ds = conversations.danh_sach(bot_id=bid)
tin = conversations.tin_nhan(ds[0]["id"]) if ds else []
check("Hộp thư: tin khách rồi câu plugin (sender ai)",
      len(tin) >= 2 and tin[-2]["sender_type"] == "customer" and tin[-2]["text"] == "ăn sáng 35k"
      and tin[-1]["sender_type"] == "ai" and tin[-1]["text"] == "Hub: ăn sáng 35k")

# 3. Plugin trả None -> model trả lời
os.environ["TRUOC_TEST_MODE"] = "none"
ra = hoi("kể chuyện vui")
check("plugin None: model trả lời", ra.get("text") == "câu của model" and _goi_model == ["kể chuyện vui"])

# 4. Plugin ném lỗi -> model trả lời, bot không im
os.environ["TRUOC_TEST_MODE"] = "loi"
ra = hoi("hỏi gì đó")
check("plugin lỗi: fail-open, model trả lời", ra.get("text") == "câu của model" and len(_goi_model) == 1)

# 5. Plugin trả chuỗi trắng -> coi như không trả lời
os.environ["TRUOC_TEST_MODE"] = "rong"
ra = hoi("câu trắng")
check("reply toàn khoảng trắng: model trả lời", ra.get("text") == "câu của model")

# 6. Plugin quá giờ -> bỏ qua
cu = plugins_host.TRUOC_TRA_LOI_TRAN_S
plugins_host.TRUOC_TRA_LOI_TRAN_S = 0.2
os.environ["TRUOC_TEST_MODE"] = "cham"
ra = hoi("chậm")
plugins_host.TRUOC_TRA_LOI_TRAN_S = cu
check("plugin quá giờ: model trả lời", ra.get("text") == "câu của model" and len(_goi_model) == 1)

# 7. Hook async trả lời được (và đứng trước nên thắng)
os.environ["TRUOC_TEST_MODE"] = "async"
ra = hoi("chạy 5km")
check("hook async: trả lời, model không chạy", ra.get("text") == "async: chạy 5km" and _goi_model == [])

# 8. Người thật tiếp quản -> hook không được hỏi
os.environ["TRUOC_TEST_MODE"] = "reply"
conversations.dat_che_do(ds[0]["id"], "human")
ra = hoi("có ai không")
check("tiếp quản: bot im, hook KHÔNG được hỏi",
      ra.get("im_lang") is True and nhat_ky() == [] and _goi_model == [])
conversations.dat_che_do(ds[0]["id"], "ai")

if _fails:
    print(f"\nFAIL {len(_fails)} ca: {_fails}")
    sys.exit(1)
print("\nOK - test_truoc_tra_loi: tất cả assertion pass")
