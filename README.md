# Phân Tích Chứng Khoán CII

Phân tích chuyên sâu cổ phiếu **CII** (CTCP Đầu tư Hạ tầng Kỹ thuật TP.HCM – HOSE) trong 8 năm gần nhất (2018–2026), xác định **vùng giá tối ưu đầu tư tích lũy tháng 04-05-06 năm 2026**.

---

## Tính năng

- Tải dữ liệu lịch sử giá CII từ Yahoo Finance (8 năm: 2018–nay)
- Tính toán đầy đủ các chỉ số kỹ thuật:
  - Moving Averages: SMA 20/50/100/200, EMA 12/26/50
  - Bollinger Bands (20 kỳ, 2σ) + %B + Bandwidth
  - RSI 14 kỳ
  - MACD (12/26/9)
  - Stochastic Oscillator (%K/%D)
  - ATR 14 kỳ
  - OBV (On-Balance Volume)
- Phân tích mùa vụ tháng 4-5-6 theo từng năm
- Xác định vùng hỗ trợ/kháng cự + mức Fibonacci
- Xuất file Excel nhiều sheet chi tiết

## Yêu cầu

```
Python 3.9+
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Sử dụng

```bash
python analyze_CII.py
```

Script sẽ tạo file `CII_PhanTich_ChuyenSau.xlsx` gồm 5 sheet:

| Sheet | Nội dung |
|-------|----------|
| `01_Du_Lieu_Lich_Su` | Dữ liệu OHLCV thô, % thay đổi hàng ngày |
| `02_Chi_So_Ky_Thuat` | Tất cả chỉ số kỹ thuật (27 cột) |
| `03_Phan_Tich_Mua_Vu` | Hiệu suất T4-T5-T6 qua từng năm + thống kê tháng |
| `04_Tom_Tat_Khuyen_Nghi` | Vùng giá đề xuất 2026, Fibonacci, chiến lược DCA |
| `05_Hieu_Suat_Nam` | Tổng kết hiệu suất mỗi năm |

## Vùng giá khuyến nghị (dựa trên phân tích lịch sử)

Script tự động tính toán các vùng giá sau cho giai đoạn T04-T06/2026:

- **Vùng mua mạnh** – Ưu tiên mua tích lũy mạnh (quá bán lịch sử)
- **Vùng mua** – Mua theo từng đợt
- **Vùng tích lũy** – Mua dần khi thị trường ổn định
- **Mục tiêu 1 / Mục tiêu 2** – Vùng chốt lời

> ⚠️ **Lưu ý**: Phân tích kỹ thuật không đảm bảo kết quả trong tương lai. Luôn quản lý rủi ro khi đầu tư.

