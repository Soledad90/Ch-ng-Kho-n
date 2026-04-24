"""Multi-agent system for BTC entry-zone selection.

Components:
- mvrv_agent:   on-chain valuation regime (uses data/mvrv_btc.csv)
- ta_agent:     technical analysis on BTC/USD OHLC (Kraken public API)
- orchestrator: fuse MVRV + TA into entry zone, stop, TPs
"""
