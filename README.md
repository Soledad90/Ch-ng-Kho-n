# Ch-ng-Kho-n

Phân tích chuyên sâu thị trường chứng khoán Việt Nam với khung phân bổ vốn
90 ngày cho từng mã (ví dụ `CII_Analysis.csv`), kèm một **MVRV Macro Filter**
dựa trên chu kỳ BTC để điều chỉnh size risk-on / risk-off.

## Cấu trúc

```
CII_Analysis.csv                  # phân tích CII + các dòng MVRV đã điều chỉnh
data/mvrv_btc.csv                 # MVRV daily BTC từ charts.bitbo.io
docs/MVRV_Filter.md               # thiết kế & ngưỡng của macro filter
scripts/compute_mvrv_filter.py    # tính regime, ghi MVRV rows vào CSV
```

## Dùng MVRV Filter

```bash
python scripts/compute_mvrv_filter.py            # in regime hiện tại
python scripts/compute_mvrv_filter.py --apply    # append/refresh MVRV rows
```

Xem chi tiết ngưỡng, quantile và quy tắc size trong
[`docs/MVRV_Filter.md`](docs/MVRV_Filter.md).
