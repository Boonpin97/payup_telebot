# Trip Split Bot

A Telegram group-chat bot for tracking and splitting trip expenses, similar to a lightweight Splitwise.

- One Telegram group can hold many trips, but only one is **active** at a time.
- Members are added manually (Telegram cannot reliably enumerate group members).
- Expenses can be split equally, by amount, or by percentage.
- A simplified-debt algorithm minimises the number of settlement transactions.
- No real money is moved — the bot only records and reports.

## Architecture

```
Telegram group chat
        ↓ (HTTPS webhook)
FastAPI on Cloud Run
        ↓
Firestore (Native mode)
```

| Layer        | Tech                                                |
|--------------|-----------------------------------------------------|
| Language     | Python 3.12                                         |
| Framework    | FastAPI + uvicorn                                   |
| HTTP client  | httpx (calls Telegram Bot API directly)             |
| Database     | Google Cloud Firestore                              |
| Hosting      | Google Cloud Run (Docker)                           |
| Secrets      | Google Secret Manager                               |

## Commands

| Command            | Purpose                                             |
|--------------------|-----------------------------------------------------|
| `/new_trip`        | Create a new trip; becomes the active trip          |
| `/add_expense`     | Add an expense to the active trip                   |
| `/summary`         | Show totals, balances, and simplified settlement    |
| `/delete_payment`  | Pick an expense from a list and delete it           |
| `/add_members`     | Add one or more `@usernames` to the active trip     |
| `/delete_members`  | Remove members from the active trip                 |
| `/switch_trip`     | Pick a different trip to be the active one          |
| `/delete_trip`     | Soft-delete a trip                                  |

`/add_expense` formats:

```
/add_expense pasta 10                # split equally among all trip members
/add_expense pasta 10 @alice @bob    # split equally among the two listed users
```

After every added expense the bot shows `[Edit] [Delete] [Partial Split]` inline buttons.
Multi-step interactions (prompts, edit menus, custom-split inputs) expire after **3 minutes**.

## Project layout

```
trip-split-bot/
  app/
    main.py             # FastAPI entrypoint, routes /webhook and /health
    config.py           # Pydantic settings
    telegram/           # Telegram client, keyboards, message templates, webhook handler
    commands/           # One module per /command and per callback flow
    services/           # Business logic (no Firestore-specific code)
    repositories/       # Firestore access
    models/             # Pydantic data models
    utils/              # Money, parser, timeout, logging helpers
  tests/
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## Local development

### 1. Install dependencies

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Authenticate to Firestore

```bash
gcloud auth application-default login
gcloud config set project PROJECT_ID
```

The backend uses Application Default Credentials when running locally.

### 3. Configure environment

```bash
cp .env.example .env
# Then fill in TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, GOOGLE_CLOUD_PROJECT
```

### 4. Run

```bash
uvicorn app.main:app --reload --port 8080
```

Or with Docker:

```bash
docker compose up --build
```

To accept Telegram webhooks locally, expose port 8080 via ngrok or Cloudflare Tunnel.

### 5. Run tests

```bash
pytest
```

## Firestore setup

1. Open the Firebase / Google Cloud console.
2. Create a Firebase project (or reuse a Google Cloud project).
3. Enable Firestore in **Native mode**.
4. Pick the closest region — for SG/MY users, `asia-southeast1` is reasonable. Compare price/latency before committing.

Enable required APIs:

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

Create a least-privilege service account:

```bash
gcloud iam service-accounts create trip-split-bot-sa \
  --display-name="Trip Split Bot Cloud Run Service Account"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:trip-split-bot-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:trip-split-bot-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Store the Telegram secrets:

```bash
echo -n "YOUR_TELEGRAM_BOT_TOKEN" | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=-
echo -n "YOUR_RANDOM_WEBHOOK_SECRET" | gcloud secrets create TELEGRAM_WEBHOOK_SECRET --data-file=-
```

To rotate later:

```bash
echo -n "NEW_VALUE" | gcloud secrets versions add TELEGRAM_BOT_TOKEN --data-file=-
```

## Cloud Run deployment

```bash
export PROJECT_ID="your-project-id"
export REGION="asia-southeast1"
export REPO="trip-split-bot"
export SERVICE="trip-split-bot"

gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repository for Telegram trip split bot"

gcloud builds submit \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:latest

gcloud run deploy $SERVICE \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$SERVICE:latest \
  --region $REGION \
  --platform managed \
  --service-account trip-split-bot-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID,ENVIRONMENT=production,FIRESTORE_DATABASE_ID="(default)" \
  --set-secrets TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_WEBHOOK_SECRET=TELEGRAM_WEBHOOK_SECRET:latest
```

`--allow-unauthenticated` is required because Telegram cannot present GCP IAM
credentials. Security relies on the `X-Telegram-Bot-Api-Secret-Token` header.

Get the deployed URL:

```bash
gcloud run services describe $SERVICE --region $REGION --format='value(status.url)'
```

Register the webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://<your-service-url>/webhook" \
  -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

The backend exposes:

- `POST /webhook` — Telegram updates
- `GET /health` — `{"status": "ok"}`

## Security

- Verifies `X-Telegram-Bot-Api-Secret-Token` on every webhook request.
- Bot token and webhook secret are loaded from environment / Secret Manager.
- Money is computed with `Decimal`, never floating point.
- `.env` is git-ignored; only `.env.example` is committed.
