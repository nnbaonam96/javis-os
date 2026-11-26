# javis-os-bong - Fork Ari cua Javis OS

> Khong sua `CLAUDE.md` (day la system prompt chay that cua Javis). Khi fix build do hoac update VPS, dung dung repo nay (`ari-main`), khong sua trong `D:\PROJECTS\_LAB\javis-os`.

## Ban do phien
| Can | File |
|---|---|
| Trang thai song - mo phien doc | `gh issue list -R nnbaonam96/javis-os -l ari-build-do` · `docs/ari-update-runbook.md` |
| Quyet dinh & runbook VPS | `D:\PROJECTS\_LAB\javis-os-ari\RUNBOOK-build-do.md` · `D:\PROJECTS\ARI\_TOOLS\ARI_Javis_SoTay.md` |
| Viec chua lam | `gh run list -R nnbaonam96/javis-os -L 5` |
| Ghi nhat ky khi xong viec | Commit tren `ari-main` · cap nhat `D:\PROJECTS\_LAB\javis-os-ari\RUNBOOK-build-do.md` neu doi quy trinh |
| Khong doc tru khi duoc yeu cau | `D:\PROJECTS\_LAB\javis-os` (ban cu, chi dung `.venv`) · `D:\PROJECTS\_LAB\_javis-cu` · `D:\PROJECTS\_LAB\javis-tailieu` |

## Tu lam / Phai hoi
- **Tu lam:** Doc log CI, kiem tra test bang `D:\PROJECTS\_LAB\javis-os\.venv\Scripts\python.exe tests/run.py ...`, rebase thu trong worktree tam, kiem tra trang thai container VPS chi doc.
- **Phai hoi truoc:** Force-push len `fork/ari-main`, thay doi `/usr/local/bin/ari-build-dispatch` hoac `/docker/javis-os` tren VPS, xoa/sua du lieu production trong `/data/`.

## Quy tac ky thuat bat buoc
- Tai khoan `gh`: luon la `nnbaonam96` (`gh auth switch -u nnbaonam96`). Khong bao gio push ve `origin` (`blogminhquy/javis-os`).
- Giu code Ari trong module rieng (`server/ari_overrides.py`, `server/ari_house_grounding.py`, `server/ari_antigravity_turn.py`), chi de moc 3-10 dong o file goc.
- Ten ham, bien, tham so moi trong `server/`, `tools/`, `cli/` phai dung **tieng Anh** (`test_english_identifiers.py`).
- Truoc khi push: giu working tree sach (neu khong `keo-ve.ps1` se bao lech) va chay it nhat `test_ignore_files.py`, `test_english_identifiers.py`, `test_ari_reminder_haravan.py`, `test_truoc_tra_loi.py`, `test_agy_ma_luot.py`, `test_chatbot_api_channel.py`.
