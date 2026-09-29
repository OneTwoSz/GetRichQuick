# Hosting a demo

The root `Dockerfile` builds one service: FastAPI serves the API under
`/api` and the built React app for every other path. `render.yaml` deploys
it to Render's free plan.

## Render (free)

1. Sign in at https://render.com with GitHub.
2. **New → Blueprint**, pick this repository and the branch to deploy
   (`main` once the Phase 3 PR is merged).
3. Apply. The first build takes ~5–10 minutes. You get a URL like
   `https://greenthread-xxxx.onrender.com`.

What you get:

- The demo factory (Saravana Knits) is seeded on start, with a published
  product passport. The login page has an **Explore the demo factory**
  button — no credentials to share.
- Passport QR codes point at the live URL automatically (Render sets
  `RENDER_EXTERNAL_URL`).
- HTTPS, so the QR codes work from phone cameras.

Free-plan behaviour to know about:

- The service sleeps after ~15 minutes idle; the next visit takes ~30–60
  seconds to wake. Open it yourself a minute before a demo.
- The SQLite database lives on the container's disk and **resets on every
  deploy and wake-up**, re-seeding the demo. Anything visitors enter is
  temporary. For persistent data, add a Render Postgres database and set
  `DATABASE_URL` to its connection string.

## Anywhere else

Any host that runs a Dockerfile works (Fly.io, Railway, a VPS):

```bash
docker build -t greenthread .
docker run -p 8000:8000 -e SECRET_KEY=change-me -e DEMO_SEED=true \
  -e PUBLIC_BASE_URL=https://your-domain greenthread
```
