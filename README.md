# arXiv Digest

Automated daily arXiv paper digest with semantic ranking and LLM summaries, delivered to your inbox.

## Table of Contents

- [Overview](#overview)
- [Why This Over the arXiv Mailing List?](#why-this-over-the-arxiv-mailing-list)
- [How It Works](#how-it-works)
- [Example Output](#example-output)
- [Choose Your LLM](#choose-your-llm)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup Guide](#detailed-setup-guide)
  - [Step 1: Install Docker](#step-1-install-docker)
  - [Step 2: Find Your Docker Group GID](#step-2-find-your-docker-group-gid)
  - [Step 3: Clone and Configure](#step-3-clone-and-configure)
  - [Step 4: Set Up Gmail App Password](#step-4-set-up-gmail-app-password)
  - [Step 5: Set Up Google Cloud OAuth2](#step-5-set-up-google-cloud-oauth2)
  - [Step 6: Set Up Your LLM](#step-6-set-up-your-llm)
  - [Step 7: Create Your Google Sheet](#step-7-create-your-google-sheet)
  - [Step 8: Deploy](#step-8-deploy)
  - [Step 9: Import the Workflow](#step-9-import-the-workflow)
  - [Step 10: Configure n8n Credentials](#step-10-configure-n8n-credentials)
  - [Step 11: Update the Workflow Nodes](#step-11-update-the-workflow-nodes)
  - [Step 12: Test](#step-12-test)
  - [Step 13: Verify Automation](#step-13-verify-automation)
- [Configuration Reference](#configuration-reference)
- [Flask Scraper API Reference](#flask-scraper-api-reference)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [Cost Estimate](#cost-estimate)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

arXiv Digest is a self-hosted system that automatically:

1. **Scrapes** new papers from your chosen arXiv categories daily
2. **Ranks** them by semantic similarity to your research keywords using [SPECTER2](https://huggingface.co/allenai/specter2_base) embeddings
3. **Summarizes** the top papers using an LLM of your choice, personalized to your interests
4. **Emails** a formatted HTML digest to each subscriber

It supports **multiple subscribers**, each with their own categories, keywords, and email address: all managed from a simple Google Sheet. Add a colleague by adding a row.

### Key Features

- **Any arXiv subfield**: configure categories for physics, CS, math, biology, economics, or any combination
- **Semantic ranking**: SPECTER2 (trained on scientific papers) ranks papers by relevance to your specific keywords, not just category
- **LLM summaries**: structured summaries with key results, methods, findings, and relevance to your interests
- **Flexible LLM backend**: use a cloud API (Anthropic, OpenAI, etc.) or run a local model with Ollama
- **Multi-subscriber**: one deployment serves an entire lab or reading group
- **Cool emails**: responsive HTML with dark mode support, relevance badges, and paper links
- **No GPU required**: SPECTER2 runs on CPU; LLM can be cloud-based or local

---

## Why This Over the arXiv Mailing List?

arXiv provides a [built-in email alert service](https://info.arxiv.org/help/subscribe.html) that sends daily listings of new submissions. It's a good starting point, but it has significant limitations for researchers who follow active categories. Here's how arXiv Digest compares:

| Feature | arXiv Mailing List | arXiv Digest |
|---------|-------------------|--------------|
| **Paper discovery** | All new papers in subscribed categories, unranked | Semantically ranked by relevance to your specific keywords |
| **Volume** | Every paper in the category (can be 50-100+/day for popular categories like cs.AI) | Top N most relevant papers (default: 10) |
| **Summaries** | Titles and abstracts only, no summaries | LLM-generated structured summaries (key result, method, findings, relevance) |
| **Personalization** | Category-level only | Keyword-level: each subscriber gets papers ranked to their specific interests |
| **Format** | Plain text ASCII email | Responsive HTML with dark mode, relevance badges, direct PDF/abstract links |
| **Multi-user** | Each person manages their own subscription | One deployment serves everyone; subscribers managed in a shared Google Sheet |
| **Keyword filtering** | No keyword filtering: you get everything in the category | SPECTER2 semantic embeddings rank papers against your research keywords |
| **Reading time** | Must scan all titles/abstracts yourself | Pre-ranked and summarize: read the top 10 summaries in minutes |
| **Setup** | Send an email to subscribe | Self-hosted with Docker (one-time setup, ~30 minutes) |
| **Cost** | Free | Free infrastructure + ~$0.02-0.05/day for cloud LLM (or $0 with local Ollama) |
| **Hosting** | Managed by arXiv | Self-hosted (you control everything) |
| **Customization** | None | Fully customizable: change models, prompts, schedule, paper count, email format |

**When to use the arXiv mailing list:** You follow a niche category with low volume (< 10 papers/day) and don't mind scanning titles yourself.

**When to use arXiv Digest:** You follow active categories, want papers ranked to your specific interests, and want to read summaries instead of abstracts.

---

## How It Works

```
                         arXiv Digest System Architecture
  ═══════════════════════════════════════════════════════════════════════════

  TRIGGER (Daily cron or manual)
      │
      ▼
  ┌────────────────────┐     ┌────────────────────┐     ┌──────────────────┐
  │  n8n Workflow      │     │  Flask Scraper     │     │  External APIs   │
  │  (Orchestrator)    │     │  (SPECTER2 + CPU)  │     │                  │
  │                    │     │                    │     │                  │
  │ 1. Start Flask ────┼────>│  Container starts  │     │                  │
  │    container       │     │                    │     │                  │
  │                    │     │                    │     │                  │
  │ 2. Read subscriber─┼──────────────────────────┼────>│  Google Sheets   │
  │    list            │<─────────────────────────┼─────│  (subscribers)   │
  │                    │     │                    │     │                  │
  │ 3. Scrape papers ──┼───> │  Fetch RSS feeds ─┼─────>│  arXiv RSS       │
  │    (all categories)│     │  Fetch metadata  ──┼────>│  arXiv API       │
  │                    │<────┼  Compute SPECTER2  │     │                  │
  │                    │     │  embeddings (CPU)  │     │                  │
  │                    │     │                    │     │                  │
  │ 4. Per subscriber: │     │                    │     │                  │
  │    Score papers ───┼────>│  Cosine similarity │     │                  │
  │    by keywords     │<────┼  vs keyword embed  │     │                  │
  │                    │     │                    │     │                  │
  │ 5. Summarize top ──┼──────────────────────────┼────>│  LLM             │
  │    papers          │<─────────────────────────┼─────│  (Cloud or Local)│
  │                    │     │                    │     │                  │
  │ 6. Format HTML     │     │                    │     │                  │
  │    email digest    │     │                    │     │                  │
  │                    │     │                    │     │                  │
  │ 7. Send email ─────┼──────────────────────────┼────>│  Gmail SMTP      │
  │                    │     │                    │     │                  │
  │ 8. Cleanup cache ──┼────>│  Free memory       │     │                  │
  │ 9. Stop Flask ─────┼────>│  Container stops   │     │                  │
  └────────────────────┘     └────────────────────┘     └──────────────────┘

  ═══════════════════════════════════════════════════════════════════════════
  Docker Compose runs both services. The Flask container is started on-demand
  by n8n (via Docker socket) and stopped after the digest completes to save RAM.
```

**Step-by-step:**

1. **Trigger**: The workflow runs daily on a cron schedule (default: 5:10 AM) or manually
2. **Start Flask**: n8n starts the Flask scraper container via the Docker socket API
3. **Read subscribers**: Fetches the subscriber list from your Google Sheet (name, email, keywords, categories)
4. **Scrape**: Flask fetches RSS feeds for all unique categories, retrieves full paper metadata from the arXiv API, and computes SPECTER2 embeddings for every abstract
5. **Score**: For each subscriber, Flask computes cosine similarity between their keyword embedding and each paper's abstract embedding, returning the top 10 most relevant papers
6. **Summarize**: Each top paper is sent to the LLM with a personalized prompt including the subscriber's name and research interests
7. **Format**: Summaries are assembled into a responsive HTML email with metrics, relevance badges, and paper links
8. **Send**: The digest is emailed to the subscriber via Gmail SMTP
9. **Cleanup**: Flask frees cached papers and embeddings from memory, then n8n stops the Flask container

---

## Example Output

Each subscriber receives an HTML email containing:

- **Header** with their name and the date
- **Profile section** showing their configured categories and keywords
- **Metrics grid**: papers published, papers in their categories, top papers selected, timing
- **Paper cards** for each top paper, including:
  - Rank number and relevance score badge (e.g., "87.3%")
  - Title (linked to arXiv), authors, publication date
  - Abstract and PDF links
  - LLM-generated summary with key result, method, findings, and personalized relevance note
- **Footer** with pipeline statistics

The email supports both light and dark mode via CSS `prefers-color-scheme`.

---

## Choose Your LLM

The summarization step is modular, so you can use a cloud API or a local model. Choose the approach that fits your needs:

### Option A: Cloud API (Recommended for most users)

Use a hosted API like Anthropic (Claude) or OpenAI (GPT). The included workflow is pre-configured for Anthropic.

| Pros | Cons |
|------|------|
| No GPU or extra hardware needed | Costs ~$0.02-0.05/day |
| Fast, high-quality summaries | Requires an API key and internet access |
| Zero maintenance | Paper abstracts are sent to a third-party API |
| Works on any machine (even a Raspberry Pi) | |

**Getting started:**

1. Sign up at [console.anthropic.com](https://console.anthropic.com) (or your preferred provider)
2. Create an API key
3. In the n8n workflow, the **"Summarize Paper"** node is already connected to a **"Claude Model"** node
4. Add your Anthropic credential in n8n and select it in the Claude Model node

See [Step 6A](#step-6a-cloud-api-anthropic) for the full walkthrough.

### Option B: Local Model with Ollama

Run an open-source model locally using [Ollama](https://ollama.com). Good for privacy or if you already have GPU hardware.

| Pros | Cons |
|------|------|
| Completely free after setup | Requires a capable machine (GPU recommended) |
| Full privacy, nothing leaves your network | Slower than cloud APIs without a GPU |
| No API keys or accounts needed | You manage model updates and maintenance |
| Works offline | Summarization quality depends on model choice |

**Getting started:**

1. Install Ollama on your server:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a model suitable for summarization:
   ```bash
   # Good balance of quality and speed (requires ~20 GB RAM/VRAM)
   ollama pull qwen2.5:32b-instruct-q4_K_M

   # Lighter alternative (~8 GB RAM/VRAM)
   ollama pull qwen2.5:14b-instruct-q4_K_M

   # Minimal option (~4 GB RAM/VRAM)
   ollama pull qwen2.5:7b-instruct-q4_K_M
   ```

3. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

4. In the n8n workflow, you need to swap the LLM node:
   - Delete the **"Claude Model"** node
   - Add a new **"Ollama Model"** node (search for "Ollama" in the n8n node panel)
   - Set the model name to the one you pulled (e.g., `qwen2.5:32b-instruct-q4_K_M`)
   - Create an Ollama credential in n8n pointing to `http://host.docker.internal:11434` (this lets the n8n container reach Ollama on the host)
   - Connect the Ollama Model node to the **"Summarize Paper"** node's `ai_languageModel` input

See [Step 6B](#step-6b-local-model-with-ollama) for the full walkthrough.

---

## Prerequisites

- A **Linux server** (Ubuntu 22.04+ recommended) or any machine that can run Docker
- **Docker Engine** and **Docker Compose** plugin (not Docker Desktop)
- A **Google Cloud** project (free tier is fine for Google Sheets OAuth2)
- A **Gmail** account with 2-Step Verification enabled (for App Password)
- An **LLM backend**: either a cloud API key or Ollama installed locally
- **~2 GB RAM** minimum (SPECTER2 uses ~500 MB when loaded)
  - If using Ollama locally, add RAM/VRAM for the model (4-20+ GB depending on model size)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sjbevins/n8n-arxiv-digest.git
cd n8n-arxiv-digest

# 2. Configure
cp .env.example .env
# Edit .env with your values (see Detailed Setup Guide)

# 3. Deploy
docker compose up -d

# 4. Import workflow
docker exec -i n8n n8n import:workflow --input=/dev/stdin < workflow/arxiv-digest-v10.json

# 5. Configure credentials in n8n UI at http://YOUR_IP:5678
#    Then activate the workflow
```

For the full walkthrough (including Google OAuth2 setup, Gmail App Password, etc.), see the [Detailed Setup Guide](#detailed-setup-guide) below.

---

## Detailed Setup Guide

### Step 1: Install Docker

Install Docker Engine on Ubuntu (not Docker Desktop):

```bash
# Install prerequisites
sudo apt install -y ca-certificates curl

# Add Docker's GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Add your user to the docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run hello-world
```

For other distributions, see the [official Docker docs](https://docs.docker.com/engine/install/).

---

### Step 2: Find Your Docker Group GID

The n8n container needs access to the Docker socket to start and stop the Flask scraper container. This requires knowing the GID of the `docker` group on your system:

```bash
getent group docker | cut -d: -f3
```

This will output a number like `988`, `999`, or `998`. Note it down, you'll need it for `.env`.

---

### Step 3: Clone and Configure

```bash
git clone https://github.com/sjbevins/n8n-arxiv-digest.git
cd n8n-arxiv-digest
cp .env.example .env
```

Edit `.env` and fill in the values:

```bash
nano .env  # or your preferred editor
```

| Variable | How to find it |
|----------|---------------|
| `N8N_BASIC_AUTH_USER` | Choose any username for the n8n login page |
| `N8N_BASIC_AUTH_PASSWORD` | Choose a strong password |
| `WEBHOOK_URL` | Your LAN IP + `.nip.io` suffix (see below) |
| `TZ` | Your timezone, e.g. `America/New_York`, `Europe/London` |
| `DOCKER_GID` | Output from Step 2 |

**Finding your WEBHOOK_URL:**

```bash
# Get your LAN IP
hostname -I | awk '{print $1}'
# Example output: 192.168.1.50
```

Then set `WEBHOOK_URL=http://192.168.1.50.nip.io:5678/`

The `.nip.io` suffix is a free wildcard DNS service, `192.168.1.50.nip.io` resolves to `192.168.1.50`. This is needed because Google's OAuth2 won't accept bare IP addresses as redirect URIs.

---

### Step 4: Set Up Gmail App Password

You need a Gmail App Password so n8n can send emails via SMTP. Your regular Gmail password will not work.

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Sign in with the Gmail account you want to send digest emails from
3. Under **"How you sign in to Google"**, click **"2-Step Verification"**
   - If it's not enabled, follow the prompts to turn it on (required for App Passwords)
4. Go to [App Passwords](https://myaccount.google.com/apppasswords)
5. Enter app name: `n8n`
6. Click **"Create"**
7. Copy the **16-character password** (e.g., `abcd efgh ijkl mnop`)
   - Save this somewhere safe, you won't see it again
   - You'll enter it in n8n later (Step 10)

---

### Step 5: Set Up Google Cloud OAuth2

This is the most involved step. n8n needs OAuth2 credentials to read your Google Sheet subscriber list.

#### 5a. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Sign in with the same Google account that will own the subscriber Google Sheet
3. Click the project dropdown in the top-left (next to "Google Cloud" logo)
4. Click **"New Project"**
5. Name it `arxiv-digest` (or whatever you like)
6. Click **"Create"**
7. Make sure the new project is selected in the dropdown

#### 5b. Enable APIs

1. In the search bar, type **"Google Sheets API"** → click the result → click **"Enable"**
2. Go back to the search bar, type **"Google Drive API"** → click the result → click **"Enable"**

#### 5c. Configure OAuth Consent Screen

1. In the left sidebar: **APIs & Services** → **OAuth consent screen**
2. Select **"External"** → click **"Create"**
3. Fill in:
   - **App name:** `Arxiv Digest`
   - **User support email:** select your email
   - **Developer contact information:** enter your email
4. Click **"Save and Continue"**
5. On the **Scopes** page:
   - Click **"Add or Remove Scopes"**
   - Search for and check:
     - `https://www.googleapis.com/auth/spreadsheets`
     - `https://www.googleapis.com/auth/drive.readonly`
   - Click **"Update"** → **"Save and Continue"**
6. On the **Test Users** page:
   - Click **"+ Add Users"**
   - Enter your Google account email
   - Click **"Add"** → **"Save and Continue"**
7. Review the summary → click **"Back to Dashboard"**

> **Important:** While the app is in "Testing" mode, only the test users you added can authorize it. This is fine for personal use.

#### 5d. Create OAuth2 Credentials

1. In the left sidebar: **APIs & Services** → **Credentials**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. **Application type:** select **"Web application"**
4. **Name:** `n8n`
5. Under **"Authorized redirect URIs"**, click **"+ Add URI"** and enter:
   ```
   http://YOUR_LAN_IP.nip.io:5678/rest/oauth2-credential/callback
   ```
   Replace `YOUR_LAN_IP` with your actual LAN IP (same one from your `WEBHOOK_URL`).
6. Click **"Create"**
7. A popup shows your **Client ID** and **Client Secret**, copy both
   - You'll enter these in n8n later (Step 10)

---

### Step 6: Set Up Your LLM

Choose one of the two options below.

#### Step 6A: Cloud API (Anthropic)

1. Go to [Anthropic Console](https://console.anthropic.com)
2. Create an account if you don't have one
3. Add a payment method (usage-based billing)
4. Go to **API Keys** → **Create Key**
5. Copy the key (starts with `sk-ant-...`)
   - You'll enter it in n8n later (Step 10)

The included workflow is pre-configured to use Claude Haiku 4.5 (fast and inexpensive). You can change the model later: see [Changing the LLM Model](#changing-the-llm-model).

> **Using a different API provider?** n8n has built-in nodes for OpenAI, Google Gemini, Azure OpenAI, Mistral, and others. You can swap the LLM node in the workflow to use any supported provider. The rest of the pipeline stays the same.

#### Step 6B: Local Model with Ollama

1. Install Ollama on your server (the host machine, not inside Docker):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a model. Choose based on your hardware:

   | Model | RAM/VRAM Required | Quality | Speed |
   |-------|-------------------|---------|-------|
   | `qwen2.5:32b-instruct-q4_K_M` | ~20 GB | Best | Slow on CPU |
   | `qwen2.5:14b-instruct-q4_K_M` | ~8 GB | Good | Moderate |
   | `qwen2.5:7b-instruct-q4_K_M` | ~4 GB | Acceptable | Fast |
   | `llama3.1:8b-instruct-q4_K_M` | ~5 GB | Good | Fast |

   ```bash
   ollama pull qwen2.5:14b-instruct-q4_K_M
   ```

3. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   # Should return a JSON list of your models
   ```

4. You'll configure the n8n workflow node in Step 11.

---

### Step 7: Create Your Google Sheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it whatever you like (e.g., "ArXiv Digest")
3. Set up the column headers in Row 1:

| Name | Email | Keywords | Categories | Status |
|------|-------|----------|------------|--------|

4. Add subscriber rows. Example:

| Name | Email | Keywords | Categories | Status |
|------|-------|----------|------------|--------|
| Jane Doe | jane@example.com | deep learning, transformers, NLP, language models | cs.AI, cs.CL, cs.LG | active |
| Bob Smith | bob@example.com | quantum computing, error correction, topological codes | quant-ph, cond-mat.str-el | active |

**Column details:**

- **Name**: Used in the email greeting and in the LLM prompt for personalization
- **Email**: Where the digest will be sent
- **Keywords**: Comma-separated research interests. These are embedded with SPECTER2 and compared against paper abstracts. Be specific: `"transformer architecture, attention mechanisms, large language models"` works better than just `"AI"`
- **Categories**: Comma-separated arXiv categories to scrape. See the [arXiv category taxonomy](https://arxiv.org/category_taxonomy) for the full list. Common categories are listed in the [Configuration Reference](#arxiv-categories) section below.
- **Status**: Set to `active` to receive digests. Set to anything else (e.g., `inactive`, `paused`) to skip

5. Copy your **Google Sheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/THIS_PART_IS_YOUR_SHEET_ID/edit
   ```
   You'll need this in Step 11.

---

### Step 8: Deploy

```bash
cd n8n-arxiv-digest

# Start both containers
docker compose up -d

# Verify both are running
docker compose ps
```

You should see two containers: `n8n` (running) and `flask-scraper` (running).

**First startup note:** The Flask scraper downloads the SPECTER2 model (~500 MB) on its first run. This can take a few minutes depending on your internet speed. You can watch the progress:

```bash
docker compose logs -f flask-scraper
```

Wait until you see `"SPECTER2 loaded"` in the logs before running the workflow for the first time. The model is cached in a Docker volume, so subsequent starts are fast.

---

### Step 9: Import the Workflow

```bash
docker exec -i n8n n8n import:workflow \
  --input=/dev/stdin < workflow/arxiv-digest-v10.json
```

Now open n8n in your browser:

```
http://YOUR_LAN_IP:5678
```

Log in with the `N8N_BASIC_AUTH_USER` and `N8N_BASIC_AUTH_PASSWORD` you set in `.env`.

You should see the **"Arxiv Digest v10"** workflow.

---

### Step 10: Configure n8n Credentials

In n8n, go to **Settings** (gear icon or your avatar in the bottom-left) → **Credentials** → **Add Credential**.

#### 10a: SMTP (for sending emails)

1. Click **"Add Credential"** → search for **"SMTP"**
2. Fill in:

| Field | Value |
|-------|-------|
| Host | `smtp.gmail.com` |
| Port | `465` |
| SSL/TLS | Enabled (toggle on) |
| User | Your Gmail address |
| Password | The 16-character App Password from Step 4 (no spaces) |

3. Click **"Save"**

#### 10b: Google Sheets OAuth2 (for reading subscribers)

1. Click **"Add Credential"** → search for **"Google Sheets OAuth2 API"**
2. Enter the **Client ID** and **Client Secret** from Step 5
3. **Important:** Make sure you're accessing n8n via the `.nip.io` URL:
   ```
   http://YOUR_LAN_IP.nip.io:5678
   ```
   This must match the redirect URI you registered in Google Cloud Console.
4. Click **"Sign in with Google"**
5. Sign in with your Google account → click **"Continue"** past the "unverified app" warning → grant permissions
6. You should see a green **"Connected"** status
7. Click **"Save"**

#### 10c: LLM Credential

**If using Anthropic (cloud API):**

1. Click **"Add Credential"** → search for **"Anthropic"**
2. Paste your API key from Step 6A
3. Click **"Save"**

**If using Ollama (local model):**

1. Click **"Add Credential"** → search for **"Ollama"**
2. Set the base URL to `http://host.docker.internal:11434`
   - This is how the n8n Docker container reaches Ollama running on the host machine
3. Click **"Save"**

---

### Step 11: Update the Workflow Nodes

Open the workflow in the n8n editor. You need to update several nodes with your credentials and personal settings.

#### Read Subscribers

1. Click the **"Read Subscribers"** node
2. Under **Credential to connect with**, select your Google Sheets OAuth2 credential
3. Click the **Document** dropdown → select your spreadsheet
4. Click the **Sheet** dropdown → select the sheet with your subscriber data (usually "Sheet1")
5. Close the node

#### Send Flask Failure Alert

1. Click the **"Send Flask Failure Alert"** node
2. Under **Credential to connect with**, select your SMTP credential
3. Change **From Email** to your Gmail address
4. Change **To Email** to where you want failure alerts sent
5. Close the node

#### Send Personalized Email

1. Click the **"Send Personalized Email"** node
2. Under **Credential to connect with**, select your SMTP credential
3. Change **From Email** to your Gmail address
4. Close the node (the To Email is dynamic, it reads from your Google Sheet)

#### LLM Model Node

**If using Anthropic (cloud API):**

1. Click the **"Claude Model"** node
2. Under **Credential to connect with**, select your Anthropic credential
3. Optionally change the model (default: Claude Haiku 4.5, see [Changing the LLM Model](#changing-the-llm-model))
4. Close the node

**If using Ollama (local model):**

1. Delete the existing **"Claude Model"** node
2. From the node panel (click **+** or search), add an **"Ollama Model"** node
3. Set the **Model** field to the model you pulled (e.g., `qwen2.5:14b-instruct-q4_K_M`)
4. Under **Credential to connect with**, select your Ollama credential
5. Connect the Ollama Model node to the **"Summarize Paper"** node:
   - Drag from the Ollama Model node's output to the Summarize Paper node
   - It should connect to the `ai_languageModel` input (shown at the bottom of the Summarize Paper node)
6. Close the node

#### Save

Click **"Save"** in the top-right corner.

---

### Step 12: Test

1. In the n8n workflow editor, click **"Test Workflow"** (this triggers the manual path)
2. Watch the execution progress through each node, you can click nodes to see their output
3. Check your email for the digest
4. If everything works, **activate the workflow** by toggling the switch in the top-right corner

**Tip:** The first run may take longer as the Flask scraper downloads the SPECTER2 model. If the workflow times out on the first run, try again after the model has finished downloading (check with `docker compose logs flask-scraper`).

---

### Step 13: Verify Automation

The workflow runs daily at 5:10 AM (your configured timezone) by default. To make sure everything starts on boot:

```bash
# Ensure Docker starts on boot
sudo systemctl enable docker

# Verify containers have restart policies
docker compose ps
# n8n should show "unless-stopped"
# flask-scraper should show "on-failure"
```

The n8n container runs continuously and its built-in cron trigger handles the daily schedule. The Flask scraper container is started and stopped on-demand by the workflow.

---

## Configuration Reference

### arXiv Categories

The full list is available at [arxiv.org/category_taxonomy](https://arxiv.org/category_taxonomy). Here are common categories by field:

#### Computer Science
| Category | Field |
|----------|-------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision and Pattern Recognition |
| `cs.LG` | Machine Learning |
| `cs.CR` | Cryptography and Security |
| `cs.DB` | Databases |
| `cs.DC` | Distributed, Parallel, and Cluster Computing |
| `cs.DS` | Data Structures and Algorithms |
| `cs.HC` | Human-Computer Interaction |
| `cs.IR` | Information Retrieval |
| `cs.NE` | Neural and Evolutionary Computing |
| `cs.PL` | Programming Languages |
| `cs.RO` | Robotics |
| `cs.SE` | Software Engineering |

#### Physics
| Category | Field |
|----------|-------|
| `astro-ph.CO` | Cosmology and Nongalactic Astrophysics |
| `astro-ph.EP` | Earth and Planetary Astrophysics |
| `cond-mat.str-el` | Strongly Correlated Electrons |
| `cond-mat.mtrl-sci` | Materials Science |
| `hep-th` | High Energy Physics - Theory |
| `hep-ph` | High Energy Physics - Phenomenology |
| `quant-ph` | Quantum Physics |
| `gr-qc` | General Relativity and Quantum Cosmology |
| `physics.optics` | Optics |

#### Mathematics
| Category | Field |
|----------|-------|
| `math.AG` | Algebraic Geometry |
| `math.CO` | Combinatorics |
| `math.NT` | Number Theory |
| `math.PR` | Probability |
| `math.ST` | Statistics Theory |

#### Statistics & Quantitative Biology
| Category | Field |
|----------|-------|
| `stat.ML` | Machine Learning (Statistics) |
| `stat.ME` | Methodology |
| `q-bio.BM` | Biomolecules |
| `q-bio.GN` | Genomics |
| `q-bio.NC` | Neurons and Cognition |

#### Economics & Finance
| Category | Field |
|----------|-------|
| `econ.EM` | Econometrics |
| `econ.TH` | Theoretical Economics |
| `q-fin.ST` | Statistical Finance |
| `q-fin.CP` | Computational Finance |

#### Electrical Engineering
| Category | Field |
|----------|-------|
| `eess.SP` | Signal Processing |
| `eess.IV` | Image and Video Processing |
| `eess.AS` | Audio and Speech Processing |
| `eess.SY` | Systems and Control |

---

### Changing the LLM Model

#### Cloud API (Anthropic)

Open the **"Claude Model"** node in the workflow editor and select a different model:

| Model | Speed | Cost per digest* | Quality |
|-------|-------|-----------------|---------|
| Claude Haiku 4.5 (default) | Fastest | ~$0.02 | Great for structured summaries |
| Claude Sonnet 4.6 | Medium | ~$0.15 | Higher quality analysis |

*Estimated cost for 10 paper summaries per subscriber.

#### Local (Ollama)

Open the **"Ollama Model"** node and change the model name. Pull the new model first:

```bash
ollama pull <model-name>
```

See [ollama.com/library](https://ollama.com/library) for available models.

#### Other Providers

n8n has built-in LLM nodes for many providers. To swap providers:

1. Delete the current LLM model node
2. Add the new provider's node (e.g., "OpenAI Model", "Google Gemini Model")
3. Create the appropriate credential in n8n
4. Connect the new node to the **"Summarize Paper"** node's `ai_languageModel` input

---

### Changing the Schedule

Open the **"Daily 5:05 AM Trigger"** node and modify the cron expression:

| Schedule | Cron Expression |
|----------|----------------|
| 5:10 AM daily (default) | `10 5 * * *` |
| 8:00 AM daily | `0 8 * * *` |
| 8:00 AM weekdays only | `0 8 * * 1-5` |
| Every 12 hours | `0 */12 * * *` |
| Mondays and Thursdays at 7 AM | `0 7 * * 1,4` |

Times are in your configured timezone (`TZ` in `.env`).

---

### Adding or Removing Subscribers

Just edit your Google Sheet:
- **Add** a new row with the subscriber's details and set Status to `active`
- **Pause** a subscriber by changing Status to `inactive`
- **Remove** by deleting the row

Changes take effect on the next workflow run, no restart needed.

---

### Adjusting the Number of Papers

By default, each subscriber receives the top 10 most relevant papers. To change this:

1. Open the **"Score Papers for Person"** node in the workflow
2. In the JSON body, change the `top_n` value
3. Save the workflow

---

## Flask Scraper API Reference

The Flask scraper runs as a sidecar container and exposes four endpoints on port 5680:

### `GET /health`

Health check and cache status.

**Response:**
```json
{
  "status": "ok",
  "cached_papers": 0,
  "cached_embeddings": 0,
  "cached_categories": [],
  "cache_time": null,
  "model_loaded": false
}
```

### `POST /scrape`

Scrape arXiv categories, fetch paper metadata, and compute SPECTER2 embeddings.

**Request body:**
```json
{
  "categories": ["cs.AI", "cs.LG", "stat.ML"]
}
```

**Response:**
```json
{
  "papers_by_category": {"cs.AI": 45, "cs.LG": 38, "stat.ML": 22},
  "total_unique_papers": 87,
  "metrics": {
    "rss_fetch_time": 2.3,
    "api_fetch_time": 15.7,
    "embedding_time": 8.4,
    "total_time": 26.4
  }
}
```

### `POST /score`

Score cached papers against a subscriber's keywords. Returns the top N papers ranked by cosine similarity.

**Request body:**
```json
{
  "keywords": "deep learning, transformer architecture, attention mechanisms",
  "categories": ["cs.AI", "cs.LG"],
  "top_n": 10
}
```

**Response:**
```json
{
  "papers": [
    {
      "arxiv_id": "2503.01234",
      "title": "...",
      "abstract": "...",
      "authors": "...",
      "relevance_score": 0.873,
      "rank": 1,
      "categories": ["cs.AI"],
      "link": "https://arxiv.org/abs/2503.01234",
      "pdf_link": "https://arxiv.org/pdf/2503.01234.pdf"
    }
  ],
  "total_in_categories": 45,
  "scoring_time": 0.012
}
```

### `POST /cleanup`

Free all cached papers, embeddings, and unload the SPECTER2 model from memory (~500 MB).

**Response:**
```json
{
  "status": "cleaned",
  "papers_freed": 87,
  "embeddings_freed": 87,
  "model_unloaded": true
}
```

---

## Troubleshooting

### Flask container won't start / Docker socket permission denied

The n8n container needs access to the Docker socket. Make sure `DOCKER_GID` in your `.env` matches the actual docker group GID:

```bash
getent group docker | cut -d: -f3
```

Update `.env` and restart: `docker compose up -d`

### Google OAuth redirect error / "Access blocked: invalid request"

This means the redirect URI doesn't match. Check:

1. You're accessing n8n via the `.nip.io` URL (not bare IP or localhost)
2. The redirect URI in Google Cloud Console matches **exactly**:
   ```
   http://YOUR_LAN_IP.nip.io:5678/rest/oauth2-credential/callback
   ```
3. Your `WEBHOOK_URL` in `.env` matches the same IP

### "invalid_client" / "Unauthorized" when connecting Google Sheets

The Client ID or Client Secret was pasted incorrectly. Go back to Google Cloud Console → Credentials → click on your OAuth client → use the copy buttons to copy the values precisely.

### No papers found in RSS feeds

- arXiv RSS feeds update once daily around 8 PM ET (new papers are posted)
- Weekends and holidays may have no new papers
- Verify the feed is working: `curl https://rss.arxiv.org/rss/cs.AI`

### SPECTER2 model download takes forever / fails

The model (~500 MB) downloads from HuggingFace on first startup. If it fails:

```bash
# Watch the download progress
docker compose logs -f flask-scraper

# If it fails, restart to retry
docker compose restart flask-scraper
```

The model is cached in the `huggingface_cache` Docker volume, so it only downloads once.

### Emails not sending

- Make sure you're using a Gmail **App Password**, not your regular password
- Verify 2-Step Verification is enabled on your Google account
- Test the SMTP credential in n8n: click the credential → "Test"
- Check that your Gmail account hasn't blocked the login (check [Gmail security alerts](https://myaccount.google.com/notifications))

### Out of memory

SPECTER2 uses ~500 MB RAM when loaded. If your system is low on memory:

- Ensure you have at least 2 GB total RAM
- The `/cleanup` endpoint unloads the model after each run
- The Flask container is stopped between runs to free all memory

### Workflow times out on first run

The first run is slower because SPECTER2 needs to download and load. If the "Check Flask Health" node fails, the 15-second wait wasn't enough:

1. Start Flask manually: `docker compose up flask-scraper`
2. Wait for `"SPECTER2 loaded"` in the logs
3. Then run the workflow manually in n8n

Subsequent runs will be much faster since the model is cached.

### Ollama not reachable from n8n

If using Ollama and the workflow can't connect:

1. Make sure Ollama is running on the host: `curl http://localhost:11434/api/tags`
2. The n8n container reaches the host via `host.docker.internal`, verify your Ollama credential URL is set to `http://host.docker.internal:11434`
3. On some Linux systems, `host.docker.internal` may not resolve. Add this to the n8n service in `docker-compose.yml`:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
   Then restart: `docker compose up -d`

### nip.io is down or blocked

If `nip.io` is unreachable (rare), you can use an alternative:

1. Add an entry to your hosts file (on the machine running your browser):
   - Linux/Mac: `/etc/hosts`
   - Windows: `C:\Windows\System32\drivers\etc\hosts`
   ```
   192.168.1.50  n8n.local
   ```
2. Update your Google Cloud OAuth redirect URI to `http://n8n.local:5678/rest/oauth2-credential/callback`
3. Update `WEBHOOK_URL` in `.env` to `http://n8n.local:5678/`
4. Restart n8n: `docker compose up -d n8n`

---

## Architecture

### Why n8n + Flask microservice?

- **n8n** handles orchestration, scheduling, credential management, email formatting, and the subscriber loop. It's a visual workflow tool that makes the pipeline easy to understand and modify.
- **Flask** handles the compute-intensive work (RSS fetching, arXiv API calls, SPECTER2 inference) in a lightweight Python container. Separating this from n8n keeps the workflow engine responsive.

### Why SPECTER2?

[SPECTER2](https://huggingface.co/allenai/specter2_base) is a sentence transformer model specifically trained on scientific papers by the Allen Institute for AI. It produces 768-dimensional embeddings that capture semantic meaning of scientific text much better than general-purpose models. It runs on CPU with no GPU required.

### Why on-demand container management?

The Flask scraper loads a ~500 MB ML model into RAM. Rather than keeping it running 24/7, n8n starts the container when needed and stops it afterward. This is especially useful on memory-constrained servers.

### Why Google Sheets?

A Google Sheet is the simplest possible "database" for subscriber management. Adding a colleague is as easy as adding a row, no admin panel or API calls needed. It also makes it easy to share subscriber management with others in your lab.

---

## Cost Estimate

| Component | Cloud LLM | Local LLM (Ollama) |
|-----------|-----------|---------------------|
| arXiv RSS/API | Free | Free |
| SPECTER2 (CPU) | Free | Free |
| Google Sheets API | Free | Free |
| Gmail SMTP | Free | Free |
| LLM Summaries | ~$0.02-0.05/day | Free (your hardware) |
| **Total** | **~$0.02-0.05/day** | **$0/day** |

Costs scale linearly with subscribers and papers per subscriber. A 5-person lab digest with a cloud API costs roughly $0.10-0.25/day.

---

## Contributing

Found a bug? Have a feature idea? Please [open an issue](https://github.com/sjbevins/n8n-arxiv-digest/issues).

Pull requests are welcome. For major changes, open an issue first to discuss.

---

## License

[MIT](LICENSE)
