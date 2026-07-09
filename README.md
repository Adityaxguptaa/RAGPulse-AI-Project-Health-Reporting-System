# RAGPulse : AI Project Health Reporting System

A Streamlit tool that takes messy Excel project plans and turns them into a straight answer: is this project Green, Amber, or Red — and why. Upload one or more workbooks and it parses tasks, milestones and risks out of them, scores health on six weighted dimensions, optionally layers Gemini on top for the narrative (summary, risks, recommendations), and spits out a weekly PDF report and a PowerPoint deck per project, plus a portfolio-level rollup when you upload more than one.

I built this because the usual PMO status report is either a spreadsheet nobody reads or a slide deck someone spent half a day formatting by hand. This does the scoring and the formatting for you, and — importantly — it doesn't quietly change the RAG colour depending on whether the AI is switched on.

---

## Running it

### Prerequisites
- Python 3.11+
- A Gemini API key if you want the AI narrative layer ([Google AI Studio](https://aistudio.google.com/)) — the rule engine works fine without one

### Setup

```bash
# install dependencies
pip install -r requirements.txt

# add your Gemini key (optional — only needed for AI enrichment)
echo "GEMINI_API_KEY=your_key_here" > .env

# run it
streamlit run app.py --server.port 5000
```

On Replit, this is already wired up as the `Streamlit App` workflow and `GEMINI_API_KEY` is managed as a secret — just hit Run.

### Using the dashboard

1. Upload one or more `.xlsx` / `.xls` project plan files.
2. Toggle Gemini AI on or off in the sidebar (the RAG colour won't change either way — see below).
3. Click **Run Analysis**.
4. For a single project you get its RAG badge, ten key metrics, all six dimension scores with rationale, a full detail view (tasks, risk register, milestones, AI reasoning), and inline PDF/slide previews. For multiple projects you also get a portfolio overview with a RAG distribution chart and a cross-project comparison table.
5. Download individual PDFs/PPTXs, or grab everything as one ZIP.


### Environment variables

| Variable | Required | What it's for |
|---|---|---|
| `GEMINI_API_KEY` | Only for AI enrichment | Google Gemini API key. Without it the app still runs — you just get rule-engine scoring without the narrative layer. |

### Project layout

```
.
├── app.py                        # Streamlit dashboard — upload, run, view, download
├── requirements.txt
├── replit.md                     # project notes / preferences for this workspace
├── prompts/                      # standalone prompts (not used by the app itself)
│   ├── ppt_generation_prompt.md      # prompt to generate a portfolio PPT externally
│   └── methodology_pdf_prompt.md     # prompt to generate a 1-page methodology PDF externally
├── src/
│   ├── models.py                 # Project / Task / Risk dataclasses
│   ├── parser.py                 # Excel workbook parser (handles .xlsx and .xls)
│   ├── rag_engine.py             # the deterministic 6-dimension scoring engine
│   ├── gemini_client.py          # Gemini API client (loads GEMINI_API_KEY from env/.env)
│   ├── analysis.py               # orchestrates parse → score → enrich → report
│   ├── pdf_generator.py          # ReportLab PDF reports (per-project + portfolio)
│   ├── ppt_generator.py          # python-pptx decks (per-project + portfolio)
│   ├── slide_renderer.py         # same slides as HTML, for in-app preview
│   └── portfolio.py              # cross-project rollup and health signal
├── sample_data/                  # two example project plan workbooks
└── outputs/                      # generated PDFs/PPTXs land here (auto-created)
```

---

## How it actually works

```
Excel file(s) (.xlsx / .xls)
        │
        ▼
1. Parser            src/parser.py         → reads the sheets, normalises them into Project / Task / Risk objects
        │
        ▼
2. Rule engine        src/rag_engine.py     → deterministic 6-dimension weighted score (this always runs)
        │
        ▼
3. Gemini enrichment   src/gemini_client.py  → optional narrative layer (summary, risks, recommendations)
        │
        ▼
4. Report generation   src/pdf_generator.py, src/ppt_generator.py, src/slide_renderer.py, src/portfolio.py
        │
        ▼
Weekly PDF + PPTX per project, portfolio PDF + PPTX, live dashboard
```

The parser doesn't assume a fixed template. It fuzzy-matches headers (so "Task Name", "Activity" and "Item" all resolve to the same field), pulls out tasks, milestones, risks, and free-text comments, and if a sheet or column is missing it just notes the gap rather than failing — that gap later shows up as a Data Quality penalty instead of a crash.

### The scoring logic (rule engine)

This is the part that actually decides Red/Amber/Green, and it's deliberately **not** AI — it's a fixed, auditable formula so the same input always gives the same output. Six dimensions, each scored 0.0 (worst) to 1.0 (best), combined with fixed weights that sum to 1.00:

| Dimension | Weight | What it looks at | How it's scored |
|---|---|---|---|
| Schedule Performance | 25% | Are tasks running late, and by how much | `1.0 − (delay_ratio × 0.5) − min(avg_variance_days / 30, 0.5)` |
| Milestone Completion | 20% | Are committed milestones being hit | `1.0 − (overdue_milestones / total_milestones × 1.2)`, floored at 0 |
| Task Completion | 20% | Raw progress | `completion_percent / 100` |
| Risk Exposure | 15% | Open risks, weighted by severity | `1.0 − min(1.0, high×0.25 + medium×0.10)` |
| Critical Path Blockers | 10% | Are critical-path tasks stuck | `1.0 − (blocked_critical_tasks / total_critical_tasks)` |
| Data Quality | 10% | Can the other 5 numbers be trusted | `1.0 − (0.18 × missing_data_categories)` |

Composite score = the weighted sum of all six. Thresholds: **Green ≥ 0.70**, **Amber 0.40–0.69**, **Red < 0.40**.

A couple of deliberate choices worth calling out:
- Milestones are weighted more punitively than ordinary tasks (`× 1.2`) because they're commitments, not just line items.
- High/critical risks cost 4x more than medium ones, and closed/resolved risks don't count against you.
- If a whole category of data is missing (say, no milestones sheet at all), that dimension gets a neutral default (0.6) rather than a 0 — the gap itself is penalised once, cleanly, in Data Quality, instead of being punished twice.
- Every dimension carries a plain-English rationale string (e.g. *"3/12 tasks delayed; avg schedule variance +4.2 days"*), and that rationale follows the score into the app, the PDF, and the PPTX — nothing is a black box.

### Where Gemini fits in — and the consistency guarantee

When you flip on Gemini AI in the sidebar, the app builds a structured prompt out of the rule-engine result (all six dimension scores + rationale, top risks, critical blockers, stakeholder comments) and asks Gemini for a JSON response: an executive summary, plain-English reasoning, a risk list, recommendations, missing-data notes, and next week's priorities.

Here's the important bit: **the RAG colour and confidence you see always come from the rule engine, whether Gemini is on or off.** Gemini used to be allowed to overwrite the colour, which meant the same file could come out Amber with Gemini off and Red with Gemini on — not something you can trust a report on. Now Gemini is purely additive: it explains, it doesn't decide. If Gemini's own read genuinely disagrees with the rule engine, that opinion is kept for transparency (`gemini_rag` / `gemini_agrees`, shown as "advisory only" in the UI) and a note gets appended to the reasoning — but the badge and the score never move because of it. If the Gemini call fails or times out, the pipeline just falls back to the rule-engine summary and keeps going.

### Turning that into reports

- `src/pdf_generator.py` (ReportLab) builds a per-project weekly PDF — cover page, KPIs, dimension breakdown, task table, risk register, AI reasoning — and a portfolio summary PDF.
- `src/ppt_generator.py` (python-pptx) builds a 5-slide per-project deck (Title → Dashboard → Progress/Milestones → Risk Register → Recommendations) and a 7-slide portfolio deck.
- `src/slide_renderer.py` renders the same slide content as plain HTML so it can be previewed live inside the Streamlit app, without opening the PPTX.
- `src/portfolio.py` rolls all analysed projects up into portfolio stats: RAG distribution, average score, and a one-line health signal like *"Portfolio under pressure — 3 of 8 projects Amber or Red."*

---

## Notes on the approach

- **Deterministic first, AI second.** The rule engine gives a stable, explainable baseline that doesn't depend on an external API being up. AI adds value on top; it doesn't replace the scoring.
- **Weighted, not averaged.** Schedule and milestones count for more than raw completion %, because a project can look 80% done while every deliverable that actually matters is late.
- **Every number has a reason attached.** Rationale strings travel with the score into every output format — app, PDF, and PPTX.
- **Nothing crashes on messy input.** Missing sheets, missing columns, a Gemini timeout — all of it degrades to a lower-confidence but still valid report instead of an error page.

## Possible next steps

- Historical trend tracking (store run results, chart RAG drift over time)
- Support for `.mpp` (native MS Project) files
- Budget variance as a seventh scoring dimension
- Slack/Teams notification on RAG change
- Configurable thresholds per organisation
