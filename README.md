# कवच · Kawach

Kawach is a browser activity monitoring and security-focused Chrome extension designed to provide an additional layer of protection while users interact with the web. The project focuses on identifying potentially risky or suspicious online activities by collecting selected browser activity with the user's knowledge and consent.

In today's digital environment, users interact with a wide variety of websites, search engines, online communication platforms, and file-sharing services. These interactions can sometimes expose users to potentially harmful, suspicious, or unsafe content. Kawach aims to address this challenge by monitoring relevant browser activities and analyzing them to identify patterns that may indicate potential risk.

The Kawach system consists of a Chrome browser extension connected to a backend analysis system. The extension is responsible for detecting and collecting selected browser activities, while the backend processes this information using a weighted-scoring approach. Different activities can be assigned different levels of importance, allowing the system to calculate an overall risk score based on the observed activity.

The main goal of Kawach is to provide a safety layer for online browser activity and help identify potentially risky activities.

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
