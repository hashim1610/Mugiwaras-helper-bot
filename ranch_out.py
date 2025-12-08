# ranch_out.py
from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from typing import Dict, List, Any, Optional

# --------------------
# Parsing
# --------------------

_EVENT_TYPES = {
    "Cash Deposit": "cash_deposit",
    "Cash Withdrawal": "cash_withdrawal",
    "Eggs Added": "eggs_added",
    "Milk Added": "milk_added",
    "Bought Cattle": "bought_cattle",
    "Player Hired": "player_hired",
    "Herding Completed": "herding_completed",
    "Cattle Sale": "cattle_sale",
}

_PLAYER_RE = re.compile(r"^@(?P<name>.+?) \[(?P<role>.+?)\] (?P<id>\d+)")
DATE_MARKER_RE = re.compile(r"^__DATE__\s+(\d{2}-\d{2}-\d{4})$")
TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.IGNORECASE)


def _normalize_timestamp(
    date_str: Optional[str],
    ts_line: str,
) -> str:
    ts_line = ts_line.lstrip("—").strip()

    m_time = TIME_RE.search(ts_line)
    if date_str and m_time:
        time_str = m_time.group(1).upper().replace("  ", " ")
        return f"{date_str} {time_str}"

    return ts_line


def parse_ranch_log(raw_log: str) -> List[Dict[str, Any]]:
    """
    Parse raw ranch log text from the ranch log channel.
    """
    lines = [ln.strip() for ln in raw_log.splitlines() if ln.strip()]

    print(f"[ranch_out] parse_ranch_log: total lines after strip = {len(lines)}")

    for idx, ln in enumerate(lines[:30]):
        print(f"[ranch_out] line[{idx}]: {ln}")

    events: List[Dict[str, Any]] = []
    i = 0

    current_date_str: Optional[str] = None
    current_ts: Optional[str] = None

    while i < len(lines):
        ln = lines[i]

        # Date marker
        m_date = DATE_MARKER_RE.match(ln)
        if m_date:
            current_date_str = m_date.group(1)
            i += 1
            continue

        # Timestamp via "APP" line
        if ln == "APP":
            if i + 1 < len(lines) and lines[i + 1].startswith("—"):
                ts_line = lines[i + 1]
                current_ts = _normalize_timestamp(current_date_str, ts_line)
                i += 2
                continue

        # Event header line
        event_key = None
        for key in _EVENT_TYPES.keys():
            if ln == key or ln.startswith(key + ":"):
                event_key = key
                break

        if event_key is not None:
            etype = _EVENT_TYPES[event_key]

            if i + 1 >= len(lines):
                break
            m_player = _PLAYER_RE.match(lines[i + 1])
            if not m_player:
                print(f"[ranch_out] Expected player line after '{ln}', got: {lines[i+1]}")
                i += 1
                continue

            player_name = m_player.group("name")
            role = m_player.group("role")
            discord_id = m_player.group("id")

            if i + 2 >= len(lines):
                break
            detail = lines[i + 2]

            ev: Dict[str, Any] = {
                "type": etype,
                "ts": current_ts or "",
                "player": player_name,
                "role": role,
                "discord_id": discord_id,
            }

            if etype == "cash_deposit":
                m = re.search(r"Deposit of ([\d.]+)", detail)
                ev["amount"] = float(m.group(1)) if m else 0.0
                events.append(ev)
                i += 3
                continue

            if etype == "cash_withdrawal":
                m = re.search(r"Withdrawal of ([\d.]+)", detail)
                ev["amount"] = float(m.group(1)) if m else 0.0
                events.append(ev)
                i += 3
                continue

            if etype in ("eggs_added", "milk_added"):
                m = re.search(r":\s*(\d+)$", detail)
                ev["quantity"] = int(m.group(1)) if m else 0
                events.append(ev)
                i += 3
                continue

            if etype == "player_hired":
                events.append(ev)
                i += 3
                continue

            if etype == "bought_cattle":
                m = re.search(r"bought\s+(\d+)\s+(\w+)\s+for\s+\$?([\d.]+)", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                    ev["amount"] = float(m.group(3))
                events.append(ev)

                if i + 3 < len(lines) and lines[i + 3].startswith("Ranch ID"):
                    i += 4
                else:
                    i += 3
                continue

            if etype == "herding_completed":
                m = re.search(r"herded\s+(\d+)\s+(\w+)\s+to", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                events.append(ev)
                i += 3
                continue

            if etype == "cattle_sale":
                m = re.search(r"sold\s+(\d+)\s+(\w+)\s+for\s+([\d.]+)\$", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                    ev["amount"] = float(m.group(3))
                events.append(ev)

                if i + 3 < len(lines) and lines[i + 3].startswith("Ranch ID"):
                    i += 4
                else:
                    i += 3
                continue

        i += 1

    print(f"[ranch_out] parse_ranch_log: parsed {len(events)} events")
    return events


# --------------------
# Aggregation
# --------------------

def _summarize(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_player: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "role": None,
            "eggs": 0,
            "milk": 0,
            "cash_deposit": 0.0,
            "cash_withdrawal": 0.0,
            "cattle_buy": 0.0,
            "cattle_sale": 0.0,
            "cattle_buy_count": 0,
            "cattle_sale_count": 0,
        }
    )

    cash_tx: List[Dict[str, Any]] = []
    eggs_events: List[Dict[str, Any]] = []
    milk_events: List[Dict[str, Any]] = []
    hired_events: List[Dict[str, Any]] = []
    herding_events: List[Dict[str, Any]] = []
    sale_events: List[Dict[str, Any]] = []
    purchase_events: List[Dict[str, Any]] = []

    for ev in events:
        player = ev["player"]
        stats = per_player[player]
        if stats["role"] is None:
            stats["role"] = ev.get("role")

        etype = ev["type"]

        if etype == "eggs_added":
            q = ev.get("quantity", 0)
            stats["eggs"] += q
            eggs_events.append(ev)

        elif etype == "milk_added":
            q = ev.get("quantity", 0)
            stats["milk"] += q
            milk_events.append(ev)

        elif etype == "cash_deposit":
            amt = ev.get("amount", 0.0)
            stats["cash_deposit"] += amt
            cash_tx.append({**ev, "sign": "+", "kind": "Deposit"})

        elif etype == "cash_withdrawal":
            amt = ev.get("amount", 0.0)
            stats["cash_withdrawal"] += amt
            cash_tx.append({**ev, "sign": "-", "kind": "Withdrawal"})

        elif etype == "bought_cattle":
            amt = ev.get("amount", 0.0)
            cnt = ev.get("count", 0)
            stats["cattle_buy"] += amt
            stats["cattle_buy_count"] += cnt
            cash_tx.append({**ev, "sign": "-", "kind": "Cattle Buy"})
            purchase_events.append(ev)

        elif etype == "cattle_sale":
            amt = ev.get("amount", 0.0)
            cnt = ev.get("count", 0)
            stats["cattle_sale"] += amt
            stats["cattle_sale_count"] += cnt
            cash_tx.append({**ev, "sign": "+", "kind": "Cattle Sale"})
            sale_events.append(ev)

        elif etype == "player_hired":
            hired_events.append(ev)

        elif etype == "herding_completed":
            herding_events.append(ev)

    net_total = 0.0
    for tx in cash_tx:
        amt = tx.get("amount", 0.0)
        net_total += amt if tx["sign"] == "+" else -amt

    return {
        "per_player": per_player,
        "cash_tx": cash_tx,
        "cash_net": net_total,
        "eggs_events": eggs_events,
        "milk_events": milk_events,
        "hired_events": hired_events,
        "herding_events": herding_events,
        "sale_events": sale_events,
        "purchase_events": purchase_events,
    }


# --------------------
# Player-specific markdown (used by /ranch player)
# (unchanged style, no CSV involved here, so I won't re-add emojis explanation)
# --------------------

def build_ranch_player_markdown_sections(
    events: List[Dict[str, Any]],
    discord_id: str,
    user_mention: str,
    prices: Dict[str, float],
) -> List[str]:
    egg_price = float(prices.get("egg", 1.0))
    milk_price = float(prices.get("milk", 1.0))

    player_events = [ev for ev in events if ev.get("discord_id") == discord_id]
    if not player_events:
        return []

    summary = _summarize(player_events)
    sections: List[str] = []

    player_name, stats = next(iter(summary["per_player"].items()))

    net = (stats["cash_deposit"] + stats["cattle_sale"]) - (
        stats["cash_withdrawal"] + stats["cattle_buy"]
    )
    eggs_value = stats["eggs"] * egg_price
    milk_value = stats["milk"] * milk_price

    lines: List[str] = []
    lines.append(f"# 👤 Ranch Player Summary — {user_mention}")
    lines.append("")
    lines.append(f"Log name: **{player_name}**")
    lines.append("")
    lines.append("| Stat | Value |")
    lines.append("| ---- | ----- |")
    lines.append(f"| Role | {stats['role']} |")
    lines.append(f"| 🥚 Total Eggs | {stats['eggs']} (value {eggs_value:.2f} at {egg_price:.2f}/egg) |")
    lines.append(f"| 🥛 Total Milk | {stats['milk']} (value {milk_value:.2f} at {milk_price:.2f}/milk) |")
    lines.append(f"| 💰 Cash Deposited | {stats['cash_deposit']:.2f} |")
    lines.append(f"| 💸 Cash Withdrawn | {stats['cash_withdrawal']:.2f} |")
    lines.append(f"| 🐄 Cattle Purchased (count) | {stats['cattle_buy_count']} |")
    lines.append(f"| 🐄 Cattle Purchased (amount) | {stats['cattle_buy']:.2f} |")
    lines.append(f"| 💵 Cattle Sold (count) | {stats['cattle_sale_count']} |")
    lines.append(f"| 💵 Cattle Sold (amount) | {stats['cattle_sale']:.2f} |")
    lines.append(f"| 📊 Net Cash Impact | {net:.2f} |")

    sections.append("\n".join(lines))

    if summary["cash_tx"]:
        lines = []
        lines.append(f"# 💰 Cash Transactions — {user_mention}")
        lines.append("")
        lines.append("| Date/Time | Type | Animal | Count | Amount |")
        lines.append("| --------- | ---- | ------ | ----- | ------ |")

        for tx in summary["cash_tx"]:
            ts = tx.get("ts", "") or ""
            kind = tx["kind"]
            animal = tx.get("animal", "") or ""
            count = tx.get("count", "") or ""
            amt = tx.get("amount", 0.0)
            sign = tx["sign"]
            lines.append(
                f"| {ts} | {kind} | {animal} | {count} | {sign}{amt:.2f} |"
            )

        sections.append("\n".join(lines))

    if stats["eggs"] or stats["milk"]:
        lines = []
        lines.append(f"# 🥚🥛 Production — {user_mention}")
        lines.append("")
        lines.append(f"Current egg price: **{egg_price:.2f}**, milk price: **{milk_price:.2f}**")
        lines.append("")
        lines.append("| Resource | Total | Unit Price | Total Value |")
        lines.append("| -------- | ----- | ---------- | ----------- |")
        lines.append(f"| Eggs | {stats['eggs']} | {egg_price:.2f} | {eggs_value:.2f} |")
        lines.append(f"| Milk | {stats['milk']} | {milk_price:.2f} | {milk_value:.2f} |")
        sections.append("\n".join(lines))

    if summary["herding_events"] or summary["sale_events"]:
        lines = []
        lines.append(f"# 🐾 Herding & 💵 Sales — {user_mention}")
        lines.append("")
        lines.append("| Date/Time | Type | Animal | Count | Amount |")
        lines.append("| --------- | ---- | ------ | ----- | ------ |")

        for ev in summary["herding_events"]:
            lines.append(
                f"| {ev.get('ts','')} | Herding | {ev.get('animal','')} | {ev.get('count','')} |  |"
            )
        for ev in summary["sale_events"]:
            lines.append(
                f"| {ev.get('ts','')} | Cattle Sale | {ev.get('animal','')} | {ev.get('count','')} | {ev.get('amount',0.0):.2f} |"
            )
        sections.append("\n".join(lines))

    return sections


# --------------------
# CSV output (GLOBAL) — NO EMOJIS
# --------------------

def build_ranchsummary_csv_bytes(
    events: List[Dict[str, Any]],
    prices: Dict[str, float],
) -> bytes:
    """
    Build a CSV (as bytes) summarising per-player stats:
    Eggs, Milk, their values, cash in/out, cattle buy/sell & net cash.
    NO emojis in headers or values.
    """
    egg_price = float(prices.get("egg", 1.0))
    milk_price = float(prices.get("milk", 1.0))

    summary = _summarize(events)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "Player",
            "Role",
            "Total Eggs",
            "Egg Value",
            "Total Milk",
            "Milk Value",
            "Cash Deposit",
            "Cash Withdrawal",
            "Cattle Buy Amount",
            "Cattle Sale Amount",
            "Cattle Buy Count",
            "Cattle Sale Count",
            "Net Cash Change",
        ]
    )

    for player, stats in sorted(summary["per_player"].items(), key=lambda kv: kv[0].lower()):
        eggs_value = stats["eggs"] * egg_price
        milk_value = stats["milk"] * milk_price
        net = (stats["cash_deposit"] + stats["cattle_sale"]) - (
            stats["cash_withdrawal"] + stats["cattle_buy"]
        )
        writer.writerow(
            [
                player,
                stats["role"],
                stats["eggs"],
                f"{eggs_value:.2f}",
                stats["milk"],
                f"{milk_value:.2f}",
                f"{stats['cash_deposit']:.2f}",
                f"{stats['cash_withdrawal']:.2f}",
                f"{stats['cattle_buy']:.2f}",
                f"{stats['cattle_sale']:.2f}",
                stats["cattle_buy_count"],
                stats["cattle_sale_count"],
                f"{net:.2f}",
            ]
        )

    return output.getvalue().encode("utf-8")
