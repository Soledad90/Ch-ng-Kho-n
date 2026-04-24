# Scheduler + Alerts

Tự động chạy Master Data Agent theo lịch, gửi alert khi **decision flip
NO_TRADE → TRADE** hoặc **direction flip LONG ↔ SHORT**.

Kênh: Telegram, Discord, email. Stdlib only (urllib + smtplib).

## Chạy

```bash
# Cron mode: 1 lần mỗi invocation (cron mỗi 15 phút)
*/15 * * * * cd /path/to/repo && python -m agents.run_scheduler --once --assets BTC

# Loop mode: daemon, sleep giữa các tick
python -m agents.run_scheduler --loop --interval 900 --assets BTC,ETH,SOL

# Test alerts luôn (không cần flip gì)
python -m agents.run_scheduler --test-alert
```

## Cấu hình (env vars)

Để trống env = kênh đó bị skip.

### Telegram

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-xyz..."
export TELEGRAM_CHAT_ID="12345678"          # hoặc @channel
```

Cách lấy: chat với [@BotFather](https://t.me/BotFather) → `/newbot` → lấy token. Chat_id lấy
bằng cách nhắn bot 1 tin rồi gọi `https://api.telegram.org/bot<TOKEN>/getUpdates`.

### Discord

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/.../..."
```

Cách lấy: Server Settings → Integrations → Webhooks → New Webhook → Copy URL.

### Email (SMTP)

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"            # 587 = STARTTLS, 465 = SSL
export SMTP_USER="you@gmail.com"
export SMTP_PASS="xxxx xxxx xxxx xxxx"  # Gmail App Password, không phải mật khẩu chính
export ALERT_EMAIL_TO="recipient@example.com"
```

Gmail cần bật [App Password](https://myaccount.google.com/apppasswords).
Yahoo/Outlook tương tự.

## Flip detection logic

State file `reports/scheduler/state.json` lưu `{asset: {decision, direction, ts}}`.

Mỗi tick:

| Prev | New | Alert? |
|---|---|---|
| UNKNOWN / NO_TRADE | TRADE | **Yes** (confluence gate passed) |
| TRADE long | TRADE short | **Yes** (direction flip) |
| TRADE short | TRADE long | **Yes** |
| TRADE | NO_TRADE | No (alert-fatigue — skip) |
| NO_TRADE | NO_TRADE | No |
| TRADE long | TRADE long | No |

## Alert format

```
[BTC/USDT] NO_TRADE → TRADE (LONG, 8/12)

Asset: BTC/USDT
Flip: NO_TRADE → TRADE
Reason: NO_TRADE -> TRADE (confluence gate passed)

Decision : TRADE
Direction: long
Entry    : 67500
Stop     : 66200
TP1      : 70100
TP2      : 72400
RR(TP1)  : 2.0
Confluence: 8/12
Bias HTF : bullish — D1=up, H4=up, W1=up
MVRV: 1.44 (Discount)

As of: 2026-04-24 09:15 UTC
```

## Giới hạn

- **Alert fatigue**: hiện tại fire cả khi chỉ direction flip giữa 2 tick. Nếu quá ồn,
  có thể thêm cooldown N tick (TODO).
- **No retry**: nếu Telegram/Discord/SMTP fail thì skip tick này, không retry. State
  vẫn được update (để tránh spam ở tick sau khi connectivity hồi phục).
- **No batching**: 3 asset flip cùng 1 tick = 3 alerts riêng lẻ.
- **No HTML formatting trong email**: plain text only.
- **No multi-recipient**: `ALERT_EMAIL_TO` chỉ nhận 1 địa chỉ (hoặc comma-separated nếu SMTP server hỗ trợ).

## Systemd timer (production-ready)

`/etc/systemd/system/devin-master-agent.service`:

```ini
[Unit]
Description=Master Data Agent scheduler
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/repos/Ch-ng-Kho-n
EnvironmentFile=/home/ubuntu/.config/master-agent.env
ExecStart=/usr/bin/python3 -m agents.run_scheduler --once --assets BTC,ETH,SOL
```

`/etc/systemd/system/devin-master-agent.timer`:

```ini
[Unit]
Description=Run Master Data Agent every 15 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
```

`/home/ubuntu/.config/master-agent.env` (chmod 600):

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DISCORD_WEBHOOK_URL=...
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now devin-master-agent.timer
journalctl -u devin-master-agent.service -n 50
```
