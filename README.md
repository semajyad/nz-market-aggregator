# NZ Market Aggregator

Automated NZ second-hand & retail market monitor with AI-powered NLP query parsing, real-time Telegram notifications, and a clean web dashboard.

## Features

- **7 Platforms**: TradeMe, Facebook Marketplace, Cash Converters, PB Tech, Computer Lounge, Noel Leeming, MightyApe
- **AI Query Parsing**: Google Gemini parses natural language into search parameters
- **Deduplication**: Never notified twice for the same listing
- **Hourly Auto-Scan**: APScheduler runs all active monitors every 60 minutes
- **Telegram Notifications**: Instant push alerts on your phone for new deals
- **Web Dashboard**: Next.js UI to manage monitors and browse the deals feed

## Project Structure

```
nz-market-aggregator/
├── backend/           # Python FastAPI backend
│   ├── main.py        # FastAPI app + routes + scheduler
│   ├── aggregator.py  # Orchestration engine
│   ├── nlp.py         # Gemini NLP parser
│   ├── database.py    # Supabase client
│   ├── notifications.py # Telegram bot
│   ├── scrapers/      # One scraper per platform
│   └── Dockerfile
├── frontend/          # Next.js dashboard
│   └── src/app/
├── supabase/
│   └── schema.sql     # Run this in Supabase SQL editor
└── railway.toml       # Railway deployment config
```

## Prerequisites (Get These First)

### 1. Google Gemini API Key
- Go to: https://aistudio.google.com/app/apikey
- Sign in → Create API Key → Copy it

### 2. Supabase Project
- Go to: https://supabase.com → New Project
- After creation, go to **Settings → API** and copy:
  - Project URL
  - `anon` public key
- Run `supabase/schema.sql` in your project's **SQL Editor**

### 3. Telegram Bot
- Open Telegram → search `@BotFather`
- Send `/newbot` → follow prompts → copy the **Bot Token**
- Search `@userinfobot` → send `/start` → copy your **numeric Chat ID**

## Local Development

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your keys

uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

Open http://localhost:3000

## Deploy to Railway

### Backend Service
1. Push repository to GitHub
2. In Railway: **New Project → Deploy from GitHub**
3. Select your repo, set **Root Directory** to `backend`
4. Railway will auto-detect the Dockerfile
5. Add environment variables in **Railway Variables**:
   ```
   GEMINI_API_KEY=...
   SUPABASE_URL=...
   SUPABASE_ANON_KEY=...
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ALLOWED_ORIGINS=https://your-frontend.railway.app
   ```

### Frontend Service
1. In same Railway project: **New Service → GitHub Repo** (same repo)
2. Set **Root Directory** to `frontend`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend.railway.app
   ```

## Environment Variables Reference

### Backend (`backend/.env`)
| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram user/chat ID |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `SCRAPE_INTERVAL_MINUTES` | Scan interval (default: 60) |

### Frontend (`frontend/.env.local`)
| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/queries` | Create new monitor |
| GET | `/api/queries` | List all monitors |
| DELETE | `/api/queries/{id}` | Pause a monitor |
| GET | `/api/items` | All found items (feed) |
| GET | `/api/queries/{id}/items` | Items for specific monitor |
| POST | `/api/run-now` | Manually trigger a scan |
| POST | `/api/run-all` | Trigger scan for all monitors |
| POST | `/api/notifications/test` | Send test Telegram message |
| GET | `/api/scheduler/status` | View scheduler status |

## Scraper Notes

- **Facebook Marketplace**: Most challenging - uses heavy JavaScript rendering. Results depend on whether FB detects the headless browser. Consider using a residential proxy if results are consistently empty.
- **TradeMe**: Generally reliable HTML scraping.
- **Retailers**: (PB Tech, Computer Lounge, Noel Leeming, MightyApe) - Standard e-commerce scraping. Selectors may need updating if site layouts change.
- **Rate Limiting**: Built-in delays (2-4s between requests) + random jitter to avoid detection.

## Cost Breakdown

| Service | Cost |
|---|---|
| Google Gemini API | **$0** (Free tier: 1,500 req/day) |
| Supabase | **$0** (Free tier: 500MB DB, 2 projects) |
| Telegram Bot API | **$0** (Always free) |
| Railway (your existing access) | **$0 additional** |
| **Total** | **$0/month** |
