# Ari: xử lý Javis không cập nhật

## Luồng hiện tại

Cron VPS (`/usr/local/bin/ari-build-dispatch`) gọi `ari-build.yml` trên `nnbaonam96/javis-os`, nhánh `ari-main` khi nguồn đổi (và tự dừng không spam khi đang có issue `ari-build-do` mở trên cùng SHA `ari-main`).
Workflow tách bản vá Ari vào module riêng (`server/ari_overrides.py`, `server/ari_house_grounding.py`, `server/ari_antigravity_turn.py`, móc tối thiểu ở `main.py` / `channels/api.py` / `antigravity_cli.py` / `chatbot_runtime.py`), chồng lên `main` gốc, chạy 4 shard `tests/run.py` cô lập + `common`, rồi xuất image GHCR.
Test/build đỏ thì không xuất image; VPS giữ bản đang chạy.

## Chẩn đoán nhanh

1. `gh auth status`: tài khoản ghi fork là `nnbaonam96`.
2. `gh run list -R nnbaonam96/javis-os -L 5`.
3. Lưu log ra tệp thay vì đổ toàn bộ ra màn hình:
   `gh run view RUN_ID -R nnbaonam96/javis-os --log-failed > build-failed.log`.
   Tìm `FAIL`, `CHẠY LẠI MỘT MÌNH`, `error`, và tên bước lỗi.
4. Xung đột rebase: giữ cả thay đổi gốc và ý nghĩa bản vá Ari.
   Test đỏ: kiểm tra test chạy riêng và CI gốc ở cùng upstream SHA.
   Build/push đỏ: xem log Docker/GHCR, không sửa test để vượt qua.
5. Nguồn từng đỏ được cache. Sau khi sửa, push tạo nguồn mới; nếu chỉ thử lại
   cùng nguồn dùng `gh workflow run ari-build.yml -R nnbaonam96/javis-os --ref ari-main -f force=true`.

## Những lỗi đã gặp và cách ngăn

- 09/11/2026: thiếu ignore `server/.auth_stamp.json`.
- 17/11/2026: thiếu ignore `server/turn_ledger.sqlite3`, khiến test an toàn đỏ,
  image không được xuất bản và VPS dừng ở 0.576.0. Đã lên 0.584.0, run 44104905423 xanh.
- SQLite vận hành ngay dưới `server/` được loại bằng `server/*.sqlite3*` ở Git
  và Docker, gồm WAL/SHM. Không dùng quy tắc rộng cho mọi JSON hoặc mọi thư mục.
- `test_ignore_files.py` chạy riêng trước và sau toàn bộ test, tránh kiểm tra trạng thái
  Git trong lúc test khác đang ghi; lỗi đã có sẵn được phát hiện trước bộ test dài.
- Bước import main dùng `JAVIS_STATE_DIR` tạm ngoài checkout.
- Chưa ép toàn bộ test dùng state dir mới: nhiều test có giả định riêng về đường dẫn.
  Nếu tách tiếp, phải kiểm chứng toàn bộ suite; không xoá artifact trước kiểm tra để che lỗi.

## Xác nhận sau sửa

- `python tests/python/test_ignore_files.py` và `git diff --check`.
- Bản mới phải qua đầy đủ test và build; không bỏ chốt để cập nhật nhanh.
- Khi image đã xuất bản, trên VPS chạy:
  `ssh javis 'cd /docker/javis-os && docker compose pull javis && docker compose up -d javis'`.
- Xác nhận `/app/VERSION`, container healthy, và `https://javis.callmeari.vn` trả HTTP 200.
- Nếu phát hành gây lỗi, chọn image tag phiên bản trước; không xoá volume dữ liệu.

Issue `ari-build-do` được workflow mở khi đỏ và đóng khi có image xanh.
Issue đóng chỉ chứng minh image đã xuất bản; vẫn cần kiểm tra VPS đã nhận bản mới.
