# BOT ARENA — Vercel Edition

This version replaces Flask-SocketIO with Vercel-compatible HTTP polling and stores room state in Upstash Redis. Vercel Functions are request-driven, so the game simulation advances from elapsed time whenever a player polls or sends an action.

## Why this architecture
Vercel can run Flask as a Python Function, but a traditional always-running Socket.IO server/background game loop is not the right deployment model. This project therefore uses:

- Flask on Vercel
- HTTP JSON actions instead of Socket.IO
- 120 ms client polling for state
- Upstash Redis for shared room state across function instances
- No background thread/game loop required

## Environment variables
Create an Upstash Redis database and set:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

The Python Upstash SDK is designed for serverless environments.

## Deploy

```bash
npm i -g vercel
vercel
vercel --prod
```

For local Vercel behavior:

```bash
vercel dev
```

## Important
Do not commit your Redis token. Add the two variables in Vercel Project Settings → Environment Variables.

The browser keeps a player ID in localStorage, so refreshing the page can reconnect to the same room from the same browser.
