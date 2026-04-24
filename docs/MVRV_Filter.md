# MVRV Macro Filter

Bộ lọc vĩ mô dùng chỉ số **MVRV (Market Value / Realized Value) của Bitcoin**
để điều chỉnh kế hoạch phân bổ vốn của hệ thống Ch-ng-Kho-n (ví dụ
`CII_Analysis.csv`). BTC cycle thường dẫn dắt tâm lý risk-on/risk-off toàn cầu,
nên dùng MVRV như một "gate" cho toàn bộ positions — bao gồm cổ phiếu VN.

## Nguồn dữ liệu

- `data/mvrv_btc.csv` — trích xuất từ
  [charts.bitbo.io/mvrv](https://charts.bitbo.io/mvrv/) (inline Plotly arrays:
  `axis_x`, `c`, `mvrv`, `mvrvm1`, `real`).
- 5.562 dòng daily từ **2011-02-01** đến **2026-04-24**.
- Cột: `date, mvrv, mvrv_minus_1, btc_price_usd, realized_price_usd`.

## Thống kê lịch sử

| Chỉ số | Giá trị |
|---|---|
| Mean   | 1.823 |
| Median | 1.715 |
| Stdev  | 0.81  |
| P25    | 1.29  |
| P75    | 2.19  |
| P90    | 2.79  |
| Max    | 7.17 (2011-06-05) |
| Min    | 0.41 (2011-10-20) |

## Phân vùng (regime)

| Ngưỡng MVRV           | Regime       | Size multiplier | Tín hiệu |
|-----------------------|--------------|-----------------|----------|
| < 1.00                | Deep Value   | **1.50x**       | Aggressive buy — vùng đáy vĩ mô |
| 1.00 – P50 (1.715)    | Discount     | **1.15x**       | Trên baseline — còn rẻ, lạc quan nhẹ |
| P50 – P75 (1.715–2.19)| Neutral      | **1.00x**       | Baseline — không có lợi thế vĩ mô |
| P75 – P90 (2.19–2.79) | Hot          | **0.60x**       | Giảm size, chốt lời dần — định giá cao |
| ≥ P90 (2.79)          | Euphoria     | **0.25x**       | Hạn chế mua mới, tăng tiền mặt — rủi ro đỉnh |

Size multiplier được áp vào từng tháng trong `Capital Allocation Plan` của từng
tài sản. Kết quả làm tròn đến 1.000 VND.

## Áp dụng vào CII (tại 2026-04-24)

- MVRV hiện tại = **1.44** → percentile **35.4%** (thấp hơn 65% lịch sử).
- Regime = **Discount** → multiplier **1.15x**.
- Baseline 90 ngày: 3,000,000 + 3,500,000 + 3,500,000 = 10,000,000 VND.
- **Adjusted**: 3,450,000 + 4,025,000 + 4,025,000 = **11,500,000 VND**.
- Macro signal: *"Above-baseline buy — mild optimism, still cheap"*.

Các dòng `MVRV *` được append vào `CII_Analysis.csv` (idempotent — chạy lại sẽ
ghi đè đúng các dòng đó, giữ nguyên các trường gốc).

## Quy trình cập nhật

```bash
# (1) Cập nhật data/mvrv_btc.csv từ nguồn bitbo nếu cần.
# (2) Tính regime và in ra stdout (không ghi file):
python scripts/compute_mvrv_filter.py

# (3) Ghi các dòng MVRV vào CII_Analysis.csv:
python scripts/compute_mvrv_filter.py --apply
```

## Ghi chú thiết kế

- **Tại sao dùng MVRV cho cổ phiếu VN?** MVRV là proxy tốt cho global risk
  appetite — khi MVRV euphoria thì risk asset toàn cầu (bao gồm VN equities
  beta cao như CII) thường gần đỉnh cục bộ. Dùng làm macro overlay, không
  thay thế phân tích cơ bản của từng mã.
- **Tại sao quantile thay vì ngưỡng cứng (1.0 / 2.4 / 3.7)?** Quantile thích
  nghi theo cấu trúc dữ liệu thực tế — ngưỡng chart-based như "3.7 = đỉnh"
  bias về các chu kỳ đầu (2011, 2013) khi biên độ lớn hơn.
- **Rounding:** multiplier áp lên capital amount rồi làm tròn đến 1.000 VND
  để ra con số dễ chuyển khoản.
- **Idempotent:** script `--apply` luôn xóa các dòng `MVRV *` cũ trước khi
  append lại, tránh trùng lặp qua nhiều lần chạy.
