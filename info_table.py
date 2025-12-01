# info_table.py
import re

def normalize_number(num_str):
    return float(num_str.replace(",", ".").strip())


# ---------------- NAME HANDLING ----------------

def clean_discord_name(discord_part, lines, idx):
    """
    Extract meaningful name from log line.
    Prefer <@ID> → resolved display name.
    """
    s = discord_part.replace("**", "").replace("`", "").strip()

    # Raw mention in this line
    m = re.search(r"<@!?(\d+)>", s)
    if m:
        return "<@%s>" % m.group(1)

    # Pattern like: @Name ... ID
    tokens = s.split()
    if tokens and tokens[-1].isdigit():
        return "<@%s>" % tokens[-1]

    # Look ahead for name or ID
    for k in range(idx + 1, min(idx + 4, len(lines))):
        nxt = lines[k].replace("**", "").replace("`", "").strip()
        if not nxt:
            continue

        m2 = re.search(r"<@!?(\d+)>", nxt)
        if m2:
            return "<@%s>" % m2.group(1)

        parts = nxt.split()
        if parts and parts[-1].isdigit():
            return "<@%s>" % parts[-1]

        # fallback textual name
        name = " ".join(parts)
        return name

    # Final fallback: use raw cleaned text
    return s or None


def display_name_from_mention(name, id_to_name):
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

def extract_number_after_marker(text, marker):
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


def extract_number_after_char(text, ch_marker):
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

def parse_log(raw_log):
    """
    Parse the raw log text into three lists:
      - donations: [{name, materials, date}]
      - supplies: [{name, amount, date}]
      - ledger: [{name, transition, amount, date}]
    Date is derived from special lines: "__DATE__ YYYY-MM-DD"
    injected by chat_read.build_raw_log_from_channel.
    """
    lines = raw_log.splitlines()
    n = len(lines)

    donations = []
    supplies = []
    ledger = []

    current_date = None

    i = 0
    while i < n:
        line = lines[i].strip()

        # Date marker from chat_read
        if line.startswith("__DATE__ "):
            current_date = line[len("__DATE__ "):].strip()
            i += 1
            continue

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

        # Supplies
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
                    })

        # Ledger
        if ("Deposited to clan ledger" in line) or ("Withdrew from clan ledger" in line):
            trans = "Deposit" if "Deposited" in line else "Withdrawal"
            amt = extract_number_after_char(line, "$")

            if amt is not None:
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

def make_table(headers, rows, align_right=None):
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
      3: Ledger transactions (WITH date)
    Titles are plain text so they don't show raw asterisks inside ```md blocks.
    """
    sections = []

    # Donations summary (aggregated)
    donation_map = {}
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

    # ✅ Total members in this date range:
    # We deduplicate by the raw "name" field (usually <@ID>)
    member_names = set()
    for d in donations:
        member_names.add(d["name"])
    for s in supplies:
        member_names.add(s["name"])
    for l in ledger:
        member_names.add(l["name"])
    total_member_count = len(member_names)

    # 1) Donations table
    sec1_lines = []
    sec1_lines.append("🟥 Donations Breakdown Table Summary")

    donation_rows = [
        [
            display_name_from_mention(name, id_to_name),
            stats["count"],
            "%.2f" % stats["total"],
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

    # 2) Overall Totals (now with Total Member Count)
    sec2_lines = []
    sec2_lines.append("🟦 Overall Totals")
    sec2_lines.append(
        make_table(
            ["Total Member Count" ,"Total Donations", "Total Materials Value"],
            [[total_member_count,total_count, "%.2f" % total_mat]],
            align_right={0, 1, 2}
        )
    )
    sections.append("\n\n".join(sec2_lines))

    # 3) Supplies (with Date column)
    sec3_lines = []
    sec3_lines.append("🟩 Supply Mission Summary")

    supply_rows = []
    for s in supplies:
        date_str = s.get("date") or ""
        name = display_name_from_mention(s["name"], id_to_name)
        supply_rows.append([date_str, name, "%.2f" % s["amount"]])

    sec3_lines.append(
        make_table(
            ["Date", "Name", "Supplies Delivered"],
            supply_rows,
            align_right={2}
        )
    )
    sections.append("\n\n".join(sec3_lines))

    # 4) Ledger (with Date column)
    sec4_lines = []
    sec4_lines.append("🟨 Ledger Transactions")
    ledger_rows = []
    for l in ledger:
        date_str = l.get("date") or ""
        base_name = display_name_from_mention(l["name"], id_to_name)
        transition = "⬆️ Deposit" if l["transition"] == "Deposit" else "⬇️ Withdrawal"
        ledger_rows.append(
            [date_str, base_name, transition, "$%.2f" % l["amount"]]
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

