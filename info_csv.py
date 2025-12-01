# info_csv.py
import csv
import io
from info_table import display_name_from_mention

def build_logsummary_csv_bytes(donations, supplies, ledger, id_to_name=None) -> bytes:
    """
    Build a CSV that mirrors your 4 sections:
      - Donations Breakdown
      - Overall Totals
      - Supply Mission Summary
      - Ledger Transactions

    Returns CSV data as bytes (UTF-8), ready for discord.File().
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # ---------------- Donations Breakdown ----------------
    donation_map = {}
    for d in donations:
        nm = d["name"]
        mt = d["materials"]
        donation_map.setdefault(nm, {"count": 0, "total": 0})
        donation_map[nm]["count"] += 1
        donation_map[nm]["total"] += mt

    sorted_don = sorted(
        donation_map.items(),
        key=lambda kv: (-kv[1]["count"], -kv[1]["total"])
    )

    total_count = sum(v["count"] for v in donation_map.values())
    total_mat = sum(v["total"] for v in donation_map.values())

    writer.writerow(["Donations Breakdown Table Summary"])
    writer.writerow(["Name", "Donations", "Total Materials Value"])
    for name, stats in sorted_don:
        disp_name = display_name_from_mention(name, id_to_name)
        writer.writerow([
            disp_name,
            stats["count"],
            f"{stats['total']:.2f}",
        ])
    writer.writerow([])  # blank line between sections

    # ---------------- Overall Totals ----------------
    writer.writerow(["Overall Totals"])
    writer.writerow(["Total Donations", "Total Materials Value"])
    writer.writerow([total_count, f"{total_mat:.2f}"])
    writer.writerow([])

    # ---------------- Supply Mission Summary ----------------
    writer.writerow(["Supply Mission Summary"])
    writer.writerow(["Name", "Supplies Delivered"])
    for s in supplies:
        disp_name = display_name_from_mention(s["name"], id_to_name)
        writer.writerow([disp_name, f"{s['amount']:.2f}"])
    writer.writerow([])

    # ---------------- Ledger Transactions ----------------
    writer.writerow(["Ledger Transactions"])
    writer.writerow(["Name", "Transition", "Amount"])
    for l in ledger:
        disp_name = display_name_from_mention(l["name"], id_to_name)
        transition = "Deposit" if l["transition"] == "Deposit" else "Withdrawal"
        writer.writerow([disp_name, transition, f"{l['amount']:.2f}"])

    return output.getvalue().encode("utf-8")
