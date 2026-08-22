(() => {
  "use strict";

  // Allow ?api=http://localhost:8000/task for local backend testing without
  // touching this file. Defaults to the live Render deployment.
  const params = new URLSearchParams(window.location.search);
  const API_URL = params.get("api") || "https://devcrew-gmja.onrender.com/task";

  const form = document.getElementById("task-form");
  const input = document.getElementById("task-input");
  const submitBtn = document.getElementById("submit-btn");
  const schematicSection = document.getElementById("schematic-section");
  const schematicStatus = document.getElementById("schematic-status");
  const resultsSection = document.getElementById("results");
  const resultsSummary = document.getElementById("results-summary");
  const specCode = document.getElementById("spec-code");
  const timelineEntries = document.getElementById("timeline-entries");
  const finalCode = document.getElementById("final-code");
  const finalCodeStatus = document.getElementById("final-code-status");
  const copyFinalCodeBtn = document.getElementById("copy-final-code");
  const emptyState = document.getElementById("empty-state");

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.task;
      input.focus();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const task = input.value.trim();
    if (!task) return;

    runTask(task);
  });

  async function runTask(task) {
    setLoading(true);
    clearError();
    emptyState.hidden = true;
    resultsSection.hidden = true;

    let coldStartTimer = window.setTimeout(() => {
      schematicStatus.textContent =
        "still working — the backend sleeps when idle and can take up to 30s to wake up";
    }, 6000);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
      });

      window.clearTimeout(coldStartTimer);

      if (!response.ok) {
        let detail = "";
        try {
          const errJson = await response.json();
          detail = errJson.detail ? ` — ${JSON.stringify(errJson.detail)}` : "";
        } catch (_) {
          /* response wasn't JSON, ignore */
        }
        throw new Error(`Request failed (${response.status})${detail}`);
      }

      const data = await response.json();
      renderResult(data);
    } catch (err) {
      window.clearTimeout(coldStartTimer);
      showError(err);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitBtn.classList.toggle("is-loading", isLoading);
    schematicSection.classList.toggle("is-processing", isLoading);
    schematicStatus.textContent = isLoading
      ? "dispatching task through the crew…"
      : "idle";
    clearNodeStates();
  }

  function clearNodeStates() {
    document.querySelectorAll(".node").forEach((node) => {
      node.removeAttribute("data-state");
    });
  }

  function showError(err) {
    clearError();
    const banner = document.createElement("div");
    banner.className = "error-banner";
    banner.id = "error-banner";
    banner.innerHTML = `<strong>Run failed.</strong> ${escapeHtml(err.message || String(err))}`;
    schematicSection.insertAdjacentElement("afterend", banner);
    schematicStatus.textContent = "idle";
  }

  function clearError() {
    const existing = document.getElementById("error-banner");
    if (existing) existing.remove();
  }

  function renderResult(data) {
    resultsSection.hidden = false;

    // Final verdict coloring on the schematic itself.
    const finalNode = document.querySelector('.node[data-node="reviewer"]');
    if (finalNode) {
      finalNode.setAttribute("data-state", data.approved ? "approved" : "rejected");
    }
    schematicStatus.textContent = data.approved
      ? `approved after ${data.iteration_count} iteration${data.iteration_count === 1 ? "" : "s"}`
      : `not approved after ${data.iteration_count} iteration${data.iteration_count === 1 ? "" : "s"} (iteration cap reached)`;

    renderSummary(data);
    renderSpec(data);
    renderTimeline(data);
    renderFinalCode(data);

    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderSummary(data) {
    const verdictClass = data.approved ? "approved" : "rejected";
    const verdictText = data.approved ? "approved" : "not approved";
    resultsSummary.innerHTML = `
      <span class="summary-verdict ${verdictClass}">${verdictText}</span>
      <span class="summary-meta">${escapeHtml(data.task)}</span>
      <span class="summary-meta">· ${data.iteration_count} iteration${data.iteration_count === 1 ? "" : "s"}</span>
    `;
  }

  function renderSpec(data) {
    specCode.textContent = data.spec || "(empty)";
    if (window.hljs) window.hljs.highlightElement(specCode);
  }

  function renderTimeline(data) {
    timelineEntries.innerHTML = "";
    const iterations = data.iterations && data.iterations.length
      ? data.iterations
      : fallbackIterationsFromReviewFeedback(data);

    iterations.forEach((entry, idx) => {
      timelineEntries.appendChild(buildIterationCard(entry, idx === iterations.length - 1));
    });
  }

  // If an older backend deploy hasn't picked up the `iterations` field yet,
  // fall back to review_feedback so the timeline still renders (with only
  // the reviewer's notes, not a per-iteration code snapshot).
  function fallbackIterationsFromReviewFeedback(data) {
    if (!data.review_feedback || !data.review_feedback.length) return [];
    return data.review_feedback.map((fb, idx) => ({
      iteration: fb.iteration,
      code: idx === data.review_feedback.length - 1 ? data.code : null,
      tests: idx === data.review_feedback.length - 1 ? data.tests : null,
      test_results: idx === data.review_feedback.length - 1 ? data.test_results : null,
      approved: fb.approved,
      notes: fb.notes,
    }));
  }

  function buildIterationCard(entry, isLast) {
    const card = document.createElement("div");
    card.className = "iteration-card";
    card.dataset.open = isLast ? "true" : "false";
    card.dataset.openVerdict = entry.approved ? "approved" : "rejected";

    const header = document.createElement("div");
    header.className = "iteration-header";
    header.innerHTML = `
      <span class="iteration-num">iteration ${entry.iteration}</span>
      <span class="iteration-toggle">&#9656;</span>
      <span class="iteration-verdict ${entry.approved ? "approved" : "rejected"}">
        ${entry.approved ? "approved" : "sent back for revision"}
      </span>
    `;
    header.addEventListener("click", () => {
      card.dataset.open = card.dataset.open === "true" ? "false" : "true";
    });

    const body = document.createElement("div");
    body.className = "iteration-body";
    body.appendChild(buildSubsection("reviewer notes", null, entry.notes));

    if (entry.code) {
      body.appendChild(buildSubsection("code", "python", entry.code));
    }
    if (entry.tests) {
      body.appendChild(buildSubsection("tests", "python", entry.tests));
    }
    if (entry.test_results) {
      body.appendChild(buildTestResultsSubsection(entry.test_results));
    }

    card.appendChild(header);
    card.appendChild(body);
    return card;
  }

  function buildSubsection(label, lang, content) {
    const wrap = document.createElement("div");
    wrap.className = "iteration-subsection";

    const labelEl = document.createElement("p");
    labelEl.className = "iteration-subsection-label";
    labelEl.textContent = label;
    wrap.appendChild(labelEl);

    if (label === "reviewer notes") {
      const notes = document.createElement("div");
      notes.className = "reviewer-notes";
      notes.textContent = content || "(no notes)";
      wrap.appendChild(notes);
      return wrap;
    }

    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.className = `language-${lang}`;
    code.textContent = content;
    pre.appendChild(code);
    wrap.appendChild(pre);
    if (window.hljs) window.hljs.highlightElement(code);
    return wrap;
  }

  function buildTestResultsSubsection(testResults) {
    const wrap = document.createElement("div");
    wrap.className = "iteration-subsection";

    const labelEl = document.createElement("p");
    labelEl.className = "iteration-subsection-label";
    labelEl.textContent = "test results";
    wrap.appendChild(labelEl);

    const statusMatch = testResults.match(/status:\s*(.+)/i);
    if (statusMatch) {
      const rawStatus = statusMatch[1].trim();
      const statusClass = rawStatus.toLowerCase().replace(/\s+/g, "-");
      const badge = document.createElement("span");
      badge.className = `test-status-line ${statusClass}`;
      badge.textContent = rawStatus;
      wrap.appendChild(badge);
    }

    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.className = "language-text";
    code.textContent = testResults;
    pre.appendChild(code);
    wrap.appendChild(pre);
    return wrap;
  }

  function renderFinalCode(data) {
    finalCode.textContent = data.code || "(no code produced)";
    if (window.hljs) window.hljs.highlightElement(finalCode);
    finalCodeStatus.textContent = data.approved
      ? "approved"
      : `not approved — capped at ${data.iteration_count} iterations`;
    finalCodeStatus.style.color = data.approved
      ? "var(--mint)"
      : "var(--red)";
  }

  copyFinalCodeBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(finalCode.textContent);
      const original = copyFinalCodeBtn.textContent;
      copyFinalCodeBtn.textContent = "copied";
      window.setTimeout(() => {
        copyFinalCodeBtn.textContent = original;
      }, 1500);
    } catch (_) {
      copyFinalCodeBtn.textContent = "copy failed";
    }
  });

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();