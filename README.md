# कवच · Kawach

Consent-based child online-safety monitoring that responds proportionally instead of raw keyword-blocking.

A browser extension watches for risk signals (chat, search, page visits). A keyword engine + ML classifier score each one. A correlation engine sums the score over a 30-min session window into 3 tiers — silent log → private nudge to the child → parent alert with an AI-written explanation. Parent feedback on each alert recalibrates future sensitivity per child.

## Features
- Graduated 3-tier response (not binary block/allow)
- Keyword rules + TF-IDF/SVM ML classifier, with a confidence gate
- LLM (Groq) re-checks tier-3 clusters for false positives before alerting
- Per-child feedback loop adjusts sensitivity over time
- Privacy-first: no passwords/keystrokes/chat history/file contents captured
- JWT-authenticated, ownership-scoped parent dashboard
- Fails safe if Safe Browsing / LLM / SMTP are down

## Tech stack
- **Extension:** Chrome Manifest V3, vanilla JS
- **Backend:** FastAPI, SQLAlchemy + SQLite, JWT auth
- **ML:** scikit-learn (TF-IDF + Linear SVM)
- **External APIs:** Google Safe Browsing, Groq LLM
- **Dashboard:** Next.js 16, React 19, Tailwind CSS
- **Scheduling/Email:** APScheduler, smtplib

## Quick start

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Dashboard**
```bash
cd dashboard
pnpm install
echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000" > .env.local
pnpm dev
```

**Extension**
Load unpacked from `extension/` at `chrome://extensions`, set the backend URL in Options, pair using the code from the dashboard.

## License
Not yet added — recommend MIT or Apache-2.0.