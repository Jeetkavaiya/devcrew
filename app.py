import json
import time

import requests
import streamlit as st

# Config
RENDER_API_URL = st.secrets.get(
    "DEVCREW_API_URL", "https://devcrew.onrender.com"
)
TASK_ENDPOINT = f"{RENDER_API_URL.rstrip('/')}/task"
REQUEST_TIMEOUT_SECONDS = 180

AGENT_COLORS = {
    "planner": "#79C0FF",
    "coder": "#7EE787",
    "tester": "#F0883E",
    "reviewer": "#D2A8FF",
}

EXAMPLE_RUN_PATH = "example_run.json"

# Page setup + styling
st.set_page_config(
    page_title="DevCrew",
    page_icon=":gear:",
    layout="centered",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    code, pre {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    .devcrew-hero {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
        margin-bottom: 0.1rem;
    }
    .devcrew-hero h1 {
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        font-size: 2.1rem;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .devcrew-tagline {
        font-size: 0.95rem;
        margin-top: 0;
        margin-bottom: 1.6rem;
        opacity: 0.75;
    }

    /* Per-agent accent chip — sets its own inline color per call, this
       just defines the shape */
    .agent-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
        border: 1px solid currentColor;
    }

    /* Iteration stepper — custom component, not covered by native theme */
    .stepper-track {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        margin: 1.2rem 0 1.6rem 0;
        flex-wrap: wrap;
    }
    .step-node {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.35rem 0.75rem;
        border-radius: 6px;
        border: 1px solid #30363D;
        color: #8B949E;
        background: #161B22;
    }
    .step-node.approved {
        border-color: #7EE787;
        color: #7EE787;
        background: rgba(126, 231, 135, 0.08);
    }
    .step-node.rejected {
        border-color: #F0883E;
        color: #F0883E;
        background: rgba(240, 136, 62, 0.08);
    }
    .step-arrow {
        color: #30363D;
        font-size: 0.9rem;
    }

    /* Final status banner — custom component, not covered by native theme */
    .final-status-pass {
        border: 1px solid #7EE787;
        background: rgba(126, 231, 135, 0.08);
        color: #7EE787;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    .final-status-fail {
        border: 1px solid #F0883E;
        background: rgba(240, 136, 62, 0.08);
        color: #F0883E;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="devcrew-hero">
        <h1>DevCrew</h1>
    </div>
    <p class="devcrew-tagline">
        Planner &rarr; Coder &rarr; Tester &rarr; Reviewer &mdash;
        a self-correcting multi-agent pipeline that turns a plain-English
        request into tested Python.
    </p>
    """,
    unsafe_allow_html=True,
)

# Helpers
def load_example_run():
    """Load a pre-baked example run so the page has something meaningful
    to show before the user spends live quota on a fresh call."""
    try:
        with open(EXAMPLE_RUN_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def call_devcrew(task_text: str):
    response = requests.post(
        TASK_ENDPOINT,
        json={"task": task_text},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def agent_chip(name: str) -> str:
    color = AGENT_COLORS.get(name.lower(), "#8B949E")
    return (
        f'<span class="agent-chip" style="color:{color};">'
        f"{name.upper()}</span>"
    )


def render_stepper(review_feedback: list):
    """Render the iteration history as a horizontal stepper: one node per
    reviewer pass, colored by approved/rejected."""
    if not review_feedback:
        st.caption("No review iterations recorded for this run.")
        return

    nodes = []
    for entry in review_feedback:
        state = "approved" if entry.get("approved") else "rejected"
        label = f"Iteration {entry.get('iteration', '?')}"
        nodes.append(f'<span class="step-node {state}">{label}</span>')

    track = '<span class="step-arrow">&rarr;</span>'.join(nodes)
    st.markdown(f'<div class="stepper-track">{track}</div>', unsafe_allow_html=True)


def render_result(result: dict):
    approved = bool(result.get("approved"))
    iteration_count = result.get("iteration_count", 0)

    if approved:
        st.markdown(
            f'<div class="final-status-pass">'
            f"&#10003; Approved after {iteration_count} iteration(s)"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="final-status-fail">'
            f"&#33; Not approved after {iteration_count} iteration(s) "
            f"&mdash; showing the last attempt"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.subheader("Final code")
    st.code(result.get("code", ""), language="python")

    st.subheader("Pipeline trace")
    render_stepper(result.get("review_feedback", []))

    with st.expander("PLANNER — Spec"):
        st.markdown(agent_chip("planner"), unsafe_allow_html=True)
        st.text(result.get("spec", "(no spec returned)"))

    with st.expander("CODER — Code"):
        st.markdown(agent_chip("coder"), unsafe_allow_html=True)
        st.code(result.get("code", ""), language="python")

    with st.expander("TESTER — Tests + results"):
        st.markdown(agent_chip("tester"), unsafe_allow_html=True)
        st.caption("Generated tests")
        st.code(result.get("tests", ""), language="python")
        st.caption("Sandbox run output")
        st.text(result.get("test_results", "(no test results returned)"))

    with st.expander("REVIEWER — Review history"):
        st.markdown(agent_chip("reviewer"), unsafe_allow_html=True)
        review_feedback = result.get("review_feedback", [])
        if not review_feedback:
            st.caption("No review feedback recorded.")
        for entry in review_feedback:
            verdict = "Approved" if entry.get("approved") else "Rejected"
            st.markdown(
                f"**Iteration {entry.get('iteration', '?')} — {verdict}**"
            )
            notes = entry.get("notes", "").strip()
            st.text(notes if notes else "(no notes recorded for this iteration)")
            st.divider()


# Sidebar: example run vs live call
with st.sidebar:
    st.markdown("### About")
    st.caption(
        "DevCrew chains four LLM agents through LangGraph to turn a "
        "natural-language coding request into reviewed, tested Python. "
        "Each request below hits the live pipeline deployed on Render."
    )
    st.markdown(
        "[View source](https://github.com/Jeetkavaiya/devcrew)",
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption(
        "Live runs call the Groq API on a free-tier quota, so responses "
        "may occasionally be slow or fail if quota is exhausted."
    )


# Main: example run (default view) + live run form
example_run = load_example_run()

tab_labels = ["Try it live"]
if example_run:
    tab_labels.insert(0, "Example run")

tabs = st.tabs(tab_labels)
tab_index = 0

if example_run:
    with tabs[tab_index]:
        st.caption(
            f"Pre-recorded run for: \u201c{example_run.get('task', '')}\u201d "
            f"— no live call, loads instantly."
        )
        render_result(example_run)
    tab_index += 1

with tabs[tab_index]:
    st.caption(
        "Runs the real pipeline against the deployed Render endpoint. "
        "This uses live Groq quota and can take 30-90 seconds."
    )
    task_text = st.text_area(
        "Describe the coding task",
        placeholder="e.g. Write a function that checks if a number is prime",
        height=100,
    )
    run_clicked = st.button("Run DevCrew", type="primary")

    if run_clicked:
        if not task_text.strip():
            st.warning("Enter a task description first.")
        else:
            start = time.time()
            with st.spinner(
                "Running Planner \u2192 Coder \u2192 Tester \u2192 Reviewer..."
            ):
                try:
                    result = call_devcrew(task_text.strip())
                except requests.exceptions.Timeout:
                    st.error(
                        f"The request timed out after "
                        f"{REQUEST_TIMEOUT_SECONDS}s. Render's free tier "
                        f"can cold-start slowly \u2014 try again in a moment."
                    )
                    result = None
                except requests.exceptions.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                    result = None

            if result is not None:
                elapsed = time.time() - start
                st.caption(f"Completed in {elapsed:.1f}s")
                render_result(result)