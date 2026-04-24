# Ch-ng-Kho-n — Trading Agent & Phân tích Chuyên sâu

Repo này chứa **blueprint cho một Agent phân tích kỹ thuật có kỷ luật**, áp dụng được cho Crypto Futures, Crypto Spot, Chứng khoán Việt Nam (HSX/HNX) và Phái sinh VN30.

## Cấu trúc repo

| File | Mục đích |
|------|----------|
| [`AGENT.md`](AGENT.md) | **System prompt** của Agent. Định nghĩa vai trò, quy trình 5 bước, ma trận hợp lưu, schema output, và các quy tắc cấm kỵ. |
| [`docs/PHAN_TICH_KY_THUAT.md`](docs/PHAN_TICH_KY_THUAT.md) | Từ điển kỹ thuật: Market Structure, SMC/ICT, Volume Profile, Multi-Timeframe, Kill Zones, đặc thù Crypto & CK Việt Nam. |
| [`docs/CHECKLIST_KY_LUAT.md`](docs/CHECKLIST_KY_LUAT.md) | Checklist trước / trong / sau lệnh + Circuit Breakers + Vị thế cuộc sống. |
| [`templates/TRADE_ANALYSIS_TEMPLATE.md`](templates/TRADE_ANALYSIS_TEMPLATE.md) | Template markdown phân tích 1 lệnh. |
| [`templates/TRADE_ANALYSIS_TEMPLATE.csv`](templates/TRADE_ANALYSIS_TEMPLATE.csv) | Template CSV nhật ký lệnh, theo dõi winrate & expectancy. |
| [`CII_Analysis.csv`](CII_Analysis.csv) | Ví dụ phân tích chuyên sâu cổ phiếu CII. |

## Cách dùng nhanh

1. **Làm system prompt cho LLM**: copy toàn bộ nội dung `AGENT.md` dán vào đầu hội thoại với ChatGPT / Claude / Gemini / Devin Playbook.
2. **Gửi đầu vào**: symbol + khung thời gian + ảnh chart + equity hiện tại.
3. **Nhận output** đúng theo schema Mục 4 của `AGENT.md` (Bias HTF → POI → Kịch bản A/B → Confluence Score → Risk Plan).
4. **Ghi lệnh** vào `templates/TRADE_ANALYSIS_TEMPLATE.csv` để theo dõi hiệu suất dài hạn.

## Triết lý

> **Xác suất × RR × Kỷ luật > Cảm xúc × FOMO**

Agent này là công cụ, không phải lời khuyên đầu tư. Thị trường luôn có rủi ro mất vốn.
