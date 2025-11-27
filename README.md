🎣 MUGIWARAS LOG SUMMONER
The funky Discord bot that turns boring clan logs into juicy, beautiful summaries.
<div align="center">
       __  __           _         _                           
      |  \/  | ___   __| | ___   / \    _ __   __ _ _ __ ___  
      | |\/| |/ _ \ / _` |/ _ \ / _ \  | '_ \ / _` | '_ ` _ \ 
      | |  | | (_) | (_| |  __// ___ \ | |_) | (_| | | | | | |
      |_|  |_|\___/ \__,_|\___/_/   \_\| .__/ \__,_|_| |_| |_|
                                        |_|                   


🌐 Automatically extracts & summarizes:

🦌 Animal Donations

📦 Supply Missions

💰 Ledger Transactions

🎯 Per-user totals, materials, counts & more

✨ Supports real Discord mentions (@DisplayName)
✨ Beautifully aligned Markdown tables
✨ Parses logs from any bot that outputs “Materials added: X”

</div>
🚀 Features
🧩 Smart Log Parsing

Detects donations, supply missions, and ledger activity

Reads logs from text, embeds, .txt/.log files

Ignores junk, separators, and malformed log entries

Fully understands your 4-line log format

💎 Beautiful Output

Automatically generates clean Markdown:

```md
**Donations Breakdown Table Summary**

| Name                   | Donations | Total Materials Value |
| ---------------------- | --------- | --------------------- |
| @Gamer_anz             |        68 |                163.20 |
| @Freddy Fenix [Manager]|        28 |                 66.10 |
```

🧠 Smart Mention Resolver

Turns this:

<@1116155335854534766>


into:

@Freddy Fenix [Manager]


…using server member lookup.

📅 Flexible Commands
Command	Description
!logsummary7	Summary of last 7 days
!logsummary_all	Full log summary (up to 5000 messages)
!logsummary_range YYYY-MM-DD YYYY-MM-DD	Custom date range
!logdebug_range YYYY-MM-DD YYYY-MM-DD	Debug raw log + parser
🔧 How It Works
1️⃣ Reads messages from your log channel

Includes:

Text

Embeds

Attachments

Multi-line logs

2️⃣ Extracts structured data

Donations (Materials added: X)

Supply Missions (Delivered Supplies: X)

Ledger deposits/withdrawals ($X)

3️⃣ Maps Discord IDs → Display Names

Uses privileged intents for full accuracy.

4️⃣ Outputs exactly four tables:

Donations Breakdown Table Summary

Overall Totals

Supply Mission Summary

Ledger Transactions

(As required — no extra fluff.)

🛠️ Setup
🔐 1. Enable Bot Intents

Go to Developer Portal → Your Bot → Bot:

Turn ON:

☑ SERVER MEMBERS INTENT

☑ MESSAGE CONTENT INTENT

⚙️ 2. Environment Variables
TOKEN=your_discord_bot_token
LOG_CHANNEL_ID=123456789012345678

🚀 3. Deploy

Use:

Railway (recommended)

Docker

Local Python

The bot boots instantly and begins answering commands.

🎮 Usage Examples
!logsummary7

!logsummary_range 2025-11-24 2025-11-27

!logsummary_all

🌈 Why This Bot Slaps

✨ Premium-looking output

🔥 Fast & reliable

🧼 Sanitizes odd log formatting

🧠 Smart name detection

💯 Saves clan leaders hours of manual counting

🏴‍☠️ Made for MUGIWARAS

“Because even pirates deserve clean spreadsheets.”
