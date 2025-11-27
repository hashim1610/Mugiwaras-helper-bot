Here you go — **a complete, ready-to-copy `README.md` file**, perfectly formatted for GitHub.
Just copy–paste this directly into your repo.

---

# 🎣 **MUGIWARAS LOG SUMMONER**

### *The funky Discord bot that turns boring clan logs into juicy, beautiful summaries.*

<div align="center">

```
       __  __           _         _                           
      |  \/  | ___   __| | ___   / \    _ __   __ _ _ __ ___  
      | |\/| |/ _ \ / _` |/ _ \ / _ \  | '_ \ / _` | '_ ` _ \ 
      | |  | | (_) | (_| |  __// ___ \ | |_) | (_| | | | | | |
      |_|  |_|\___/ \__,_|\___/_/   \_\| .__/ \__,_|_| |_| |_|
                                        |_|                   
```

🌐 **Automatically extracts & summarizes:**

* 🦌 Animal Donations
* 📦 Supply Missions
* 💰 Ledger Transactions
* 👤 Per-user donation counts & totals

✨ **Supports real @DisplayName mentions**
✨ **Beautiful, aligned Markdown tables**
✨ **Fully automated clan log reporting**

</div>

---

## 🚀 Features

### 🧩 Smart Log Parsing

* Detects **donations**, **supplies**, and **ledger** entries
* Supports log bots producing **4-line log blocks**
* Extracts Materials, Supplies, Ledger amounts
* Cleans & normalizes weird data formats

### 💎 Beautiful Output

Every summary is printed as a clean, padded, Markdown table:

````md
```md
**Donations Breakdown Table Summary**

| Name                         | Donations | Total Materials Value |
| ---------------------------- | --------- | --------------------- |
| @Gamer_anz                   |        68 |                163.20 |
| @Freddy Fenix [Manager]      |        28 |                 66.10 |
| @RACCOON                     |        24 |                 51.75 |
```
````

### 🧠 Mention Resolver

* Converts `<@123456789>` → `@DisplayName`
* Removes trailing numeric IDs from log sources
* Filters out junk like `@--------------`

### 📅 Flexible Commands

| Command                                   | Description                       |
| ----------------------------------------- | --------------------------------- |
| `!logsummary7`                            | Summaries for the last 7 days     |
| `!logsummary_all`                         | Use all messages from log channel |
| `!logsummary_range YYYY-MM-DD YYYY-MM-DD` | Custom date range                 |
| `!logdebug_range`                         | See raw logs + parser output      |

---

## 🔧 How It Works

1. Bot reads messages from your log channel
2. Extracts donation/supply/ledger data
3. Resolves Discord IDs → display names
4. Generates **four clean summary tables** in strict order:

   1. Donations Breakdown Table Summary
   2. Overall Totals
   3. Supply Mission Summary
   4. Ledger Transactions

No extra text. No garbage. Just clean data.

---

## 🛠️ Setup

### 1️⃣ Enable Discord Bot Intents

Go to **Discord Developer Portal → Bot** and enable:

* ☑ **MESSAGE CONTENT INTENT**
* ☑ **SERVER MEMBERS INTENT**

### 2️⃣ Add environment variables

```
TOKEN=your_discord_bot_token
LOG_CHANNEL_ID=123456789012345678
```

### 3️⃣ Deploy on…

* Railway
* Docker
* VPS
* Local PC
* A potato (if it runs Python)

---

## 📘 Example Usage

```
!logsummary_range 2025-11-24 2025-11-27
```

or

```
!logsummary7
```

---

## 🌈 Why This Bot Slaps

* Cleanest log summaries in the seven seas 🏴‍☠️
* Fast, accurate, and aesthetically pleasing
* Handles all your clan bookkeeping
* Leaders love it
* Users love seeing their pretty @names

---

## 🏴‍☠️ Built for **MUGIWARAS**

*“Because pirates deserve clean spreadsheets too.”*

---

If you want, I can also generate:

* A matching **logo**
* A **badge section** (Python version, Railway CI, License, etc.)
* A **screenshots** section
* A **fancy animated banner**
* A **Dockerfile** or **Railway template repo**

Just tell me.
