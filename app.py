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

from paths import (
    AGENT_INPUTS,
    AI_FUNDAMENTALS,
    DATA_RAW,
    DELIVERY_COPILOT,
    DELIVERY_STATUS_AGENT,
    EVAL_RESULTS_DIR,
    REPORTS_DIR,
    REPOS,
    RESULTS_DIR,
    list_accounts,
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
        [str(python), script, *args], cwd=repo_dir, capture_output=True, text=True, timeout=300,
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


# ---------------------------------------------------------------- header --

st.title("🛰️ Delivery Cockpit")
st.caption("Run, browse, and check the cost of everything in the AI-Forward Delivery Leader Build Program, without hand-recalling four venvs' worth of commands.")

cols = st.columns(5)
for i, (name, repo_dir) in enumerate(REPOS.items()):
    cols[i].metric(name, git_head(repo_dir))
cols[4].metric("MCP server", mcp_status())

accounts = list_accounts()

tab_run, tab_browse, tab_status = st.tabs(["▶ Run", "📂 Browse", "💰 Status & cost"])

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
        ],
    )

    if tool.startswith("Ask a question"):
        with st.form("ask_form"):
            question = st.text_input("Question")
            account = st.selectbox("Account", accounts) if accounts else None
            effort = st.selectbox("Effort", EFFORT_CHOICES, index=0)
            submitted = st.form_submit_button("Run")
        if submitted and question.strip() and account:
            with st.spinner("Running ask.py..."):
                result = run_script(DELIVERY_COPILOT, "ask.py", [question, "--account", account, "--effort", effort])
            st.code(result.stdout or result.stderr, language="text")
            if result.returncode != 0:
                st.error("ask.py exited with an error.")

    elif tool.startswith("Run the agent"):
        input_files = sorted(AGENT_INPUTS.glob("*.md")) if AGENT_INPUTS.exists() else []
        with st.form("agent_form"):
            input_choice = st.selectbox("Input file", [f.name for f in input_files]) if input_files else None
            account = st.selectbox("Account", accounts, key="agent_account") if accounts else None
            effort = st.selectbox("Effort", EFFORT_CHOICES, index=0, key="agent_effort")
            submitted = st.form_submit_button("Run agent")
        if submitted and input_choice and account:
            input_path = AGENT_INPUTS / input_choice
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
                "Account slug (existing account, or a new folder name already created under data/raw/)",
                value=accounts[0] if accounts else "",
            )
            submitted = st.form_submit_button("Rebuild")
        if submitted and account:
            with st.spinner("Running ingest.py..."):
                result = run_script(DELIVERY_COPILOT, "ingest.py", ["--account", account])
            st.code(result.stdout or result.stderr, language="text")

    elif tool.startswith("Run the eval suite"):
        with st.form("eval_form"):
            account = st.selectbox("Account", accounts, key="eval_account") if accounts else None
            submitted = st.form_submit_button("Run eval")
        if submitted and account:
            with st.spinner("Running eval.py — 10 questions against the live API..."):
                result = run_script(DELIVERY_COPILOT, "eval.py", ["--account", account])
            st.code(result.stdout or result.stderr, language="text")

    elif tool.startswith("Run a PH.00"):
        with st.form("exp_form"):
            task = st.selectbox("Task", ["qbr_summary", "action_items"])
            effort = st.selectbox("Effort", EFFORT_CHOICES, index=0, key="exp_effort")
            submitted = st.form_submit_button("Run")
        if submitted:
            with st.spinner("Running experiments.py..."):
                result = run_script(AI_FUNDAMENTALS, "experiments.py", ["--task", task, "--effort", effort])
            st.code(result.stdout or result.stderr, language="text")

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
    out_tabs = st.tabs(["PH.00 results", "PH.01 eval results", "PH.03 reports"])
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
