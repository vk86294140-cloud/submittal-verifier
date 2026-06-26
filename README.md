# speccheck — construction submittal verification

**Upload a project specification and a contractor's submittal. Get back, in
seconds, exactly what is met, missing, or out of spec — instead of reading two
documents line by line.**

In construction, every product a contractor installs must be approved first.
The contractor sends a **submittal** (product data, shop drawings, samples, test
reports); a reviewer checks it against the **project spec** (a CSI MasterFormat
section like `09 68 13`). On a real project that's thousands of manual
comparisons. `speccheck` does the mechanical pass and surfaces only what a human
needs to judge.

---

## Contents
- [What it tells you](#what-it-tells-you)
- [Quick start (your computer)](#quick-start-your-computer)
- [Using it](#using-it)
- [Letting other people use it](#letting-other-people-use-it)
- [What it costs](#what-it-costs)
- [Security](#security)
- [How it works](#how-it-works)
- [Project layout](#project-layout)
- [Limitations](#limitations)

---

## What it tells you

Each requirement in the spec gets one verdict:

| Result | Meaning |
| --- | --- |
| `MET` | The submittal satisfies it |
| `MISSING` | A required item or referenced standard is absent |
| `STANDARD_MISMATCH` | Spec wants e.g. `ASTM E662`; submittal cites a different one |
| `VALUE_DEVIATION` | A submitted value breaks a spec minimum/maximum |
| `UNVERIFIED` | Can't be checked automatically — flagged for a human |

Overall verdict is conservative: **APPROVE** only when nothing is missing or
deviating; otherwise **REVISE & RESUBMIT**.

---

## Quick start (your computer)

You need **Python 3.10+**. Open PowerShell in the project folder.

```powershell
# 1. install (the core needs no extra packages)
pip install -e ".[web,pdf]"

# 2. run the web app  —  NOTE: use "python -m uvicorn", not just "uvicorn"
python -m uvicorn speccheck.web:app --reload

# 3. open your browser at  http://127.0.0.1:8000
```

> **Why `python -m uvicorn`?** If you type just `uvicorn` and see
> *"uvicorn is not recognized"*, it means the tool isn't on your system PATH.
> Running it through `python -m` always works — no PATH setup needed.

Prefer the command line? No install of extras required:

```powershell
python -m speccheck.cli verify samples/spec_096813.txt samples/submittal_096813.txt
```

To confirm everything works:

```powershell
python -m pytest        # core tests run with no extra installs
```

---

## Using it

### Web app (recommended)

1. Open `http://127.0.0.1:8000`.
2. Enter a project name, choose the **spec** file and the **submittal** file
   (`.txt` or `.pdf`), click **Verify & save**.
3. You get a color-coded compliance matrix. Download it as HTML or JSON.
4. The **dashboard** keeps every past review.
5. **Resubmittal?** Put the earlier review's number in "Resubmittal of review #".
   The new review shows what was **cleared**, what's still **recurring**, and any
   **new** problems.

### Command line

```powershell
# verdict in the terminal (exit code 2 = needs revision)
python -m speccheck.cli verify spec.pdf submittal.pdf

# save a report file to share
python -m speccheck.cli verify spec.txt submittal.txt --format html -o review.html

# resubmittal: compare a new round to a saved one
python -m speccheck.cli verify spec.txt resubmittal.txt --save
python -m speccheck.cli verify spec.txt round2.txt --against 1
```

### In Python

```python
from speccheck import review, to_html

result = review(spec_text, submittal_text)
print(result.compliant)      # False
print(result.summary())      # {'missing': 2, 'met': 7, ...}
open("review.html", "w").write(to_html(result))
```

An example HTML report is at [`docs/example_report.html`](docs/example_report.html).

---

## Letting other people use it

Your coworkers **install nothing**. You host the app once; they open a link.
Three ways, same app — pick by who needs to reach it.

### Option A — Office network (fastest)

Run it on one computer; everyone on the same office Wi-Fi/LAN reaches it.

```powershell
pip install -e ".[web,pdf]"
$env:SPECCHECK_PASSWORD = "pick-a-strong-password"
python -m uvicorn speccheck.web:app --host 0.0.0.0 --port 8000
```

Find your computer's IP with `ipconfig` (look for IPv4, e.g. `192.168.1.20`),
allow port 8000 through Windows Firewall, and share
`http://192.168.1.20:8000`. The `--host 0.0.0.0` part is what makes it reachable
from other machines.

### Option B — Public website (anyone, anywhere)

Push this repo to GitHub, then on **Render** (or Railway/Fly): *New → Blueprint*,
pick the repo — it reads [`render.yaml`](render.yaml). Set `SPECCHECK_PASSWORD`
in the dashboard. You get a real HTTPS link like
`https://speccheck.onrender.com`. TLS/HTTPS is handled for you.

### Option C — Your own server (Docker)

```bash
docker build -t speccheck .
docker run -p 8000:8000 \
  -e SPECCHECK_PASSWORD=pick-a-strong-password \
  -v "$PWD/data:/data" -e SPECCHECK_DB=/data/speccheck.db \
  speccheck
```

The `-v ...:/data` part keeps the review database on disk across restarts.

---

## What it costs

| How you run it | Cost | Notes |
| --- | --- | --- |
| **Your computer / office LAN** (Option A) | **$0** | Uses a machine you already own. Best for internal use. |
| **Render free plan** (Option B) | **$0** | Sleeps when idle (slow first load), and the database **resets** on restart — fine for demos. |
| **Render Starter** (Option B) | **~$7/mo** + ~$0.25/GB disk | Always on, database persists. |
| **Railway / Fly.io** | small free credit, then usage-based | Similar to Render. |
| **Your own VPS** (Option C) | **~$4–6/mo** (Hetzner, DigitalOcean…) | Most control; you manage the server. |
| Custom domain (optional) | ~$10–15/yr | e.g. `submittals.yourcompany.com`. The host's HTTPS link is free. |

**Plain answer:** running it for yourself or your office costs **nothing**.
You only pay if you want an always-on public website with saved data — and even
then it starts around **$7/month**.

---

## Security

Built so that someone using the app cannot steal or destroy your data. What's in
place and what *you* must do:

**Already built in**
- **Login.** Set `SPECCHECK_PASSWORD` and the whole app requires a username +
  password (HTTP Basic). Passwords are compared in constant time (no timing
  leaks). Without the variable set, the app is open — only do that on a trusted
  private network.
- **No code injection.** All text shown in the browser is HTML-escaped, so a
  booby-trapped submittal can't run scripts in a reviewer's browser (XSS-safe).
  Database access uses parameterized queries, so file names/content can't perform
  SQL injection.
- **Upload limits.** Only `.txt` and `.pdf` are accepted, and each file is capped
  (default 10 MB, via `SPECCHECK_MAX_UPLOAD_MB`) to block oversized-file abuse.
  Uploads are read, never executed.
- **Rate limiting.** Each visitor IP is throttled (default 120 requests/minute,
  via `SPECCHECK_RATE_LIMIT`) to blunt brute-force and denial-of-service attempts.
- **Hardening headers.** Every response sets `Content-Security-Policy`,
  `X-Frame-Options: DENY` (no clickjacking), `X-Content-Type-Options: nosniff`,
  and `Referrer-Policy`.
- **Health check** (`/healthz`) stays open for uptime monitors but is excluded
  from the rate limiter.

**You must do**
- **Always set `SPECCHECK_PASSWORD`** for anything beyond your own machine.
- **Use HTTPS** when public. Render/Fly/Railway give it free; on your own VPS put
  the app behind a reverse proxy (Caddy/Nginx) that terminates TLS.
- **Protect the database file.** Reviews live in `speccheck.db`. Keep it on a
  drive only you/your server can read, and back it up.
- **Keep the password out of git** — pass it as an environment variable
  (as shown), never commit it.

```powershell
# example: lock it down locally
$env:SPECCHECK_PASSWORD = "a-long-random-password"
$env:SPECCHECK_USER     = "reviewer"
python -m uvicorn speccheck.web:app --host 0.0.0.0 --port 8000
```

> **Honest scope:** this is one shared login suitable for a small team. Separate
> per-user accounts, audit logging of *who* approved what, and antivirus
> scanning of uploads are sensible next steps before a large or external rollout.

---

## How it works

```
spec text ─▶ extract requirements ─┐
                                   ├─▶ verify ─▶ Report ─▶ text / JSON / HTML
submittal text ─▶ parse submittal ─┘
```

Requirement extraction is **rule-based** on purpose — construction specs follow
strong conventions (CSI format, "shall" language, referenced standards), so
targeted patterns recover most checkable obligations deterministically and
offline. An **optional** Claude pass (`--llm`, needs `ANTHROPIC_API_KEY`) adds
semantic requirements the patterns miss; it never runs unless you ask, and the
tool works fully without it.

---

## Project layout

```
speccheck/
  models.py      domain types (Requirement, Finding, Report)
  extract.py     spec  -> requirements   (rule-based)
  verify.py      submittal parse + cross-reference engine
  llm.py         optional Claude enrichment (off by default)
  report.py      text / JSON / HTML renderers
  store.py       SQLite storage of past reviews
  resubmittal.py diff a submittal against a prior saved review
  cli.py         command-line interface
  web.py         web app: dashboard, upload, auth, rate limiting, JSON API
samples/         a real-format spec section 09 68 13 and a submittal
tests/           pytest suite (core offline; web tests skip without FastAPI)
Dockerfile · render.yaml · Procfile   deploy to a container / Render / PaaS
```

---

## Limitations

- Works on text-based specs/submittals. **Scanned image PDFs need OCR first.**
- Numeric checks only fire when the value has a clear subject; ambiguous numbers
  are marked `UNVERIFIED` rather than guessed — it prefers a missed catch over a
  false approval.
- It **assists** a reviewer; it does not replace the architect's professional
  stamp.

## Roadmap

- Per-user accounts and an approval audit log
- Spec-section auto-splitting for multi-section PDF specs
- Side-by-side spec/submittal view in the web UI

## License

MIT
