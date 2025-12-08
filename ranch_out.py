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
    """
    Given a __DATE__ line (DD-MM-YYYY) and a Discord-style timestamp line like:
      "— Yesterday at 6:37 AM"
      "— Today at 7:21 PM"
      "— Monday at 8:00 PM"
      "— 12:05 AM"
    return a normalized string: "DD-MM-YYYY HH:MM AM/PM".
    If we can't parse time or don't have a date, we fall back to stripped ts_line.
    """
    ts_line = ts_line.lstrip("—").strip()

    m_time = TIME_RE.search(ts_line)
    if date_str and m_time:
        time_str = m_time.group(1).upper().replace("  ", " ")
        # Final format: DD-MM-YYYY HH:MM AM/PM
        return f"{date_str} {time_str}"

    # If no time or no date, just return whatever we have
    return ts_line


def parse_ranch_log(raw_log: str) -> List[Dict[str, Any]]:
    """
    Parse raw ranch log text from the ranch log channel.

    The raw_log is expected to contain:
      - __DATE__ DD-MM-YYYY markers from chat_read.py
      - The ranch APP logs (like in the pasted example)

    Returns a list of event dicts, each with at least:
      type, ts, player, role, discord_id
    And depending on type:
      - amount (float)
      - quantity (int)
      - animal (str)
      - count (int)
    """
    # Remove blank lines, but keep order
    lines = [ln.strip() for ln in raw_log.splitlines() if ln.strip()]

    events: List[Dict[str, Any]] = []
    i = 0

    current_date_str: Optional[str] = None  # from __DATE__ DD-MM-YYYY
    current_ts: Optional[str] = None        # normalized "DD-MM-YYYY HH:MM AM/PM"

    while i < len(lines):
        ln = lines[i]

        # --- Date markers from chat_read.py ---
        m_date = DATE_MARKER_RE.match(ln)
        if m_date:
            current_date_str = m_date.group(1)
            i += 1
            continue

        # --- Timestamp handling via "APP" line ---
        # Pattern: "APP" -> "— Yesterday at 6:37 AM" -> "Cash Deposit" ...
        if ln == "APP":
            if i + 1 < len(lines) and lines[i + 1].startswith("—"):
                ts_line = lines[i + 1]
                current_ts = _normalize_timestamp(current_date_str, ts_line)
                i += 2
                continue

        # --- Event header line ---
        if ln in _EVENT_TYPES:
            etype = _EVENT_TYPES[ln]

            # Player line
            if i + 1 >= len(lines):
                break
            m_player = _PLAYER_RE.match(lines[i + 1])
            if not m_player:
                # Something unexpected; skip this line and move on
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
                "ts": current_ts or "",  # normalized timestamp string
                "player": player_name,
                "role": role,
                "discord_id": discord_id,
            }

            # ---- Cash Deposit ----
            if etype == "cash_deposit":
                m = re.search(r"Deposit of ([\d.]+)", detail)
                ev["amount"] = float(m.group(1)) if m else 0.0
                events.append(ev)
                i += 3
                continue

            # ---- Cash Withdrawal ----
            if etype == "cash_withdrawal":
                m = re.search(r"Withdrawal of ([\d.]+)", detail)
                ev["amount"] = float(m.group(1)) if m else 0.0
                events.append(ev)
                i += 3
                continue

            # ---- Eggs / Milk Added ----
            if etype in ("eggs_added", "milk_added"):
                m = re.search(r":\s*(\d+)$", detail)
                ev["quantity"] = int(m.group(1)) if m else 0
                events.append(ev)
                i += 3
                continue

            # ---- Player Hired ----
            if etype == "player_hired":
                # detail line: "Hired to ranch id 156"
                events.append(ev)
                i += 3
                continue

            # ---- Bought Cattle ----
            if etype == "bought_cattle":
                # "Player @X ... bought 4 Deer for $200 (from ledger)"
                m = re.search(r"bought\s+(\d+)\s+(\w+)\s+for\s+\$?([\d.]+)", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                    ev["amount"] = float(m.group(3))
                events.append(ev)

                # Optional "Ranch ID: 156" line
                if i + 3 < len(lines) and lines[i + 3].startswith("Ranch ID"):
                    i += 4
                else:
                    i += 3
                continue

            # ---- Herding Completed ----
            if etype == "herding_completed":
                # "Successfully herded 4 Deer to ranch id 156"
                m = re.search(r"herded\s+(\d+)\s+(\w+)\s+to", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                events.append(ev)
                i += 3
                continue

            # ---- Cattle Sale ----
            if etype == "cattle_sale":
                # "Player @X ... sold 4 Deer for 800.0$"
                m = re.search(r"sold\s+(\d+)\s+(\w+)\s+for\s+([\d.]+)\$", detail)
                if m:
                    ev["count"] = int(m.group(1))
                    ev["animal"] = m.group(2)
                    ev["amount"] = float(m.group(3))
                events.append(ev)

                # Optional "Ranch ID: 156" line
                if i + 3 < len(lines) and lines[i + 3].startswith("Ranch ID"):
                    i += 4
                else:
                    i += 3
                continue

        i += 1

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
# Markdown builders (global)
# --------------------

def _build_cash_markdown(summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# 💰 Cash Transactions")
    lines.append("")
    lines.append("| Date/Time | Player | Type | Animal | Count | Amount |")
    lines.append("| --------- | ------ | ---- | ------ | ----- | ------ |")

    for tx in summary["cash_tx"]:
        ts = tx.get("ts", "") or ""
        player = tx.get("player", "") or ""
        kind = tx["kind"]
        animal = tx.get("animal", "") or ""
        count = tx.get("count", "") or ""
        amt = tx.get("amount", 0.0)
        sign = tx["sign"]
        lines.append(
            f"| {ts} | {player} | {kind} | {animal} | {count} | {sign}{amt:.2f} |"
        )

    lines.append(
        "|  |  |  |  | **NET** | **{:+.2f}** |".format(summary["cash_net"])
    )
    return "\n".join(lines)


def _build_resource_markdown(
    summary: Dict[str, Any],
    resource_key: str,
    title: str,
    emoji: str,
    unit_label: str,
    unit_price: float,
) -> str:
    """
    Build Eggs/Milk tables with value columns.
    """
    lines: List[str] = []
    lines.append(f"# {emoji} {title}")
    lines.append("")
    lines.append(f"Current {unit_label} price: **{unit_price:.2f}** per unit")
    lines.append("")
    lines.append("| Player | Role | Total | Unit Price | Total Value |")
    lines.append("| ------ | ---- | ----- | ---------- | ----------- |")

    for player, stats in sorted(summary["per_player"].items(), key=lambda kv: kv[0].lower()):
        total = stats[resource_key]
        if total == 0:
            continue
        total_value = total * unit_price
        lines.append(
            f"| {player} | {stats['role']} | {total} | {unit_price:.2f} | {total_value:.2f} |"
        )

    return "\n".join(lines)


def _build_bought_cattle_markdown(summary: Dict[str, Any]) -> str:
    if not summary["purchase_events"]:
        return ""
    lines: List[str] = []
    lines.append("# 🐄 Bought Cattle")
    lines.append("")
    lines.append("| Date/Time | Player | Role | Animal | Count | Amount |")
    lines.append("| --------- | ------ | ---- | ------ | ----- | ------ |")

    for ev in summary["purchase_events"]:
        lines.append(
            f"| {ev.get('ts','')} | {ev.get('player','')} | {ev.get('role','')} | "
            f"{ev.get('animal','')} | {ev.get('count','')} | {ev.get('amount',0.0):.2f} |"
        )
    return "\n".join(lines)


def _build_player_hired_markdown(summary: Dict[str, Any]) -> str:
    if not summary["hired_events"]:
        return ""
    lines: List[str] = []
    lines.append("# 👤 Player Hired")
    lines.append("")
    lines.append("| Date/Time | Player | Role |")
    lines.append("| --------- | ------ | ---- |")

    for ev in summary["hired_events"]:
        lines.append(
            f"| {ev.get('ts','')} | {ev.get('player','')} | {ev.get('role','')} |"
        )
    return "\n".join(lines)


def _build_herding_markdown(summary: Dict[str, Any]) -> str:
    if not summary["herding_events"]:
        return ""
    lines: List[str] = []
    lines.append("# 🐾 Herding Completed")
    lines.append("")
    lines.append("| Date/Time | Player | Role | Animal | Count |")
    lines.append("| --------- | ------ | ---- | ------ | ----- |")

    for ev in summary["herding_events"]:
        lines.append(
            f"| {ev.get('ts','')} | {ev.get('player','')} | {ev.get('role','')} | "
            f"{ev.get('animal','')} | {ev.get('count','')} |"
        )
    return "\n".join(lines)


def _build_cattle_sale_markdown(summary: Dict[str, Any]) -> str:
    if not summary["sale_events"]:
        return ""
    lines: List[str] = []
    lines.append("# 💵 Cattle Sale")
    lines.append("")
    lines.append("| Date/Time | Player | Role | Animal | Count | Amount |")
    lines.append("| --------- | ------ | ---- | ------ | ----- | ------ |")

    for ev in summary["sale_events"]:
        lines.append(
            f"| {ev.get('ts','')} | {ev.get('player','')} | {ev.get('role','')} | "
            f"{ev.get('animal','')} | {ev.get('count','')} | {ev.get('amount',0.0):.2f} |"
        )
    return "\n".join(lines)


def build_ranch_markdown_sections(
    events: List[Dict[str, Any]],
    prices: Dict[str, float],
) -> List[str]:
    """
    Build a list of markdown sections (strings) for the ranch report.
    These are intended to be wrapped in ```md code blocks by the Discord command.
    """
    egg_price = float(prices.get("egg", 1.0))
    milk_price = float(prices.get("milk", 1.0))

    summary = _summarize(events)
    sections: List[str] = []

    # 💰 Cash + cattle transactions
    sections.append(_build_cash_markdown(summary))

    # 🥚 Eggs
    eggs_md = _build_resource_markdown(
        summary,
        "eggs",
        "Eggs Added",
        "🥚",
        "egg",
        egg_price,
    )
    if eggs_md.strip():
        sections.append(eggs_md)

    # 🥛 Milk
    milk_md = _build_resource_markdown(
        summary,
        "milk",
        "Milk Added",
        "🥛",
        "milk",
        milk_price,
    )
    if milk_md.strip():
        sections.append(milk_md)

    # 🐄 Bought Cattle
    bc_md = _build_bought_cattle_markdown(summary)
    if bc_md.strip():
        sections.append(bc_md)

    # 👤 Player Hired
    hired_md = _build_player_hired_markdown(summary)
    if hired_md.strip():
        sections.append(hired_md)

    # 🐾 Herding Completed
    herd_md = _build_herding_markdown(summary)
    if herd_md.strip():
        sections.append(herd_md)

    # 💵 Cattle Sale
    sale_md = _build_cattle_sale_markdown(summary)
    if sale_md.strip():
        sections.append(sale_md)

    return sections


# --------------------
# Player-specific markdown
# --------------------

def build_ranch_player_markdown_sections(
    events: List[Dict[str, Any]],
    discord_id: str,
    user_mention: str,
    prices: Dict[str, float],
) -> List[str]:
    """
    Build markdown sections for a single player's ranch contribution.
    """
    egg_price = float(prices.get("egg", 1.0))
    milk_price = float(prices.get("milk", 1.0))

    player_events = [ev for ev in events if ev.get("discord_id") == discord_id]
    if not player_events:
        return []

    summary = _summarize(player_events)
    sections: List[str] = []

    # There should be exactly one player entry, but we'll just take the first.
    player_name, stats = next(iter(summary["per_player"].items()))

    net = (stats["cash_deposit"] + stats["cattle_sale"]) - (
        stats["cash_withdrawal"] + stats["cattle_buy"]
    )
    eggs_value = stats["eggs"] * egg_price
    milk_value = stats["milk"] * milk_price

    # Overall summary
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

    # Cash transactions for this player
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

    # Eggs/Milk breakdown
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

    # Herding & Cattle Sales
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
# CSV output (global)
# --------------------

def build_ranchsummary_csv_bytes(
    events: List[Dict[str, Any]],
    prices: Dict[str, float],
) -> bytes:
    """
    Build a CSV (as bytes) summarising per-player stats:
    Eggs, Milk, their values, cash in/out, cattle buy/sell & net cash.
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
