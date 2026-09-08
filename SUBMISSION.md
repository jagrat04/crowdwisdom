# Submission checklist — CrowdWisdom Video Ads Agent

For `gilad@crowdwisdomtrading.com`.

## What the brief asked for, and where it is

| Requirement | Where |
|---|---|
| Python project on the **Hermes** agent framework | [`src/cwt_ads/hermes_runtime.py`](src/cwt_ads/hermes_runtime.py) (in-process `AIAgent`), [`src/cwt_ads/kanban.py`](src/cwt_ads/kanban.py) + [`hermes/`](hermes/) (the board) |
| LLM via OpenRouter / NVIDIA | [`src/cwt_ads/llm.py`](src/cwt_ads/llm.py) — OpenRouter primary, NVIDIA NIM fallback |
| **Ads Manager Agent** — best working ads, last 30 days, via Apify, saved to JSON | [`agents/ads_manager.py`](src/cwt_ads/agents/ads_manager.py) → `output/<run>/01_winning_ads.json` |
| Agent that extracts marketing / pain / concepts from those ads | [`agents/insight_agent.py`](src/cwt_ads/agents/insight_agent.py) → `02_ad_insights.json` |
| **Script Agent**, 3 scripts: (a) pain + ICP via Tavily/Exa limited to last month, (b) our unique data, (c) how CrowdWisdom helps results | [`agents/script_agent.py`](src/cwt_ads/agents/script_agent.py) → `04_storyboards.json`. Angles `pain_led`, `data_led`, `outcome_led` |
| A visual hook that stops the scroll | `visual_hook` on every script — concept, frame 0, the event inside 3s, and the attention mechanism |
| Script saved in human-readable JSON | `04_storyboards.json` — indented, typed, with a `_meta` provenance block. Plus `05_storyboard.html`, which plays |
| **Video Agent** — 30–60s ad via OpenMontage | [`render/openmontage.py`](src/cwt_ads/render/openmontage.py) → `06_openmontage_brief.json` → `ad.mp4` |
| Tokens so you can re-run without burning your accounts | See below |
| Video of the Hermes Kanban | See below |

## Tokens

> Fill these in before sending. They are the free-tier keys used for the recorded run —
> please rotate or revoke them after you have re-run the pipeline.

```
APIFY_TOKEN=
TAVILY_API_KEY=
EXA_API_KEY=
OPENROUTER_API_KEY=
```

Drop them into `.env` (there is a `.env.example` to copy) and run:

```bash
python -m cwt_ads.cli doctor      # confirms what is wired up
python -m cwt_ads.cli run         # the full team, live
```

To evaluate the code and the creative without spending a cent of anyone's credit:

```bash
python -m cwt_ads.cli run --offline
open output/latest/05_storyboard.html
```

## Kanban recording

Recorded with:

```bash
python -m cwt_ads.cli kanban bootstrap
hermes dashboard          # Kanban tab
```

Five profiles — `cwt_ads_manager`, `cwt_insight_miner`, `cwt_market_researcher`, `cwt_script_writer`, `cwt_video_director` — claiming five linked tasks through triage → ready → running → done, each handoff a row on the board.

`python -m cwt_ads.cli kanban plan` prints the exact commands without touching anything, if you want to read the graph before creating it.

## The one thing to look at first

`output/latest/05_storyboard.html`, hero tab (**WEIGHTED**), press play.

It is built on the real prediction export you linked in the brief. The film leads with a confidence of **46 out of 100** and an empty listening channel, because the category sells certainty and the only credible way to sell calibration is to show a number that does not flatter you. Nobody fakes a weakness.
