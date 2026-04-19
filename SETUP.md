# Wild Bites Voice Bot — GitHub Actions Setup

**Local Docker NOT needed. GitHub builds everything.**
Total time: 20-25 min, mostly waiting.

---

## OVERVIEW

```
Your PC          GitHub              Docker Hub         Pipecat Cloud      Meta WhatsApp
─────────        ────────            ──────────         ─────────────      ──────────────
push code   →    builds Docker   →   stores image   →   deploys bot    ←   routes calls
                 (30MB + tests)                         (answers calls)
```

You push code to GitHub, GitHub Actions does the rest.

---

## PART 1: Accounts & Credentials (10 min)

### 1.1 Docker Hub Access Token

You already have a Docker Hub account. Now we need a **token** (not password).

1. Go to https://hub.docker.com/settings/security
2. Click **New Access Token**
3. Description: `github-actions`
4. Access permissions: **Read, Write, Delete**
5. Click **Generate**
6. **Copy the token** (it shows only once!) — save in notepad temporarily

### 1.2 Pipecat Cloud API Key (Private)

1. Sign up at https://pipecat.daily.co/sign-up (free $5 credits)
2. After login, go to **Settings** → **API Keys**
3. Under **Private API Keys**, click **+ New Key**
4. Name: `github-actions`
5. **Copy the key** (starts with `pk_live_...` or similar) — save in notepad

### 1.3 Pipecat Cloud Public API Key (for webhook verify)

1. Same Settings → API Keys page
2. Under **Public API Keys**, click **+ New Key**  
3. Name: `whatsapp-webhook`
4. **Copy the key** — save in notepad (different from Private key)

### 1.4 Pipecat Cloud Secrets (your .env values)

In Pipecat Cloud dashboard:

1. Go to **Secrets** section (left sidebar)
2. Click **+ New Secret Set**
3. Name: **`wild-bites-secrets`** (exact name matters)
4. Add these 5 secrets:

   | Key | Value |
   |-----|-------|
   | `WHATSAPP_TOKEN` | Your permanent WhatsApp token |
   | `WHATSAPP_PHONE_NUMBER_ID` | `1128408277019776` |
   | `WHATSAPP_APP_SECRET` | From Meta App Settings → Basic |
   | `DEEPGRAM_API_KEY` | From console.deepgram.com |
   | `GROQ_API_KEY` | Your Groq key |

5. **Save**

### 1.5 Image Pull Secret in Pipecat Cloud

Pipecat Cloud needs to pull your Docker image from Docker Hub.

1. In Pipecat Cloud → **Settings** → **Image Pull Secrets**
2. Click **+ New Image Pull Secret**
3. Name: `dockerhub`
4. Registry URL: `https://index.docker.io/v1/`
5. Username: your Docker Hub username
6. Password: the **Docker Hub access token** from step 1.1 (not your Docker password)
7. **Save**

---

## PART 2: GitHub Repository Setup (5 min)

### 2.1 Create GitHub Repo

1. Go to https://github.com/new
2. Repository name: `wild-bites-voice-pcc`
3. Public or Private (either works)
4. **Don't** add README/gitignore/license (we have our own)
5. Create

### 2.2 Add GitHub Secrets

Go to your new repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets (one at a time):

| Name | Value |
|------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username (e.g. `anthonywisac`) |
| `DOCKERHUB_TOKEN` | Docker Hub access token from 1.1 |
| `PCC_API_KEY` | Pipecat Cloud **Private** API key from 1.2 |

### 2.3 Push Code to GitHub

On your PC, PowerShell:

```powershell
cd D:\wild-bites-voice-pcc

# Initialize git (if not done)
git init
git branch -M main

# Add remote (replace anthonywisac-ui with your GitHub username)
git remote add origin https://github.com/anthonywisac-ui/wild-bites-voice-pcc.git

# Add all files
git add .
git status
```

Check `git status` — it should list all 7 files as "new file":
- `.github/workflows/deploy.yml`
- `.gitignore`
- `Dockerfile`
- `bot.py`
- `env.example`
- `pcc-deploy.toml`
- `pyproject.toml`

If any file missing, run `git add -f <filename>` for each.

Then:

```powershell
git commit -m "initial: wild bites voice bot"
git push -u origin main
```

---

## PART 3: Watch GitHub Actions Deploy (5-10 min)

1. Go to your GitHub repo → **Actions** tab
2. You'll see a running workflow: **"Deploy to Pipecat Cloud"**
3. Click on it to watch live logs
4. 4 steps should run green:
   - ✅ Set up QEMU + Buildx
   - ✅ Login to Docker Hub
   - ✅ Build and push Docker image (~5-7 min first time)
   - ✅ Deploy to Pipecat Cloud

If any step fails, **screenshot the error** and I'll fix it.

---

## PART 4: Verify Deployment

### 4.1 Check Pipecat Cloud Dashboard

1. Pipecat Cloud dashboard → **Agents**
2. You should see `wild-bites-voice` with status **Running** (green)
3. Click on it → **Logs** tab → live startup logs

### 4.2 Get Webhook URL

In Pipecat Cloud dashboard → your agent → **Webhooks** section, copy the URL:

```
https://api.pipecat.daily.co/v1/public/webhooks/YOUR_ORG/wild-bites-voice/whatsapp
```

---

## PART 5: Update Meta Webhook (2 min)

1. Meta Developers → App → WhatsApp → Configuration → Webhooks → **Edit**
2. **Callback URL**: paste from 4.2
3. **Verify Token**: paste the **Public API Key** from step 1.3 (NOT `mysecrettoken123`)
4. Click **Verify and Save**
5. Under **Webhook Fields**, make sure **`calls`** is subscribed

---

## PART 6: Test Call

1. Phone → WhatsApp → Meta test number (+1 555-193-0567)
2. Tap **call icon** → voice call
3. Pipecat Cloud dashboard → agent → Logs should show:
   ```
   Starting Wild Bites voice bot
   Caller connected — triggering greeting
   ```
4. Alex greets you in English

---

## FUTURE CHANGES

Any future code change = just `git push` → GitHub Actions rebuilds and redeploys automatically. 
No manual work.

Example:
```powershell
# Edit bot.py to change Alex's personality
notepad bot.py

# Push
git add bot.py
git commit -m "update alex personality"
git push origin main
```

GitHub Actions auto-runs, new version deployed in ~5-10 min.

---

## TROUBLESHOOTING

### Actions step "Build and push" fails with "denied: requested access"
→ `DOCKERHUB_TOKEN` secret wrong. Regenerate token and update GitHub secret.

### Actions step "Deploy to Pipecat Cloud" fails with 401
→ `PCC_API_KEY` secret wrong. Regenerate **Private** key (not Public) in Pipecat Cloud.

### Actions step "Deploy to Pipecat Cloud" fails with 404 "agent not found"  
→ First-time deployment needs UI creation. Go to Pipecat Cloud → Agents → **New Agent**:
- Name: `wild-bites-voice`
- Image: `YOUR_DOCKERHUB_USERNAME/wild-bites-voice:latest`  
- Pull secret: `dockerhub`
- Secret: `wild-bites-secrets`
- Click **Deploy**
- Then re-run GitHub Actions workflow

### Meta webhook verify fails
→ Verify token must be **Public API key** from Pipecat Cloud, NOT `mysecrettoken123`

### Call rings but no voice
→ Pipecat Cloud agent might be scaling. Check status — should be Running. If it's Idle, restart from dashboard.

---

## COSTS

- **Free $5 credits** on Pipecat Cloud signup
- **$0.01 per minute** of active agent running
- `min_agents: 1` in config = 1 instance warm = ~$5-7/month idle cost
- To save cost: change `min_agents: 0` → cold start ~15 sec when call comes
