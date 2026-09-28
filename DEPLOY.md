# Deploying CTQ to Render (permanent 24/7 URL)

The repo contains everything Render needs: `Dockerfile` (builds the React
frontend, runs FastAPI serving it + the API on one origin) and `render.yaml`
(Blueprint describing the service).

## One-time setup

1. **Push this project to GitHub**
   ```bash
   git remote add origin https://github.com/<your-username>/CTQ.git
   git push -u origin master
   ```
2. **Sign up at https://dashboard.render.com** using your GitHub account
   (choose "GitHub" as the sign-in method so Render can see your repos).

## Create the service

3. Dashboard → **New +** → **Blueprint**.
4. Select the `CTQ` repository → Render reads `render.yaml` automatically.
5. When prompted for **GROQ_API_KEY**, paste the key from `backend/.env`.
6. Click **Apply**. The first build takes ~10 minutes (downloads PyTorch CPU,
   sentence-transformers and the DistilBERT model).

## After the first deploy

- Your permanent URL appears at the top of the service page
  (e.g. `https://ctq-clinical-trial-qualifier.onrender.com`).
- First request after idle can take ~50 s (free plans sleep; the ML models
  reload on wake).
- Every `git push` to `master` auto-redeploys.

## Free-plan caveat

The free plan has 512 MB RAM. CTQ loads two small models (DistilBERT QA
~260 MB, MiniLM embeddings ~90 MB). If the service crashes with OOM after
boot, upgrade the plan in Render → Settings (Starter, 2 GB, $7/mo) — no
code changes needed.
