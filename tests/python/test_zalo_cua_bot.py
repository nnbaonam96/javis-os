"""Agent khai `zalo_cua_bot: true` -> prompt bot Zalo cá nhân KHÔNG có đoạn "chuyện riêng thì im" (_CAU_ZALO_CA_NHAN).

    python tests/run.py zalo_cua_bot      (KHÔNG mạng)

Lý do: đoạn đó viết cho bot chạy trên Zalo riêng của chủ (câu gửi đi mang tên chủ). Khi tài khoản Zalo là của
chính trợ lý, nó làm bot im cả với câu tán gẫu bình thường ("hôm nay trời nóng quá" -> [IM_LANG]).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-zalo-bot-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chatbot_runtime as cr  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


def prompt(meta, kenh="zalo_personal"):
    cr._deps["read_agent"] = lambda b, s: (meta, "Vai của bot.")
    return cr.build_bot_prompt({"name": "Bot", "agent": {"brain": "b", "slug": "s"}, "_kenh_luot": kenh})


DAU = "Kênh này là Zalo CÁ NHÂN của chủ"
check("Agent không khai: Zalo cá nhân vẫn có đoạn im lặng (hành vi cũ)", DAU in prompt({"name": "Bot"}))
check("Agent khai zalo_cua_bot: true -> bỏ đoạn im lặng", DAU not in prompt({"name": "Bot", "zalo_cua_bot": True}))
check("chuỗi 'true' cũng nhận", DAU not in prompt({"name": "Bot", "zalo_cua_bot": "true"}))
check("false / lạ -> giữ đoạn im lặng", DAU in prompt({"name": "Bot", "zalo_cua_bot": False})
      and DAU in prompt({"name": "Bot", "zalo_cua_bot": "khong"}))
check("kênh khác Zalo cá nhân: không bao giờ có đoạn này", DAU not in prompt({"name": "Bot"}, kenh="telegram"))
check("vai của Agent vẫn còn trong prompt", "Vai của bot." in prompt({"name": "Bot", "zalo_cua_bot": True}))
check("IM_LANG vẫn tồn tại cho các lối khác (nhóm Tự đánh giá)", cr.IM_LANG == "[IM_LANG]")

if _fails:
    print(f"\nFAIL {len(_fails)} ca: {_fails}")
    sys.exit(1)
print("\nOK - test_zalo_cua_bot: tất cả assertion pass")
