# 🚀 Skylark BI Agent — Railway Deployment Guide

## Why Railway?

| | Railway | Render | Fly.io |
|---|---|---|---|
| Free tier | $5/mo credit (≈500hrs) | Free (cold starts) | Free allowance |
| Cold starts | ✅ None | ❌ Yes (15min idle) | ✅ None |
| Python support | ✅ Auto-detect | ✅ Yes | ✅ Yes |
| Setup complexity | ⭐ Easiest | Easy | Complex |
| Public HTTPS URL | ✅ Instant | ✅ Instant | ✅ Yes |

**Railway** is recommended — no cold starts, auto-detects Python, generates a public HTTPS URL in < 2 minutes.

---

## Step 1 — Push Code to GitHub

If you don't have git set up yet:

```powershell
# In your project folder
git init
git add -A
git commit -m "Initial commit — Skylark BI Agent"
```

Then create a new **private** GitHub repo at [github.com/new](https://github.com/new), then:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/skylark-ai-agent.git
git push -u origin main
```

> [!IMPORTANT]
> The `.gitignore` already excludes `.env`. Your API keys will NOT be uploaded. You'll add them in Railway's dashboard.

---

## Step 2 — Deploy on Railway

1. Go to **[railway.app](https://railway.app)** → Sign up with GitHub (free)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `skylark-ai-agent` repository
4. Railway auto-detects Python and starts building

**That's it for the build.** Now add your environment variables:

---

## Step 3 — Add Environment Variables

In your Railway project → click the service → **"Variables"** tab → add each:

| Variable | Value | Required? |
|---|---|---|
| `GROQ_API_KEY` | Your Groq key | ✅ Yes |
| `MONDAY_API_TOKEN` | Your Monday.com token | ✅ Yes |
| `DEALS_BOARD_ID` | Your deals board ID | ✅ Yes |
| `WORKORDERS_BOARD_ID` | Your work orders board ID | ✅ Yes |
| `DATA_REFRESH_INTERVAL` | `300` | Optional |

> [!TIP]
> Get your free Groq key at [console.groq.com](https://console.groq.com) — takes 30 seconds.

---

## Step 4 — Get Your Public URL

After deploy completes:
- Railway → your service → **"Settings"** tab → **"Domains"**
- Click **"Generate Domain"** → you get a URL like `https://skylark-ai-agent.up.railway.app`

Share this link — anyone can access the agent without any local setup! ✅

---

## Re-deploying After Code Changes

```powershell
git add -A
git commit -m "your change description"
git push
```

Railway auto-deploys on every push to `main`. Zero downtime.

---

## Monitoring

- Railway dashboard → **"Logs"** tab — real-time server logs
- **`/health`** endpoint — `https://your-app.up.railway.app/health` shows data status
- **`/docs`** endpoint — interactive Swagger API explorer

---

## Cost Estimate

| Usage | Monthly Cost |
|---|---|
| 24/7 always-on | ~$3-5/mo (within free $5 credit) |
| Shared/demo use | Free |

Railway's free $5/month credit covers a small always-on FastAPI app with room to spare.
