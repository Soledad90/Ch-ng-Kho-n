# Checklist Kỷ Luật & Quản Trị Rủi Ro

> In ra dán màn hình. Mỗi lệnh phải đi qua **3 checklist**: Trước vào lệnh — Trong lệnh — Sau lệnh.

---

## A. TRƯỚC KHI VÀO LỆNH (Pre-Trade)

- [ ] Tôi đã xác định **Bias HTF (D1/H4)** rõ ràng, không phải "cảm thấy".
- [ ] Giá hiện tại **đang ở POI** (OB / FVG / Premium-Discount) — không phải giữa vùng "không đất bằng".
- [ ] Có **Liquidity Sweep** ngay trước setup (EQH/EQL, đỉnh/đáy cũ).
- [ ] Có **CHoCH** ở M15/M5 ngược hướng sweep.
- [ ] Confluence Score ≥ **5/8** theo ma trận trong `AGENT.md` Mục 3.
- [ ] Tôi đã tính Entry / SL / TP1 / TP2 **bằng số cụ thể**, không phải "khoảng đó".
- [ ] **RR ≥ 1:2** cho TP cuối.
- [ ] **Size lệnh** tính đúng công thức: `Size = (Risk% × Equity) / (Entry − SL)`. Risk ≤ **1–2%**.
- [ ] Tổng risk đang mở của tôi **< 5%** tài khoản (max 3 lệnh chạy song song).
- [ ] Tôi **không vừa lỗ 3 lệnh liên tiếp** hôm nay. Nếu có → STOP.
- [ ] Tôi **không đang tức giận / phấn khích / buồn ngủ**. Nếu có → tắt máy.
- [ ] Lệnh này **không phải để "gỡ"** lệnh trước đó.
- [ ] Tôi đã viết sẵn **kịch bản vô hiệu** (invalidation) — nếu giá làm gì thì tôi cắt.

> **Nếu bất kỳ ô nào chưa tick → KHÔNG vào lệnh.**

---

## B. TRONG KHI LỆNH CHẠY (In-Trade)

- [ ] SL đã được đặt **lên sàn** (không phải "SL trong đầu").
- [ ] Tôi **không ngồi canh chart** từng nến — đã hẹn giờ review sau X phút/giờ.
- [ ] Khi giá đạt **1R** → dời SL về **Breakeven**. Không sớm hơn, không muộn hơn.
- [ ] Khi giá đạt **TP1** → chốt 50% vị thế (nếu kế hoạch là chia TP).
- [ ] Tôi **không đổi SL xa thêm** vì "tin rằng giá sẽ quay lại".
- [ ] Tôi **không cắt lời sớm** trước TP1 vì "sợ mất lợi nhuận".
- [ ] Nếu cấu trúc HTF **đổi chiều rõ** (CHoCH + BOS trên H4) → tôi thoát lệnh dù chưa chạm SL/TP.

---

## C. SAU LỆNH (Post-Trade)

- [ ] Đã ghi lệnh vào **`templates/TRADE_ANALYSIS_TEMPLATE.csv`** (hoặc journal khác) với đầy đủ: symbol, direction, entry, SL, TP, RR, confluence score, kết quả, cảm xúc.
- [ ] Đã screenshot chart **trước và sau** lệnh.
- [ ] Viết 1–2 câu **lesson learned** (dù thắng hay thua).
- [ ] **Không** vào lệnh tiếp theo ngay vì "đang hên / đang xui". Chờ ít nhất setup tiếp theo **đủ hợp lưu**.

---

## D. NGẮT MẠCH HỆ THỐNG (Circuit Breakers)

| Ngưỡng | Hành động |
|--------|-----------|
| Lỗ **−3% equity** trong 1 ngày | STOP toàn ngày. Không mở chart. |
| Lỗ **−5% equity** trong 1 tuần | STOP toàn tuần. Review lại 20 lệnh gần nhất. |
| **3 lệnh lỗ liên tiếp** | STOP ít nhất 4 tiếng. Uống nước, đi bộ, viết nhật ký. |
| Winrate < **40%** trong 20 lệnh gần nhất | Quay về backtest, không trade tiền thật đến khi winrate > 45% trên demo. |
| Drawdown > **15%** tài khoản | STOP 2 tuần. Review hệ thống, không vào lệnh mới. |

---

## E. NGUYÊN TẮC VỊ THẾ CUỘC SỐNG (Life Position)

- [ ] Số tiền tôi đang trade là **tiền nhàn rỗi** (vốn A) — mất hết cũng không ảnh hưởng sinh hoạt 6 tháng tới.
- [ ] Tôi **không vay** để trade (không margin từ tiền vay, không thẻ tín dụng, không vay bạn bè).
- [ ] Tôi **không kỳ vọng** trading là nguồn thu nhập chính trong 12 tháng đầu.
- [ ] Tôi xem trading là **kỹ năng dài hạn** — đo bằng năm, không đo bằng tuần.
- [ ] Tôi **không khoe lệnh thắng** trên mạng xã hội. Ego là kẻ thù lớn nhất.

---

## F. MẪU NHẬT KÝ NGẮN (Daily Journal — 5 dòng)

```
Ngày: _______
Tâm trạng (1-10): ___   Giấc ngủ (1-10): ___
Lệnh đã vào: ___   Thắng/Thua/BE: ___
Tuân thủ checklist A: Yes / No  →  Nếu No, vi phạm điều nào: ___
Cảm xúc nổi bật hôm nay: ___
Sửa gì cho ngày mai: ___
```

---

*"Thị trường không trả tiền cho người giỏi nhất, thị trường trả tiền cho người kỷ luật nhất."*
