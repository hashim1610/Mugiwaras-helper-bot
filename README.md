````md
# 🏴‍☠️ Mugiwaras Log Bot

Ahoy, captain!  
This is a Discord bot that sails through your log channel, parses clan activity, and prints **clean, beautiful markdown reports** for donations, supplies, and ledger transactions. Perfect for game clans, RP servers, or any community tracking contributions.  

---

## ✨ Features

- 🔍 **Parses raw log messages** (including embeds & `.txt` / `.log` attachments)
- 💰 **Donation breakdown** per player (count + total materials)
- 📦 **Supply mission summary**
- 🧾 **Ledger transactions** with deposits / withdrawals
- 🧠 Auto-resolves `<@ID>` mentions to usernames in tables
- 📅 **Date range filtering** with both:
  - `!` **prefix commands**
  - `/` **slash commands**
- 📊 Output formatted in **Discord-friendly markdown tables**  
- ✅ Handles long output by **auto-chunking** into multiple messages

---

## 🧱 Tech Stack

- 🐍 Python
- 🤖 [discord.py](https://github.com/Rapptz/discord.py)
- ⏱ `asyncio` + Discord history API
- 🧮 Custom log parser + markdown table formatter

---

## 🚀 Commands Overview

> All dates use the format: `DD-MM-YYYY` (e.g. `01-12-2025`)

### 🔹 Prefix Commands (`!`)

```text
!logsummary_all
    Summarize ALL logs in the log channel.

!logsummary7
    Summarize logs from the last 7 days.

!logsummary_range <start> <end>
    Example: !logsummary_range 01-12-2025 07-12-2025

!logdebug_range <start> <end>
    Debug helper: preview raw logs + parsed counts.
````

#### Section-specific (Prefix)

```text
!logdonations_range <start> <end>
    Only show Donations Breakdown table.

!logtotals_range <start> <end>
    Only show Overall Totals.

!logsupply_range <start> <end>
    Only show Supply Mission summary.

!logledger_range <start> <end>
    Only show Ledger transactions.
```

---

### 🔹 Slash Commands (`/`)

All slash commands mirror the prefix ones:

```text
/logsummary_all
/logsummary7
/logsummary_range      (start_str, end_str)
/logdebug_range        (start_str, end_str)

/logdonations_range    (start_str, end_str)
/logtotals_range       (start_str, end_str)
/logsupply_range       (start_str, end_str)
/logledger_range       (start_str, end_str)
```

Each slash command:

* Reads the configured log channel
* Parses donations, supplies, and ledger
* Sends one or more **markdown-formatted** tables back to the channel

---

## ⚙️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
```

### 2. Install dependencies

```bash
pip install -U "discord.py>=2.0.0"
```

(or add a `requirements.txt` with your versions)

### 3. Environment variables

Set these in your environment / Railway / Docker:

```bash
TOKEN=your_discord_bot_token
LOG_CHANNEL_ID=123456789012345678
```

* `TOKEN` → Your bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
* `LOG_CHANNEL_ID` → Channel where logs / webhooks are being posted

### 4. Run the bot

```bash
python bot.py
```

On startup you should see something like:

```text
✔ Logged in as Mugiwaras Bot#1234 (ID 1443397730624868473)
✔ Globally synced X slash commands
```

---

## 🧩 How It Works (High Level)

* Reads messages from the configured **log channel**
* Extracts:

  * raw text
  * embed title / description / fields
  * `.txt` / `.log` attachment contents
* Uses regex-based parsing to detect:

  * `Donated ... Materials added ...`
  * `Delivered ... Supplies ...`
  * `Deposited to clan ledger` / `Withdrew from clan ledger`
* Maps `<@ID>` → display names and builds structured tables:

  * **Donations Breakdown Summary**
  * **Overall Totals**
  * **Supply Mission Summary**
  * **Ledger Transactions**
* Sends them back using code-block markdown for clean Discord visuals.

---

## 🧭 Example Output

```md
🟥 Donations Breakdown Table Summary

| Name                           | Donations | Total Materials Value |
| ------------------------------ | --------- | --------------------- |
| Gerralt Rivia [Manager]       |        70 |                166.95 |
| Henery James [Watcher]        |        68 |                119.05 |

🟦 Overall Totals

| Total Donations | Total Materials Value |
| --------------- | --------------------- |
|             213 |                468.30 |
```

*(Exact numbers depend on your logs, of course)*

---

## 🧪 Debugging

If your logs don’t parse correctly:

1. Use:

   ```text
   !logdebug_range 01-12-2025 07-12-2025
   ```
2. Check the **preview** of the raw log content.
3. Confirm your log lines match these patterns:

   * `Donated ... Materials added`
   * `Delivered ... Supplies`
   * `Deposited to clan ledger $...`
   * `Withdrew from clan ledger $...`

You can then tweak the regex / parsing logic as needed.

---

## 🏴‍☠️ Credits & License

* Built with ❤️, ☕, and too many test runs.
* Inspired by clan management and log parsing madness.
* License: **MIT** (or whichever you prefer – update this line).

If you like this bot, feel free to ⭐ the repo and share it with your crew!
Fair winds and following seas, captain. ⛵

```
```
