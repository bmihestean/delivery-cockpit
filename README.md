# delivery-cockpit

An operational console over the AI-Forward Delivery Leader Build Program's four repos — not a new phase of AI capability, but the answer to a real problem that showed up once there were four of them: remembering which venv to activate, which CLI flags each script takes, and where inputs and outputs live for each one.

This isn't [PH.05](../ai-fundamentals-rig)'s "portfolio packaging" — that's an *outward*-facing case-study page for recruiters. This is *inward*-facing: built now, ahead of PH.04, because the friction was a today problem, not a launch-day one.

## What it is

One Streamlit app, four tabs, almost no logic of its own:

- **Run** — pick a tool from a dropdown, fill a short form, click Run. Every action shells out to a script that already exists, in that script's own venv (`ask.py`, `agent.py`, `ingest.py`, `eval.py`, `experiments.py`, `delivery-evals`'s judge suites) — nothing here reimplements what those scripts already do.
- **Browse** — see what's indexed (`delivery-copilot/data/raw/<account>/`), what raw inputs exist for the agent (`delivery-status-agent/inputs/`), and every generated result/eval/report file across all four output directories, previewed inline instead of hunted down in Finder.
- **Status & cost** — one aggregated view over the cost/token data those scripts already log, per repo and per run.
- **Private notes** — for actually using this day-to-day with real meeting notes instead of the synthetic demo data. See below — this is the one tab that isn't just a thin wrapper over an existing script.

A header row shows each repo's latest local commit and whether `delivery-mcp-server` is connected in Claude Code (`claude mcp list`, parsed).

**Deliberately not built:** a browser chat UI for PH.02's MCP server. That would duplicate `delivery-status-agent`'s actual job — a real agent loop calling those tools — badly. The cockpit's role for PH.02 is just a connection-status check.

## A real gap this surfaced

Scoping this out meant actually checking what each repo persists, and two of three didn't log cost at all: `delivery-copilot/eval_results/*.json` had no token/cost fields even though `answer_question()` already returns them — they just weren't being captured. `delivery-status-agent/reports/*.json` didn't track usage at all. Fixed both before building the cost tab, since a cost dashboard covering one repo out of three isn't a cost dashboard.

One thing worth being careful about, fixing the agent's side: usage data is saved *alongside* the report (`{"report": {...}, "usage": {...}}`), never inside it. The `StatusReport` model doubles as the JSON schema Claude has to fill in via `output_config.format` — it can't report its own token cost while generating its own output, so that bookkeeping has to happen in code, after the call returns, not as a field the model is asked to populate.

## Using this with real notes, not the demo data

The synthetic Meridian Health account is safe to keep public — it's invented. Real meeting notes, standups, or client content are not, and `delivery-copilot/data/raw/` and `delivery-status-agent/inputs/` are both tracked, public repo folders.

The **Private notes** tab points at a folder configured in `~/.delivery-program/config.json`, defaulting to `~/Projects/delivery-leader-program-private/` — a plain directory that isn't a git repository at all, sitting outside every repo in this program. That's a stronger guarantee than gitignoring a folder inside one of the repos: git can't accidentally pick up a file that isn't inside its working tree in the first place, so there's no rule to remember or ever undo by mistake.

From that tab: change where the folder lives, upload a `.md`/`.txt` file (export or copy your Teams/Gemini notes as plain text — `.docx` isn't parsed directly yet), and choose whether it's **indexed knowledge** (goes to `<private root>/data/raw/<account>/`, searchable later — run "Rebuild an index" afterward) or a **one-off agent input** (goes to `<private root>/agent_inputs/`, for a single `agent.py` run). Both `delivery-copilot/accounts.py` and this repo's `paths.py` transparently merge public and private accounts wherever an account list or file list is shown — a private account works identically to the demo one everywhere else in the program, including the Chroma collection-per-account isolation from PH.01.

## Setup

```bash
# needs the other four repos already set up as siblings under the same
# parent directory, each with its own venv and (where relevant) API key
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No `.env` here — this repo never calls Claude directly, only launches scripts that already handle their own keys.

## Run it

```bash
streamlit run app.py
```

That's it — that command is now the only one worth remembering.

---

Part of the [AI-Forward Delivery Leader Build Program](../ai-fundamentals-rig).
