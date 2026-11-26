"""Ari's House server-authored FAQ grounding kept out of upstream channels/api.py."""
from __future__ import annotations

import datetime as _datetime
import re
import sys
from typing import Optional
from zoneinfo import ZoneInfo

# Deliberately narrow, server-authored FAQ grounding for Ari's House. These answers are built from
# the two approved source files below, not from model claims or merely from retrieval results.
_ARI_HOUSE_GROUNDING = {
    "rieng-theo-nhom/api-ari-house/thong-tin-ari-co-ban.md": "ari-house/returns",
    "rieng-theo-nhom/api-ari-house/su-kien-uu-dai.md": "ari-house/events",
}


def grounded_faq(turn: dict, cfg: dict, meta: dict) -> Optional[dict]:
    """Build two Ari's House FAQs from approved, scope-matched source files.

    This is deliberately not a general RAG citation feature: retrieval/prompt inclusion and model-authored source
    names are not proof. The response text is constructed here from parsed facts; source IDs are fixed server-side.
    Everything else falls through to the normal chatbot turn with no grounding claim.
    """
    agent = (cfg or {}).get("agent") or {}
    scopes = set(turn.get("scopes") or [])
    if agent.get("slug") != "ari-house" or "ari-house" not in scopes:
        return None

    question = str(turn.get("text") or "").casefold()
    if any(term in question for term in ("đổi trả", "đổi/hoàn", "đổi hoàn", "chính sách đổi", "hoàn hàng")):
        source_path = "rieng-theo-nhom/api-ari-house/thong-tin-ari-co-ban.md"
        source_id = _ARI_HOUSE_GROUNDING[source_path]
        answer_kind = "returns"
    elif any(term in question for term in ("black friday", "blackfriday")):
        source_path = "rieng-theo-nhom/api-ari-house/su-kien-uu-dai.md"
        source_id = _ARI_HOUSE_GROUNDING[source_path]
        answer_kind = "events"
    else:
        return None

    try:
        import chatbot_grounding
        import chatbot_runtime
        root = chatbot_runtime._deps["brain_root"](cfg["brain"])
        docs = chatbot_grounding.scoped_docs(root, chatbot_grounding.scope_of(meta),
                                              chatbot_runtime.bot_doc_files(cfg))
        doc = next((d for d in docs if d.get("path") == source_path), None)
        if not doc:
            return None
        content = str(doc.get("text") or "")
    except Exception as exc:  # fail closed; normal model path remains available
        print(f"[chatbot-api grounding] {type(exc).__name__}", file=sys.stderr)
        return None

    if answer_kind == "returns":
        policy = re.search(r"(?im)^-\s*Đổi\s*/\s*hoàn:\s*(.+)$", content)
        if not policy:
            return None
        terms = policy.group(1)
        days = re.search(r"tiếp nhận trong\s+\*{0,2}(\d+)\s+ngày\*{0,2}\s+từ ngày mua hoặc nhận hàng", terms, re.I)
        exclusion = re.search(r"Đơn mua trực tiếp tại cửa hàng và đơn ưu đãi từ (\d+)% trở lên không áp dụng đổi trả",
                              terms, re.I)
        if (not days or not exclusion or "sản phẩm chưa sử dụng" not in terms.casefold()
                or "còn tag" not in terms.casefold() or "mỗi đơn đổi tối đa 1 lần" not in terms.casefold()):
            return None
        reply = (f"Ari tiếp nhận đổi hoặc hoàn trong {days.group(1)} ngày từ ngày mua hoặc nhận hàng. Sản phẩm cần "
                 "chưa qua sử dụng và còn tag. Mỗi đơn được đổi tối đa 1 lần. Đơn mua trực tiếp tại cửa hàng và "
                 f"đơn ưu đãi từ {exclusion.group(1)}% trở lên không áp dụng đổi trả. "
                 "Với đơn cụ thể, Nàng nhắn Zalo Ari để được kiểm tra nha.")
    else:
        date_match = re.search(r"từ thứ\s+\w+\s+(\d{1,2}/\d{1,2}/\d{4})\s+đến hết\s+(\d{1,2}/\d{1,2}/\d{4})", content, re.I)
        online = re.search(r"^## Online[^\n]*\n([\s\S]*?)(?=^#{1,2} |\Z)", content, re.I | re.M)
        store = re.search(r"^## Tại cửa hàng[^\n]*\n([\s\S]*?)(?=^#{1,2} |\Z)", content, re.I | re.M)
        if not date_match or not online or not store:
            return None
        online_sale = re.search(r"Sale up to\s+(\d+)%", online.group(1), re.I)
        store_sale = re.search(r"Sale up to\s+(\d+)%", store.group(1), re.I)
        voucher = re.search(r"Voucher website các mệnh giá\s+(\d+K(?:,\s*\d+K)*)", online.group(1), re.I)
        ship = re.search(r"Freeship cho đơn từ\s+(\d+K)", online.group(1), re.I)
        if (not online_sale or not store_sale or not voucher or not ship
                or "vòng xoay extra deal" not in store.group(1).casefold()
                or "sample sale" not in store.group(1).casefold()):
            return None
        try:
            starts = _datetime.datetime.strptime(date_match.group(1), "%d/%m/%Y").date()
            ends = _datetime.datetime.strptime(date_match.group(2), "%d/%m/%Y").date()
            today = _datetime.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        except (ValueError, KeyError):
            return None
        if ends < starts:
            return None
        period = f"từ {date_match.group(1)} đến hết {date_match.group(2)}"
        timing = "sắp diễn ra" if today < starts else "đang diễn ra" if today <= ends else "đã kết thúc"
        if today <= ends:
            reply = (f"Black Friday của Ari {timing} {period}. Online có sale đến {online_sale.group(1)}%, "
                     f"voucher {voucher.group(1)} và freeship từ {ship.group(1)}. Tại cửa hàng có sale đến "
                     f"{store_sale.group(1)}%, vòng xoay Extra Deal và sample sale nha.")
        else:
            reply = f"Black Friday của Ari {period} đã kết thúc rồi Nàng nha."

    return {"reply": reply, "grounding": {"kind": "verified-v1", "used_source_ids": [source_id]}}
