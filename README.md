# AYURCASE deployment

AYURCASE is one Flask service: it serves the dashboard files and the `/api/*`
routes from the same origin. This keeps the assistant working after deployment
without sending browser requests to a visitor's `localhost`.

## Required deployment settings

Configure these as host-managed environment variables, not in frontend code:

| Variable | Required | Value |
| --- | --- | --- |
| `GEMINI_API_KEY` | Yes | A Gemini API key stored as a deployment secret. |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.5-flash`. |
| `AYURCASE_DB_PATH` | Yes for durable production data | The absolute path to `ayurcase.db` on a mounted persistent disk. |

Do not upload or commit a real `.env` file. Use `.env.example` only as a local
setup template.

## Start command

Use the included `Procfile`, or configure this command in the host dashboard:

```text
gunicorn --workers 1 --bind 0.0.0.0:$PORT backend.app:app
```

Keep the worker count at `1` while using SQLite. Attach a persistent volume and
set `AYURCASE_DB_PATH` to a file on that volume; otherwise a host restart can
discard new accounts, cases, and appointments.

## Verify after deployment

1. Open `https://your-domain/api/health`. It must return `"status": "ok"` and
   `"ai_configured": true`.
2. Sign in, open either dashboard assistant, and submit a general question.
3. Confirm the network request to `/api/recommend` returns a `200` response
   with a non-empty `recommendation` and `"source": "gemini"`.

If Gemini is temporarily unavailable or the key is missing, the API still
returns a safe non-empty `recommendation` with `"source": "fallback"`; the
chat never leaves the user without a response.
