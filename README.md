# 🎣 MUGIWARAS LOG SUMMONER

### *The funky Discord bot that turns boring clan logs into juicy, beautiful summaries.*

<div align="center">



🌐 **Automatically extracts & summarizes:**

* 🧱 Materials Donations
* 📦 Supply Missions
* 💰 Ledger Transactions
* 👤 Per-user donation counts & totals

✨ **Supports real @DisplayName mentions**  
✨ **Beautiful, aligned Markdown tables**  
✨ **Prefix `!` *and* slash `/` commands**

</div>

---

## ✨ Features

### 🧩 Smart Log Parsing

* Detects **donations**, **supplies**, and **ledger** entries
* Supports log bots producing multi-line log blocks
* Extracts:
  * Materials donated (`Materials added`)
  * Supplies delivered (`Delivered Supplies`)
  * Dollar amounts in ledger (`$123.45`)
* Cleans & normalizes weird numeric formats like `1,23` → `1.23`

---

### 💎 Beautiful Output

Every summary is printed as a clean Markdown table, chunked safely under Discord’s character limit:

````md
```md
**🟥 Donations Breakdown Table Summary**

| Name                         | Donations | Total Materials Value |
| ---------------------------- | --------- | --------------------- |
| Gamer_anz                    |        68 |                163.20 |
| Freddy Fenix [Manager]       |        28 |                 66.10 |
| RACCOON                      |        24 |                 51.75 |


Sections are always generated in this order:

1. 🟥 **Donations Breakdown Table Summary**  
2. 🟦 **Overall Totals**  
3. 🟩 **Supply Mission Summary**  
4. 🟨 **Ledger Transactions** (with `$` in the Amount column)

---

### 🧠 Mention Resolver

* Converts `<@123456789>` → `DisplayName`
* Uses live guild member list to resolve IDs
* Leaves normal text names untouched
* Works even if the log contains weird trailing IDs

---

### 🧾 Command Overview

The bot supports **both prefix `!` commands** and **slash `/` commands**.

#### ⌨️ Prefix Commands (`!`)

All date ranges use **`DD-MM-YYYY`**.

**Summary commands**

| Command                                                | Description                                |
| ------------------------------------------------------ | ------------------------------------------ |
| `!logsummary7`                                         | Full summary for the last 7 days          |
| `!logsummary_all`                                      | Full summary using all logs in the channel |
| `!logsummary_range DD-MM-YYYY DD-MM-YYYY`              | Full summary for a custom date range      |
| `!logdebug_range DD-MM-YYYY DD-MM-YYYY`                | Raw log preview + parse stats + summary   |

**Section-only commands (cleaner chat)**

These only print *one* of the four sections:

| Command                                                | Shows only…                    |
| ------------------------------------------------------ | ------------------------------ |
| `!logdonations_range DD-MM-YYYY DD-MM-YYYY`            | 🟥 Donations Breakdown         |
| `!logtotals_range DD-MM-YYYY DD-MM-YYYY`               | 🟦 Overall Totals              |
| `!logsupply_range DD-MM-YYYY DD-MM-YYYY`               | 🟩 Supply Mission Summary      |
| `!logledger_range DD-MM-YYYY DD-MM-YYYY`               | 🟨 Ledger Transactions (with $)|

---

#### ⚡ Slash Commands (`/`)

Same features as above, but as Discord-native slash commands.

**Full summaries**

- `/logsummary_all`
- `/logsummary7`
- `/logsummary_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`
- `/logdebug_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`

**Section-only summaries**

- `/logdonations_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`
- `/logtotals_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`
- `/logsupply_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`
- `/logledger_range start_str: DD-MM-YYYY end_str: DD-MM-YYYY`

> Prefix and slash commands coexist. You can keep using `!` while slowly moving your users to `/`.

---

## 🔧 How It Works

1. Bot reads all messages & embeds from your configured **log channel**
2. For each message, it extracts:
   - Text content
   - Embed title, description, and fields
   - Attached `.txt` / `.log` files
3. It parses lines to detect:
   - **Donations** – `"Donated"` + `"Materials added ..."`
   - **Supplies** – `"Delivered Supplies ..."`
   - **Ledger** – `"Deposited to clan ledger"` / `"Withdrew from clan ledger"` + `$amount`
4. It maps Discord IDs → display names using the guild member list
5. It aggregates by user and renders Markdown tables

No manual Excel. No copy–paste pain. Just type a command and get a neat breakdown.

---

## 🛠️ Setup

### 1️⃣ Requirements

- Python **3.10+** recommended
- `discord.py` **2.x** (for slash commands support)

Install dependencies:

```bash
pip install -U discord.py
```

### 2️⃣ Discord Bot Setup

In the **Discord Developer Portal**:

1. Go to **Bot → Privileged Gateway Intents**:
   - ☑ **SERVER MEMBERS INTENT**
   - ☑ **MESSAGE CONTENT INTENT**
2. Under **OAuth2 → URL Generator**:
   - Scopes:
     - ☑ `bot`
     - ☑ `applications.commands`
   - Bot Permissions: at least:
     - Read Messages / View Channels
     - Send Messages
     - Read Message History

Invite the bot to your server using the generated URL.

### 3️⃣ Environment Variables

Set these (e.g. in Railway / Docker / `.env`):

```bash
TOKEN=your_discord_bot_token
LOG_CHANNEL_ID=123456789012345678
```

- `TOKEN` – your bot token from the Developer Portal  
- `LOG_CHANNEL_ID` – the numeric ID of the channel where your clan logs are posted

---

## 🚀 Running the Bot

Local:

```bash
python bot.py
```

Railway / other hosting:

- Add your repo
- Set `TOKEN` and `LOG_CHANNEL_ID` as environment variables
- Use `python bot.py` as the start command

---

## 📘 Example Usage

### Full summaries

```text
!logsummary7
!logsummary_all
!logsummary_range 01-11-2025 07-11-2025
```

or as slash commands:

```text
/logsummary7
/logsummary_range start_str: 01-11-2025 end_str: 07-11-2025
```

### Section-only (cleaner chat)

```text
!logdonations_range 01-11-2025 07-11-2025
!logledger_range 01-11-2025 07-11-2025
```

```text
/logsupply_range start_str: 01-11-2025 end_str: 07-11-2025
/logtotals_range start_str: 01-11-2025 end_str: 07-11-2025
```

---

## 🧪 Debugging

If parsing looks off, use:

```text
!logdebug_range 01-11-2025 07-11-2025
```

or:

```text
/logdebug_range start_str: 01-11-2025 end_str: 07-11-2025
```

This will show:

- How many characters of raw log were fetched
- A text preview of the raw log
- Parsed counts: donations / supplies / ledger
- The final tables

---

## 🌈 Why This Bot Slaps

- Cleanest log summaries in the seven seas 🏴‍☠️  
- Leaders get instant clarity on donations & supplies  
- Members see their contributions with proper names  
- Ledger amounts show with `$` so it looks like a real finance sheet  
- Supports both old-school `!` and modern `/` commands

---

## 🏴‍☠️ Built for **MUGIWARAS**

> *“Because pirates deserve clean spreadsheets too.”*
```
