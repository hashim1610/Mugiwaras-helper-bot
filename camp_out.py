# camp_out.py
"""
camp_out.py

Parsing + markdown + CSV output for camp log commands.

Exports:
- parse_log(raw_log)
- build_markdown_sections(donations, supplies, ledger, id_to_name)
- build_delivery_table(supplies, id_to_name)
- build_logsummary_csv_bytes(donations, supplies, ledger, id_to_name)
"""

import re
import csv
import io


def normalize_number(num_str: str) -> float:
    return float(num_str.replace(",", ".").strip())


# ---------------- NAME HANDLING ----------------

def clean_discord_name(discord_part: str, lines, idx: int) -> str | None:
    """
    Extract meaningful name from log line.
    Prefer <@ID> → resolved display name.
    """
    s = discord_part.replace("**", "").replace("`", "").strip()

    # Raw mention in this line
    m = re.search(r"<@!?(\d+)>", s)
    if m:
        return f"<@{m.group(1)}>"

    # Pattern like: @Name ... ID
    tokens = s.split()
    if tokens and tokens[-1].isdigit():
        return f"<@{tokens[-1]}>"

    # Look ahead for name or ID
    for k in range(idx + 1, min(idx + 4, len(lines))):
        nxt = lines[k].replace("**", "").replace("`", "").strip()
        if not nxt:
            continue

        m2 = re.search(r"<@!?(\d+)>", nxt)
        if m2:
            return f"<@{m2.group(1)}>"

        parts = nxt.split()
        if parts and parts[-1].isdigit():
            return f"<@{parts[-1]}>"

        # fallback textual name
        name = " ".join(parts)
        return name

    # Final fallback: use raw cleaned text
    return s or None


def display_name_from_mention(name: str, id_to_name: dict | None) -> str:
    """
    Convert <@ID> → DisplayName (no leading @).
    If not a mention or unknown, return name as-is.
    """
    if not id_to_name:
        return name

    name = name.strip()
    m = re.fullmatch(r"<@!?(\d+)>", name)
    if not m:
        return name  # already a normal name

    uid = m.group(1)
    disp = id_to_name.get(uid)
    if not disp:
        return name

    return disp


# ---------------- NUMBER EXTRACTION ----------------

def extract_number_after_marker(text: str, marker: str) -> float | None:
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    digits = ""
    started = False
    for ch in tail:
        if ch.isdigit() or ch in ".,": 
            digits += ch
            started = True
        elif started:
            break
    return normalize_number(digits) if digits else None


def extract_number_after_char(text: str, ch_marker: str) -> float | None:
    if ch_marker not in text:
        return None
    tail = text.split(ch_marker, 1)[1]
    digits = ""
    started = False
    for ch in tail:
        if ch.isdigit() or ch in ".,": 
            digits += ch
            started = True
        elif started:
            break
    return normalize_number(digits) if digits else None


# ---------------- PARSER ----------------

def parse_log(raw_log: str):
    """
    Parse the raw log text into three lists:
      - donations: [{name, materials, date}]
      - supplies:  [{name, amount, date, items?, value?}]
      - ledger:    [{name, transition, amount, date}]

    Date is derived from special lines: "__DATE__ DD-MM-YYYY"
    injected by chat_read.build_camp_raw_log / build_raw_log_from_channel.

    Also handles:
      - "Made a Sale Of 100 Of Stock For $1600 ..."
      - "Bought a hunting wagon for $1000 ..."
    which are mapped into both supplies and ledger.
    """
    lines = raw_log.splitlines()
    n = len(lines)

    donations: list[dict] = []
    supplies: list[dict] = []
    ledger: list[dict] = []

    current_date: str | None = None

    i = 0
    while i < n:
        line = lines[i].strip()

        # Date marker from chat_read
        if line.startswith("__DATE__ "):
            current_date = line[len("__DATE__ "):].strip()
            i += 1
            continue

        # ---------------- NEW PATTERNS: SALE / PURCHASE ----------------

        # Example:
        # "Made a Sale Of 100 Of Stock For $1600 ID: 2159"
        if "Made a Sale Of" in line and "Of Stock For" in line and "$" in line:
            m = re.search(r"Made a Sale Of\s+(\d+).*?For\s*\$([0-9.,]+)", line)
            if m:
                qty = int(m.group(1))
                value = normalize_number(m.group(2))

                # find discord name
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break

                if name:
                    # As a "supply"/delivery (for supply summary + deliveries command)
                    supplies.append({
                        "name": name,
                        "amount": value,     # treat value as delivered amount
                        "date": current_date,
                        "items": f"{qty} Stock",
                        "value": value,
                    })
                    # As a ledger deposit
                    ledger.append({
                        "name": name,
                        "transition": "Deposit",
                        "amount": value,     # positive
                        "date": current_date,
                    })

        # Example:
        # "Bought a hunting wagon for $1000 ID: 2159"
        if "Bought a " in line and "for $" in line:
            m = re.search(r"Bought a\s+(.+?)\s+for\s*\$([0-9.,]+)", line, re.IGNORECASE)
            if m:
                item = m.group(1).strip()
                value = normalize_number(m.group(2))

                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break

                if name:
                    # As a "supply"/delivery (for supply summary + deliveries command)
                    supplies.append({
                        "name": name,
                        "amount": value,
                        "date": current_date,
                        "items": item,
                        "value": value,
                    })
                    # As a ledger withdrawal (negative amount)
                    ledger.append({
                        "name": name,
                        "transition": "Withdrawal",
                        "amount": -abs(value),
                        "date": current_date,
                    })

        # ---------------- EXISTING PATTERNS: DONATIONS / SUPPLIES / LEDGER ----------------

        # Donations
        if "Donated" in line and "Materials added" in line:
            materials = extract_number_after_marker(line, "Materials added")
            if materials is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break
                if name:
                    donations.append({
                        "name": name,
                        "materials": materials,
                        "date": current_date,
                    })

        # Supplies (classic "Delivered Supplies X" style)
        if "Delivered" in line and "Supplies" in line:
            amt = extract_number_after_marker(line, "Delivered Supplies")
            if amt is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break
                if name:
                    supplies.append({
                        "name": name,
                        "amount": amt,
                        "date": current_date,
                        # no items/value info here
                    })

        # Ledger (classic "Deposited to/Withdrew from clan ledger")
        if ("Deposited to clan ledger" in line) or ("Withdrew from clan ledger" in line):
            trans = "Deposit" if "Deposited" in line else "Withdrawal"
            amt = extract_number_after_char(line, "$")

            if amt is not None:
                # Make withdrawals negative
                if trans == "Withdrawal":
                    amt = -abs(amt)

                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break

                if name:
                    ledger.append({
                        "name": name,
                        "transition": trans,
                        "amount": amt,
                        "date": current_date,
                    })

        i += 1

    return donations, supplies, ledger


# ---------------- MARKDOWN TABLES ----------------

def make_table(headers, rows, align_right=None) -> str:
    if align_right is None:
        align_right = set()

    cols = len(headers)
    widths = [len(str(h)) for h in headers]

    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))

    def fmt_row(row):
        cells = []
        for i in range(cols):
            c = str(row[i])
            if i in align_right:
                cells.append(c.rjust(widths[i]))
            else:
                cells.append(c.ljust(widths[i]))
        return "| " + " | ".join(cells) + " |"

    header = fmt_row(headers)
    sep = "| " + " | ".join("-" * w for w in widths) + " |"

    result = [header, sep]
    for r in rows:
        result.append(fmt_row(r))

    return "\n".join(result)


def build_markdown_sections(donations, supplies, ledger, id_to_name=None):
    """
    Returns a list of 4 markdown sections:
      0: Donations breakdown
      1: Overall totals (with total member count)
      2: Supply summary (WITH date)
      3: Ledger transactions (WITH date, negative withdrawals)
    """
    sections: list[str] = []

    # Donations summary (aggregated)
    donation_map: dict[str, dict] = {}
    for d in donations:
        nm = d["name"]
        mt = d["materials"]
        if nm not in donation_map:
            donation_map[nm] = {"count": 0, "total": 0.0}
        donation_map[nm]["count"] += 1
        donation_map[nm]["total"] += mt

    sorted_don = sorted(
        donation_map.items(),
        key=lambda kv: (-kv[1]["count"], -kv[1]["total"])
    )

    total_count = sum(v["count"] for v in donation_map.values())
    total_mat = sum(v["total"] for v in donation_map.values())

    # Total members in this date range
    member_names = set()
    for d in donations:
        member_names.add(d["name"])
    for s in supplies:
        member_names.add(s["name"])
    for l in ledger:
        member_names.add(l["name"])
    total_member_count = len(member_names)

    # 1) Donations table
    sec1_lines: list[str] = []
    sec1_lines.append("🟥 Donations Breakdown Table Summary")

    donation_rows = [
        [
            display_name_from_mention(name, id_to_name),
            stats["count"],
            f"{stats['total']:.2f}",
        ]
        for name, stats in sorted_don
    ]

    sec1_lines.append(
        make_table(
            ["Name", "Donations", "Total Materials Value"],
            donation_rows,
            align_right={1, 2}
        )
    )
    sections.append("\n\n".join(sec1_lines))

    # 2) Overall Totals
    sec2_lines: list[str] = []
    sec2_lines.append("🟦 Overall Totals")
    sec2_lines.append(
        make_table(
            ["Total Donations", "Total Materials Value", "Total Member Count"],
            [[total_count, f"{total_mat:.2f}", total_member_count]],
            align_right={0, 1, 2}
        )
    )
    sections.append("\n\n".join(sec2_lines))

    # 3) Supplies (with Date column) - includes classic supplies + new sale/buy events
    sec3_lines: list[str] = []
    sec3_lines.append("🟩 Supply Mission Summary")

    supply_rows = []
    for s in supplies:
        date_str = s.get("date") or ""
        name = display_name_from_mention(s["name"], id_to_name)
        supply_rows.append([date_str, name, f"{s['amount']:.2f}"])

    sec3_lines.append(
        make_table(
            ["Date", "Name", "Supplies Delivered"],
            supply_rows,
            align_right={2}
        )
    )
    sections.append("\n\n".join(sec3_lines))

    # 4) Ledger (with Date column)
    sec4_lines: list[str] = []
    sec4_lines.append("🟨 LEDGER TRANSACTIONS")
    ledger_rows = []
    for l in ledger:
        date_str = l.get("date") or ""
        base_name = display_name_from_mention(l["name"], id_to_name)
        transition = "+ Deposit" if l["transition"] == "Deposit" else "- Withdrawal"
        ledger_rows.append(
            [date_str, base_name, transition, f"{l['amount']:.2f}"]
        )

    sec4_lines.append(
        make_table(
            ["Date", "Name", "Transition", "Amount"],
            ledger_rows,
            align_right={3}
        )
    )
    sections.append("\n\n".join(sec4_lines))

    return sections


def build_delivery_table(supplies, id_to_name=None) -> str:
    """
    Build a table for /logdelivery_range:
      Columns: Date, Name, Items, Value
    Uses:
      - supplies entries that may have 'items' and 'value'
      - for older supplies, items="Supplies", value=amount
    """
    rows = []
    for s in supplies:
        date_str = s.get("date") or ""
        name = display_name_from_mention(s["name"], id_to_name)
        items = s.get("items") or "Supplies"
        value = s.get("value", s.get("amount", 0.0))
        rows.append([date_str, name, items, f"{value:.2f}"])

    return make_table(
        ["Date", "Name", "Items", "Value"],
        rows,
        align_right={3},
    )


def build_logsummary_csv_bytes(donations, supplies, ledger, id_to_name=None) -> bytes:
    """
    Build a CSV that mirrors your 4 sections:
      - Donations Breakdown (aggregated)
      - Overall Totals (with Total Members)
      - Supply Mission Summary (with Date)
      - Ledger Transactions (with Date)

    Returns CSV data as bytes (UTF-8), ready for discord.File().
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Donations Breakdown (aggregated per name)
    donation_map: dict[str, dict] = {}
    for d in donations:
        nm = d["name"]
        mt = d["materials"]
        if nm not in donation_map:
            donation_map[nm] = {"count": 0, "total": 0.0}
        donation_map[nm]["count"] += 1
        donation_map[nm]["total"] += mt

    sorted_don = sorted(
        donation_map.items(),
        key=lambda kv: (-kv[1]["count"], -kv[1]["total"])
    )

    total_count = sum(v["count"] for v in donation_map.values())
    total_mat = sum(v["total"] for v in donation_map.values())

    # Total members in this date range
    member_names = set()
    for d in donations:
        member_names.add(d["name"])
    for s in supplies:
        member_names.add(s["name"])
    for l in ledger:
        member_names.add(l["name"])
    total_member_count = len(member_names)

    writer.writerow(["Donations Breakdown Table Summary"])
    writer.writerow(["Name", "Donations", "Total Materials Value"])
    for name, stats in sorted_don:
        disp_name = display_name_from_mention(name, id_to_name)
        writer.writerow([
            disp_name,
            stats["count"],
            f"{stats['total']:.2f}",
        ])
    writer.writerow([])

    # Overall totals
    writer.writerow(["Overall Totals"])
    writer.writerow(["Total Donations", "Total Materials Value", "Total Members"])
    writer.writerow([total_count, f"{total_mat:.2f}", total_member_count])
    writer.writerow([])

    # Supply summary WITH Date
    writer.writerow(["Supply Mission Summary"])
    writer.writerow(["Date", "Name", "Supplies Delivered"])
    for s in supplies:
        disp_name = display_name_from_mention(s["name"], id_to_name)
        date_str = s.get("date") or ""
        writer.writerow([date_str, disp_name, f"{s['amount']:.2f}"])
    writer.writerow([])

    # Ledger transactions WITH Date
    writer.writerow(["Ledger Transactions"])
    writer.writerow(["Date", "Name", "Transition", "Amount"])
    for l in ledger:
        disp_name = display_name_from_mention(l["name"], id_to_name)
        transition = "Deposit" if l["transition"] == "Deposit" else "Withdrawal"
        date_str = l.get("date") or ""
        writer.writerow([date_str, disp_name, transition, f"{l['amount']:.2f}"])

    return output.getvalue().encode("utf-8")
