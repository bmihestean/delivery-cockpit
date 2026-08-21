"""Delivery Cockpit — an operational console over the AI-Forward Delivery
Leader Build Program's four repos.

Not a new pipeline: every "Run" action here shells out to a script that
already exists, in that script's own venv, and every "Browse"/"Status"
view just reads files those scripts already produce. This app owns no
logic of its own beyond launching and displaying — the whole point is to
stop needing to remember which venv, which flags, which folder.

Usage:
    streamlit run app.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

from account_meta import LOGOS_DIR, get_account_meta, save_account_meta
from paths import (
    AGENT_INPUTS,
    AI_FUNDAMENTALS,
    DATA_RAW,
    DELIVERY_COPILOT,
    DELIVERY_EVALS,
    DELIVERY_STATUS_AGENT,
    EVAL_RESULTS_DIR,
    EVALS_RESULTS_DIR,
    REPORTS_DIR,
    REPOS,
    RESULTS_DIR,
    list_accounts,
    list_agent_inputs,
    private_agent_inputs_dir,
    private_data_dir,
    private_data_root,
    save_private_data_root,
    venv_python,
)

st.set_page_config(page_title="Delivery Cockpit", page_icon="🛰️", layout="wide")

EFFORT_CHOICES = ["low", "medium", "high", "xhigh", "max"]


def git_head(repo_dir: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "no commits"
    except Exception:
        return "?"


def mcp_status() -> str:
    try:
        out = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=15)
        for line in out.stdout.splitlines():
            if line.strip().startswith("delivery-copilot:"):
                return "✔ Connected" if "✔" in line else "registered, not connected"
        return "not registered"
    except Exception:
        return "claude CLI not found"


def run_script(repo_dir: Path, script: str, args: list[str]) -> subprocess.CompletedProcess:
    python = venv_python(repo_dir)
    return subprocess.run(
        [str(python), script, *args], cwd=repo_dir, capture_output=True, text=True, timeout=600,
    )


def latest_file(dir_: Path, pattern: str = "*.json") -> Path | None:
    if not dir_.exists():
        return None
    files = sorted(dir_.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def load_all_json(dir_: Path) -> list[dict]:
    if not dir_.exists():
        return []
    out = []
    for f in sorted(dir_.glob("*.json")):
        try:
            out.append({"file": f.name, "mtime": f.stat().st_mtime, "data": json.loads(f.read_text())})
        except Exception:
            pass
    return out


# ---------------------------------------------------------- sidebar / ops --

with st.sidebar:
    st.caption("🛰️ Delivery Cockpit")
    st.caption("Run, browse, and check the cost of everything in the AI-Forward Delivery Leader Build Program, without hand-recalling four venvs' worth of commands.")
    st.divider()
    with st.expander("Dev / ops status", icon=":material/monitoring:", expanded=False):
        for name, repo_dir in REPOS.items():
            st.caption(f"**{name}** · `{git_head(repo_dir)}`")
        st.caption(f"**MCP server** · {mcp_status()}")

# --------------------------------------------------------- account banner --

accounts = list_accounts()
st.session_state.setdefault("cockpit_account", None)
if accounts and st.session_state.cockpit_account not in accounts:
    st.session_state.cockpit_account = accounts[0]

meta = get_account_meta(st.session_state.cockpit_account) if st.session_state.cockpit_account else None

with st.container(key="account-header", border=True):
    cols = st.columns([1, 6, 3], vertical_alignment="center")
    with cols[0]:
        if meta and meta.logo and (meta.logo.startswith("http") or Path(meta.logo).exists()):
            st.image(meta.logo, width=48)
        else:
            st.markdown(f"<span style='font-size:2.5rem'>{(meta.logo if meta else None) or '🏢'}</span>", unsafe_allow_html=True)
    with cols[1]:
        st.subheader(meta.display_name if meta else "No account selected")
        if meta and meta.description:
            st.caption(meta.description)
    with cols[2]:
        if accounts:
            st.selectbox("Account", accounts, key="cockpit_account", label_visibility="collapsed")
            with st.popover("Edit account details", icon=":material/edit:"):
                with st.form("account_meta_form"):
                    new_display_name = st.text_input("Display name", value=meta.display_name)
                    new_accent_color = st.color_picker("Accent color", value=meta.accent_color)
                    new_logo = st.text_input("Logo (emoji, path, or URL)", value=meta.logo or "")
                    new_logo_upload = st.file_uploader("...or upload a logo image", type=["png", "jpg", "jpeg", "svg"])
                    new_description = st.text_area("Description", value=meta.description)
                    if st.form_submit_button("Save", icon=":material/save:"):
                        logo_value = new_logo
                        if new_logo_upload is not None:
                            LOGOS_DIR.mkdir(parents=True, exist_ok=True)
                            ext = Path(new_logo_upload.name).suffix
                            logo_path = LOGOS_DIR / f"{meta.slug}{ext}"
                            logo_path.write_bytes(new_logo_upload.getvalue())
                            logo_value = str(logo_path)
                        save_account_meta(meta.slug, {
                            "display_name": new_display_name,
                            "accent_color": new_accent_color,
                            "logo": logo_value,
                            "description": new_description,
                        })
                        st.rerun()
        else:
            st.warning("No accounts found.")

if meta:
    st.html(f"<style>.st-key-account-header {{ border-left: 6px solid {meta.accent_color}; }}</style>")

tab_run, tab_browse, tab_status, tab_private = st.tabs([
    ":material/play_arrow: Run",
    ":material/folder: Browse",
    ":material/payments: Status & cost",
    ":material/lock: Private notes",
])

# ------------------------------------------------------------------ run --

with tab_run:
    if not accounts:
        st.warning("No accounts found under delivery-copilot/data/raw/. Run ingest.py there first.")

    tool = st.selectbox(
        "Tool",
        [
            "Ask a question (delivery-copilot)",
            "Run the agent (delivery-status-agent)",
            "Rebuild an index (delivery-copilot ingest)",
            "Run the eval suite (delivery-copilot eval)",
            "Run a PH.00 experiment (ai-fundamentals-rig)",
            "Run LLM-judge evals (delivery-evals)",
        ],
    )

    if tool.startswith("Ask a question"):
        account = st.session_state.cockpit_account
        with st.form("ask_form"):
            question = st.text_input("Question")
            st.caption(f"Account: **{account}**" if account else "No account selected")
            effort = st.segmented_control("Effort", EFFORT_CHOICES, default=EFFORT_CHOICES[0], required=True)
            submitted = st.form_submit_button("Run", icon=":material/play_arrow:")
        if submitted and question.strip() and account:
            with st.spinner("Running ask.py..."):
                result = run_script(DELIVERY_COPILOT, "ask.py", [question, "--account", account, "--effort", effort])
            st.code(result.stdout or result.stderr, language="text")
            if result.returncode != 0:
                st.error("ask.py exited with an error.")

    elif tool.startswith("Run the agent"):
        input_map = list_agent_inputs()  # merges public demo inputs + private ones (🔒 prefix)
        account = st.session_state.cockpit_account
        with st.form("agent_form"):
            input_choice = st.selectbox("Input file", list(input_map.keys())) if input_map else None
            st.caption(f"Account: **{account}**" if account else "No account selected")
            effort = st.segmented_control("Effort", EFFORT_CHOICES, default=EFFORT_CHOICES[0], required=True, key="agent_effort")
            submitted = st.form_submit_button("Run agent", icon=":material/smart_toy:")
        if submitted and input_choice and account:
            input_path = input_map[input_choice]
            with st.spinner("Running agent.py — makes several tool calls, can take a minute..."):
                result = run_script(
                    DELIVERY_STATUS_AGENT, "agent.py",
                    [str(input_path), "--account", account, "--effort", effort],
                )
            with st.expander("Full run log (tool calls, stages)"):
                st.code(result.stdout or result.stderr, language="text")
            if result.returncode == 0:
                latest = latest_file(REPORTS_DIR)
                if latest:
                    data = json.loads(latest.read_text())
                    report, usage = data.get("report", data), data.get("usage")
                    st.subheader("Status report")
                    st.write(report.get("summary", ""))
                    if report.get("milestones"):
                        st.write("**Milestones**")
                        for m in report["milestones"]:
                            st.markdown(f"- {m}")
                    if report.get("risks"):
                        st.write("**Risks**")
                        st.dataframe(pd.DataFrame(report["risks"]), width="stretch")
                    if report.get("action_items"):
                        st.write("**Action items**")
                        st.dataframe(pd.DataFrame(report["action_items"]), width="stretch")
                    if report.get("open_questions"):
                        st.write("**Open questions**")
                        for q in report["open_questions"]:
                            st.markdown(f"- {q}")
                    if usage:
                        st.caption(
                            f"Usage: {usage['input_tokens']} in / {usage['output_tokens']} out / "
                            f"${usage['cost_usd']:.4f} / {usage['tool_call_count']} tool call(s)"
                        )
            else:
                st.error("agent.py exited with an error.")

    elif tool.startswith("Rebuild an index"):
        with st.form("ingest_form"):
            account = st.text_input(
                "Account slug — existing account (public or private), or a new folder already created under data/raw/ in either location",
                value=st.session_state.cockpit_account or "",
            )
            submitted = st.form_submit_button("Rebuild", icon=":material/refresh:")
        if submitted and account:
            with st.spinner("Running ingest.py..."):
                result = run_script(DELIVERY_COPILOT, "ingest.py", ["--account", account])
            st.code(result.stdout or result.stderr, language="text")

    elif tool.startswith("Run the eval suite"):
        account = st.session_state.cockpit_account
        with st.form("eval_form"):
            st.caption(f"Account: **{account}**" if account else "No account selected")
            submitted = st.form_submit_button("Run eval", icon=":material/play_arrow:")
        if submitted and account:
            with st.spinner("Running eval.py — 10 questions against the live API..."):
                result = run_script(DELIVERY_COPILOT, "eval.py", ["--account", account])
            st.code(result.stdout or result.stderr, language="text")

    elif tool.startswith("Run a PH.00"):
        with st.form("exp_form"):
            task = st.segmented_control("Task", ["qbr_summary", "action_items"], default="qbr_summary", required=True)
            effort = st.segmented_control("Effort", EFFORT_CHOICES, default=EFFORT_CHOICES[0], required=True, key="exp_effort")
            submitted = st.form_submit_button("Run", icon=":material/play_arrow:")
        if submitted:
            with st.spinner("Running experiments.py..."):
                result = run_script(AI_FUNDAMENTALS, "experiments.py", ["--task", task, "--effort", effort])
            st.code(result.stdout or result.stderr, language="text")

    elif tool.startswith("Run LLM-judge evals"):
        st.caption(
            "Judges delivery-copilot's answers and delivery-status-agent's reports "
            "semantically instead of by keyword match — see delivery-evals/README.md."
        )
        with st.form("evals_form"):
            suite_options = ["QA judge (10 questions, ~1 min)", "Report judge (2 scenarios, slower — the agent runs first)"]
            which = st.segmented_control("Which suite", suite_options, default=suite_options[0], required=True)
            submitted = st.form_submit_button("Run", icon=":material/play_arrow:")
        if submitted:
            script = "run_qa_evals.py" if which.startswith("QA") else "run_report_evals.py"
            with st.spinner(f"Running {script}..."):
                result = run_script(DELIVERY_EVALS, script, [])
            st.code(result.stdout or result.stderr, language="text")
            if result.returncode != 0:
                st.error(f"{script} exited with an error.")

# --------------------------------------------------------------- browse --

with tab_browse:
    st.subheader("Indexed source documents")
    if not accounts:
        st.info("No accounts indexed yet.")
    for account in accounts:
        files = sorted((DATA_RAW / account).glob("*.md"))
        with st.expander(f"{account} ({len(files)} files)"):
            for f in files:
                st.text(f.name)

    st.subheader("Agent input files")
    input_files = sorted(AGENT_INPUTS.glob("*.md")) if AGENT_INPUTS.exists() else []
    for f in input_files:
        with st.expander(f.name):
            st.markdown(f.read_text())

    st.subheader("Generated outputs")
    out_tabs = st.tabs(["PH.00 results", "PH.01 eval results", "PH.03 reports", "PH.04 judged evals"])
    with out_tabs[0]:
        for item in reversed(load_all_json(RESULTS_DIR)):
            with st.expander(item["file"]):
                st.json(item["data"])
    with out_tabs[1]:
        for item in reversed(load_all_json(EVAL_RESULTS_DIR)):
            with st.expander(item["file"]):
                st.dataframe(pd.DataFrame(item["data"]), width="stretch")
    with out_tabs[2]:
        for item in reversed(load_all_json(REPORTS_DIR)):
            with st.expander(item["file"]):
                st.json(item["data"])
    with out_tabs[3]:
        for item in reversed(load_all_json(EVALS_RESULTS_DIR)):
            with st.expander(f"{item['file']} ({item['data'].get('config', {}).get('timestamp', '')})"):
                st.json(item["data"].get("config", {}))
                st.dataframe(pd.DataFrame(item["data"].get("results", [])), width="stretch")

# --------------------------------------------------------- status & cost --

with tab_status:
    st.subheader("Cost & usage across the program")
    rows = []
    for item in load_all_json(RESULTS_DIR):
        for r in (item["data"] if isinstance(item["data"], list) else []):
            rows.append({
                "repo": "ai-fundamentals-rig", "file": item["file"],
                "input_tokens": r.get("input_tokens", 0), "output_tokens": r.get("output_tokens", 0),
                "cost_usd": r.get("cost_usd", 0.0),
            })
    for item in load_all_json(EVAL_RESULTS_DIR):
        for r in (item["data"] if isinstance(item["data"], list) else []):
            rows.append({
                "repo": "delivery-copilot", "file": item["file"],
                "input_tokens": r.get("input_tokens", 0), "output_tokens": r.get("output_tokens", 0),
                "cost_usd": r.get("cost_usd", 0.0),
            })
    for item in load_all_json(REPORTS_DIR):
        usage = item["data"].get("usage") if isinstance(item["data"], dict) else None
        if usage:
            rows.append({
                "repo": "delivery-status-agent", "file": item["file"],
                "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                "cost_usd": usage.get("cost_usd", 0.0),
            })
    for item in load_all_json(EVALS_RESULTS_DIR):
        # cost_usd here already includes the judge's own call cost, not just
        # the thing being judged — see delivery-evals/judge.py.
        for r in (item["data"].get("results", []) if isinstance(item["data"], dict) else []):
            rows.append({
                "repo": "delivery-evals", "file": item["file"],
                "input_tokens": 0, "output_tokens": 0,
                "cost_usd": r.get("cost_usd", 0.0),
            })

    if rows:
        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total spend", f"${df['cost_usd'].sum():.4f}")
        c2.metric("Total calls logged", len(df))
        c3.metric("Total tokens", int(df["input_tokens"].sum() + df["output_tokens"].sum()))

        st.write("**By repo**")
        st.dataframe(df.groupby("repo")[["input_tokens", "output_tokens", "cost_usd"]].sum(), width="stretch")

        st.write("**All logged runs**")
        st.dataframe(df.sort_values("cost_usd", ascending=False), width="stretch")
    else:
        st.info("No cost data yet — run something from the Run tab first.")

# ------------------------------------------------------------- private --

with tab_private:
    st.subheader("Where private notes live")
    st.caption(
        "Entirely outside every git repo in this program — not gitignored, "
        "physically separate, so nothing saved here can ever reach GitHub "
        "through a git command run in any of the five repos."
    )
    current_root = private_data_root()
    with st.form("private_root_form"):
        new_root = st.text_input("Private notes folder", value=str(current_root))
        submitted_root = st.form_submit_button("Save location", icon=":material/save:")
    if submitted_root and new_root.strip():
        save_private_data_root(Path(new_root.strip()).expanduser())
        st.success(f"Saved. Private notes now resolve to: {Path(new_root.strip()).expanduser()}")
        st.rerun()

    st.subheader("Add a file")
    st.caption(
        "Upload a meeting transcript or personal notes as .md or .txt "
        "(export/copy your Teams or Gemini notes as plain text first — "
        ".docx isn't parsed directly yet)."
    )
    with st.form("private_upload_form"):
        uploaded = st.file_uploader("File", type=["md", "txt"])
        account_slug = st.text_input("Account (existing or new — this becomes the folder/collection name)")
        kind_options = ["Indexed knowledge (searchable later via ask/agent/MCP)", "One-off agent input (process once)"]
        kind = st.segmented_control("Add as", kind_options, default=kind_options[0], required=True)
        submit_upload = st.form_submit_button("Save file", icon=":material/upload_file:")
    if submit_upload and uploaded and account_slug.strip():
        content = uploaded.getvalue().decode("utf-8", errors="replace")
        root = private_data_root()
        if kind.startswith("Indexed"):
            target_dir = root / "data" / "raw" / account_slug.strip()
        else:
            target_dir = root / "agent_inputs"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / uploaded.name
        target_path.write_text(content)
        st.success(f"Saved to {target_path}")
        if kind.startswith("Indexed"):
            st.info(f"Run \"Rebuild an index\" for account '{account_slug.strip()}' in the Run tab to make it searchable.")
        st.rerun()

    st.subheader("What's already private")
    priv_data = private_data_dir()
    priv_accounts = sorted(p.name for p in priv_data.iterdir() if p.is_dir()) if priv_data.exists() else []
    if priv_accounts:
        for acc in priv_accounts:
            files = sorted((priv_data / acc).glob("*.md"))
            with st.expander(f"🔒 {acc} ({len(files)} files)"):
                for f in files:
                    st.text(f.name)
    else:
        st.caption("No private accounts yet.")

    priv_inputs_dir = private_agent_inputs_dir()
    priv_inputs = sorted(priv_inputs_dir.glob("*.md")) if priv_inputs_dir.exists() else []
    if priv_inputs:
        st.write("**Private agent inputs**")
        for f in priv_inputs:
            st.text(f.name)
