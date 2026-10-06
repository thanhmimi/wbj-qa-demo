# Demo script — 6 phút (Wood Block Journey)

**Thông điệp chính:** "Đây không phải slide. Framework em đề xuất đã chạy thật trên game của Sun.Studio,
không cần source code, sau khoảng một ngày làm."

## 0. Chuẩn bị (trước giờ thuyết trình)
- Mở sẵn: `reports/index.html`, `testcases/WBJ_Test_Analysis.md`, file CSV đã import vào Notion (nếu có).
- Chạy thử 1 lần: `.venv/bin/pytest -m demo -o addopts="" --headed --slowmo 120 -x tests/test_02_tutorial.py`
- Video backup: `.venv/bin/pytest -m demo --video` → `reports/video/*.webm`. Mạng phòng họp yếu thì chiếu video.

## 1. Analysis trước, automation sau (1 phút)
Mở `WBJ_Test_Analysis.md`:
- State model, rules R-01..R-09, ma trận 13 layer × risk.
- "Không có spec, nên rule nào cũng ghi là *observed* và có Q cho GD. Ví dụ Q-03 là công thức điểm."

## 2. Test cases theo schema Notion (30 giây)
- 47 TC: 23 automated, 21 candidate, 3 exploratory charter. Có đủ ads, analytics, persistence, perf, UX, không chỉ UI.

## 3. Live run (2 phút)
```bash
.venv/bin/pytest -o addopts="" --headed --slowmo 120 \
  tests/test_02_tutorial.py::test_complete_tutorial_with_real_drags \
  "tests/test_03_board_rules.py::test_line_and_box_clears[row+column]" \
  tests/test_05_game_over_ads.py::test_play_again_by_image_starts_fresh_game
```
Vừa chạy vừa nói:
- **Tier 1, Bridge:** đọc board dưới dạng FEN, set đúng bàn cờ và 3 quân cần test, thay cho RNG.
- **Tier 2, Scene tree:** kéo thả bằng chuột thật. Driver đọc vị trí quân trong scene graph và tự chỉnh pointer (closed loop), không hard-code pixel.
- **Tier 3, Image:** nút PLAY tìm bằng OpenCV template, đúng kỹ thuật của Airtest. Dùng khi không còn hook nào.
- Oracle là **model luật chơi**, không phải screenshot: "board sau mỗi nước = model".

## 4. Report + Notion (1 phút)
- `python tools/build_report.py` → `reports/index.html`: pass rate, theo tier, theo layer, evidence từng test.
- `python tools/notion_sync.py`: payload Automation Run và cập nhật Last Result cho TC theo TC ID (đang dry-run).

## 5. Bài học, nói thẳng (1 phút)
- Tránh được một false positive: panel YOUR SCORE đếm từ 0 lên → phải assert sau khi animation xong.
- Test hook phải tôn trọng invariant của game: dealer không bao giờ chia 2 quân giống nhau.
- Model bắt lỗi của chính test: quân 3×3 đặt ở (0,0) ăn luôn một box.
- Ads/analytics bị chặn trong test functional, vì random ads làm test flaky và test traffic làm bẩn KPI.
- **Ask:** shim này đang đọc internals của build minified. Trong team, Dev chỉ cần expose `getState / setState(fen) / seed / forceAd` ở build dev/staging. Đó chính là Game Test Bridge trong proposal.

## Câu hỏi có thể gặp
- *"Game Unity / Cocos thì sao?"* → Unity dùng Poco SDK (tier 2) hoặc Airtest (tier 3). Cocos Creator có Poco. Pytest, report và Notion giữ nguyên.
- *"Mất bao lâu để làm cho game khác?"* → bridge.js là phần riêng của từng game. Driver, report và Notion sync dùng lại được. Game Phaser cùng studio thì ước tính 1–2 ngày.
- *"Mobile thì sao?"* → Cùng test, cùng oracle. Thay Playwright bằng Appium (WebView / FB app) hoặc Airtest cho native. Bridge gọi qua JS bridge hoặc deeplink.
