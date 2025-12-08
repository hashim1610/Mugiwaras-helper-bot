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

    # For debugging, show first 30 lines
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

        # Timestamp via "APP" line (if present)
        if ln == "APP":
            if i + 1 < len(lines) and lines[i + 1].startswith("—"):
                ts_line = lines[i + 1]
                current_ts = _normalize_timestamp(current_date_str, ts_line)
                i += 2
                continue

        # Event header line
        # Be a bit more forgiving: allow "Cash Deposit" or "Cash Deposit: blah"
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
                # Debug: show what the player line actually is
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

# (rest of ranch_out.py: summarizing, markdown builders, CSV builder)
# KEEP your last version as-is below this, no changes needed there.
# Only parse_ranch_log was changed for debugging & robustness.
