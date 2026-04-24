# Phân Tích Kỹ Thuật — Chi tiết phương pháp

> Tài liệu hỗ trợ `AGENT.md`. Mọi khái niệm bên dưới là "từ điển" Agent sử dụng. Khi phân tích, Agent chỉ được dùng những khái niệm nằm trong đây — tránh nhiễu bởi chỉ báo "thần thánh" ngoài hệ thống.

---

## 1. Cấu Trúc Thị Trường (Market Structure)

### 1.1 Phân loại đỉnh đáy
- **STL / STH** (Short-Term Low/High): đỉnh/đáy có 3 nến xác nhận bên trái và phải.
- **ITL / ITH** (Intermediate-Term): STL/STH bao quanh bởi các STL/STH thấp/cao hơn.
- **LTL / LTH** (Long-Term): ITL/ITH bao quanh bởi các ITL/ITH thấp/cao hơn.

### 1.2 BOS — Break of Structure
- Xu hướng tăng: giá đóng cửa **> LTH** gần nhất → xác nhận trend tiếp diễn.
- Xu hướng giảm: giá đóng cửa **< LTL** gần nhất → xác nhận trend tiếp diễn.

### 1.3 CHoCH — Change of Character
- Tín hiệu **đầu tiên** của đảo chiều. Giá phá cấu trúc ngược với xu hướng đang chạy.
- CHoCH ở LTF (M5/M15) **không đủ** để đảo bias HTF. Cần thêm BOS xác nhận ở H1/H4.

### 1.4 Strong vs Weak High/Low
- **Strong High**: đỉnh tạo ra một đáy phá cấu trúc (BOS giảm).
- **Weak High**: đỉnh không tạo BOS → nhiều khả năng bị quét trước khi đảo chiều thật.
- Quy tắc: **Sell tại Strong High, Buy tại Strong Low**.

---

## 2. Smart Money Concepts (SMC / ICT)

### 2.1 Order Block (OB)
- Nến giảm cuối cùng trước một cú tăng mạnh (Bullish OB) hoặc ngược lại (Bearish OB).
- **OB hợp lệ** khi: (a) phá cấu trúc sau khi hình thành, (b) chưa bị mitigate (giá chưa quay lại lấp đầy).
- Entry: giá quay lại chạm 50%–100% body của OB.

### 2.2 Fair Value Gap (FVG) / Imbalance
- Khoảng trống 3 nến: râu nến 1 và râu nến 3 không chạm nhau.
- Giá có xu hướng **quay lại lấp FVG** ít nhất 50%.
- FVG cùng chiều với Bias HTF → POI mạnh.

### 2.3 Liquidity
- **Buy-side Liquidity (BSL)**: phía trên đỉnh cũ (nơi SL của Short + Buy Stop nằm).
- **Sell-side Liquidity (SSL)**: phía dưới đáy cũ (nơi SL của Long + Sell Stop nằm).
- **EQH / EQL** (Equal Highs/Lows): mồi nhử thanh khoản dễ bị quét nhất.

### 2.4 Premium / Discount
- Chia leg HTF bằng Fibonacci 0–1.
- **Premium** (> 0.5): vùng bán — chỉ short.
- **Discount** (< 0.5): vùng mua — chỉ long.
- **Equilibrium** (0.5): vùng cân bằng, tránh vào lệnh mới.

### 2.5 Judas Swing
- Cú quét thanh khoản giả, thường xảy ra đầu phiên London (07:00–09:00 GMT) hoặc New York (13:00–14:30 GMT).
- Dấu hiệu: nến phá đỉnh/đáy rồi đóng ngược lại trong 1–3 nến tiếp theo.

---

## 3. Volume Profile

### 3.1 Khái niệm
- **POC** (Point of Control): mức giá có volume cao nhất trong range chọn.
- **Value Area (VA)**: vùng chứa 70% tổng volume.
- **HVN** (High Volume Node): vùng được tranh chấp nhiều → thường là support/resistance mạnh.
- **LVN** (Low Volume Node): vùng "chân không" → giá đi qua nhanh, lực cản yếu.

### 3.2 Cách dùng với SMC
- Vẽ **Fixed Range Volume Profile** từ swing low → swing high của leg đang xét.
- POI SMC + POC trùng nhau → hợp lưu cực mạnh.
- Entry nên đặt phía dưới POC (nếu Long) hoặc phía trên POC (nếu Short) để tận dụng dòng tiền đã bảo vệ vị thế.

---

## 4. Multi-Timeframe Analysis

| Khung | Mục đích | Gợi ý setting |
|-------|----------|---------------|
| W1 | Định hướng vĩ mô, vùng OB lịch sử | EMA 50 |
| D1 | Bias chính, vùng Premium/Discount | EMA 20, 50 |
| H4 | Cấu trúc trung hạn, POI chính | EMA 20, 50 |
| H1 | Xác nhận bias, swing point | EMA 20 |
| M15 | Quan sát sweep, tìm CHoCH | — |
| M5 / M1 | Entry / Exit chính xác | Fibo OTE |

**Nguyên tắc top-down:** HTF cho hướng, MTF cho vùng, LTF cho điểm bấm.

---

## 5. Chỉ Báo Bổ Trợ (tùy chọn, không bắt buộc)

### 5.1 RSI
- Phân kỳ (divergence) giữa giá và RSI tại POI → xác nhận đảo chiều.
- Không dùng RSI vượt 70 / dưới 30 để vào lệnh **độc lập**.

### 5.2 EMA Ribbon
- EMA 20 / 50 / 200. Ribbon dốc lên = trend tăng; ribbon dốc xuống = trend giảm; rối = sideway (tránh trade).

### 5.3 Fibonacci Retracement
- Vẽ từ điểm bắt đầu leg → điểm kết thúc leg.
- **OTE zone: 0.618 – 0.79** là vùng vào lệnh tối ưu.
- SL đặt sau mức **0.886** hoặc swing low/high gần nhất.

---

## 6. Đặc Thù Thị Trường Crypto Futures

### 6.1 Liquidation Heatmap
- Phản ánh nơi tập trung SL của các vị thế đòn bẩy cao.
- Quy tắc: **vùng thanh lý dày = nam châm giá**. Market makers thường đẩy giá quét vùng này trước khi đảo chiều thật.
- Kết hợp với EQH/EQL của SMC để xác định mục tiêu quét.

### 6.2 Funding Rate
- Funding dương quá cao (> 0.05%/8h) → đám đông đang long quá tay → cẩn thận wash-out giảm.
- Funding âm sâu → short quá tải → cẩn thận short squeeze.

### 6.3 Open Interest (OI)
- OI tăng + giá tăng = trend lành mạnh.
- OI tăng + giá đi ngang = tích lũy, sắp bung.
- OI giảm mạnh + giá giảm = thanh lý cuối trend.

---

## 7. Thời Gian & Kill Zones (UTC+7 / giờ Việt Nam)

| Phiên | Giờ VN | Tính chất |
|-------|--------|-----------|
| Á | 07:00 – 14:00 | Tích lũy, range hẹp. Hạn chế trade. |
| London Kill Zone | **14:00 – 17:00** | Quét thanh khoản Á, định hướng ngày. |
| NY Kill Zone | **20:00 – 23:00** | Biến động mạnh nhất, setup SMC rõ ràng nhất. |
| NY Close | 02:00 – 04:00 hôm sau | Chốt lời, đảo chiều cuối ngày. |

**Ưu tiên trade London + NY Kill Zones.** Tránh vào lệnh lớn trong phiên Á trừ khi có setup rõ.

---

## 8. Đặc Thù Chứng Khoán Việt Nam (HSX/HNX)

- **Phiên ATO / ATC**: biến động mạnh, không dùng để vào lệnh SMC (thanh khoản bị bóp méo bởi lệnh khớp lệnh định kỳ).
- **Khối ngoại**: xem net buy/sell hằng ngày — dòng tiền ngoại là leading indicator cho nhóm VN30.
- **T+2.5**: không scalp được như crypto. Setup phải dựa khung D1 trở lên.
- **Phái sinh (VN30F1M)**: dùng cơ chế tương tự Futures — áp dụng được Liquidation logic.

---

*Tài liệu này sẽ được cập nhật khi hệ thống có thêm backtest & thống kê thực tế.*
