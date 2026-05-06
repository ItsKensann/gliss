# Gliss

Real-time AI speech coaching app. Browser captures camera + mic, streams raw PCM audio over WebSocket to a Python backend that runs faster-whisper for transcription, local heuristics for filler/pace/pause detection, and Claude for live coaching notes. Sessions are saved as JSON and rendered as post-session reports.

---

## Tech stack

**Backend** (`backend/`)
- Python 3.12 / FastAPI / Uvicorn (WebSocket + REST)
- `faster-whisper` for transcription (CPU, int8, runs in `ThreadPoolExecutor`)
- `anthropic.AsyncAnthropic` for Claude — Sonnet 4.6 for coaching notes, Haiku 4.5 for coherence scoring
- `librosa` for audio resampling
- `pydantic` v2 for all data models
- `pydantic-settings` for env var config

**Frontend** (`frontend/`)
- Next.js 15 (App Router) + TypeScript
- Tailwind CSS + Framer Motion
- Web Audio API + AudioWorklet (`public/audio-processor.js`) for raw float32 PCM capture
- WebSocket binary frames for audio, JSON text frames for control messages
- `next/navigation` `useRouter` for redirects, `useParams` for dynamic routes

**Storage**
- JSON files at `backend/sessions/{session_id}.json` — no database yet

---

## Project structure

```
backend/
├── app/
│   ├── main.py                       FastAPI app, CORS, router registration
│   ├── core/config.py                pydantic-settings (.env loader)
│   ├── models/session.py             All Pydantic models (FillerWord, AnalysisResult, SessionReport, …)
│   ├── services/
│   │   ├── transcription.py          PCM buffer + faster-whisper wrapper
│   │   ├── audio_analysis.py         Filler/WPM/pause heuristics + immediate feedback
│   │   ├── feedback.py               Claude API calls (AsyncAnthropic)
│   │   └── session_store.py          build_report + save/load JSON files
│   └── api/routes/
│       ├── session.py                WebSocket /api/v1/session
│       └── report.py                 GET /api/v1/report/{id}
├── sessions/                         Saved session JSONs (gitignored)
├── requirements.txt
└── .env                              ANTHROPIC_API_KEY, WHISPER_MODEL

frontend/
├── public/audio-processor.js         AudioWorklet — runs in audio thread
└── src/
    ├── app/
    │   ├── page.tsx                  Landing
    │   ├── session/page.tsx          Recording UI
    │   └── report/[id]/page.tsx      Post-session report (with retry on 404)
    ├── components/
    │   ├── session/{Recorder,LiveFeedback}.tsx
    │   └── report/SessionReport.tsx
    ├── hooks/
    │   ├── useMediaStream.ts         Mic+camera + AudioWorklet
    │   └── useSession.ts             WS lifecycle + nav to report
    └── lib/
        ├── websocket.ts              GlissWebSocket class
        └── types.ts                  Shared TS types (mirrors backend Pydantic)
```

---

## Key conventions

### Async + threading
- Anthropic calls use `AsyncAnthropic` — never blocks the event loop.
- Whisper is CPU-bound; always run via `loop.run_in_executor(_whisper_executor, …)`.
- The analysis loop uses a **stop event**, not `task.cancel()`, so an in-flight Whisper run finishes cleanly before shutdown.
- A final transcription cycle always runs in the `finally` block to capture audio buffered since the last interval (covers short sessions).

### Mutable state in nested async functions
The session WebSocket handler uses 1-element list refs (`face_metrics_ref`, `ai_enabled_ref`) instead of `nonlocal` for state that the receive loop updates and `run_analysis` reads. This avoids Python's `nonlocal` quirks for mutable values across nested closures.

### WebSocket protocol
- Audio: **binary** frames. First 4 bytes = uint32 LE source sample rate, remainder = float32 LE mono PCM. Backend resamples to 16kHz.
- Control: **JSON text** frames with a `type` discriminator: `"metrics"` (eye contact), `"config"` (`ai_enabled`).
- Session ID is passed as a query string: `?session_id=<uuid>`.

### AI feedback toggle (dev mode)
- Default is **OFF** on both backend (`ai_enabled_ref = [False]`) and frontend (`aiEnabled: false` in `useSession`) to avoid burning Anthropic credits during development.
- The toggle pill in `Recorder.tsx` sends a `{type:"config", ai_enabled:bool}` message.

### Pydantic v2
- All cross-boundary data (WebSocket messages, REST responses, persisted JSON) is a Pydantic model.
- Use `model_dump_json()` for serialization, `model_validate_json()` for parsing.
- Frontend `lib/types.ts` mirrors these — keep them in sync.

### Code style
- Default to writing no comments. Only comment for non-obvious *why* (e.g. the WebM header concatenation issue, the executor / cancellation race).
- Don't add backwards-compatibility shims, premature abstractions, or future-proofing.
- Trust internal code — only validate at system boundaries.

### Error handling at boundaries
- Anthropic call failures (400, 429, etc.) are caught around the `asyncio.gather` so one bad chunk doesn't kill the analysis loop.
- WebSocket disconnects: check `data.get("type") == "websocket.disconnect"` AND catch `WebSocketDisconnect` AND `RuntimeError` (Starlette is inconsistent).

---

## Commands

All commands assume PowerShell on Windows.

### Backend
```powershell
cd backend
.venv\Scripts\Activate.ps1                # activate venv (created with python -m venv .venv)
pip install -r requirements.txt           # first-time only
uvicorn app.main:app --reload             # dev server on :8000
```

First run downloads the Whisper model (~150MB) into the HuggingFace cache.

### Frontend
```powershell
cd frontend
npm install                               # first-time only
npm run dev                               # dev server on :3000
npm run build                             # production build
npm run lint                              # ESLint (next/core-web-vitals config)
```

### Full local stack
Open the app at <http://localhost:3000> after both servers are running.

---

## Environment variables

`backend/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
WHISPER_MODEL=base                        # tiny | base | small | medium | large-v3
```

`frontend` (optional, defaults to localhost):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/session
```

---

## Things to know when adding features

- **Whisper is the bottleneck.** It runs on CPU. Don't await it on the main event loop.
- **MediaRecorder is intentionally not used** — its WebM/Opus chunks aren't independently decodable. Keep the AudioWorklet PCM pipeline.
- **Sessions can take 15–30s to save** after disconnect because of the final transcription. The report page retries the 404 for up to 40s.
- **Face tracking is stubbed** — `eye_contact_score` and `head_stability` are sent over the WS but always 1.0. MediaPipe wiring is the next big feature.

---

## Open questions for the user

1. **Testing:** No test framework wired up yet. Do you want pytest + Vitest set up, and what should the bar be (unit / integration / e2e)?
2. **Linting/formatting:** ESLint is on. Add `ruff` + `black` for the backend? Pre-commit hooks?
3. **Type checking:** Want `mypy` (or `pyright`) on the backend? `tsc --noEmit` strictness on the frontend?
4. **Deployment target:** Vercel for frontend + Fly.io / Render / Railway for backend? Or self-hosted? This affects how we configure CORS and env vars.
5. **Database:** When the JSON-files-on-disk approach hits its limit (multi-user, search, history), what's the target — Postgres? SQLite? Supabase?
6. **Auth:** Mentioned Clerk vs. Supabase Auth in earlier planning — still TBD?
7. **Conventions to enforce:** Anything in your existing workflow I should respect that I haven't picked up on (commit message format, branch naming, file naming for new components)?
