# CrowdWisdom Video Ads Agent

A five-agent marketing team, built on the [Hermes agent framework](https://github.com/NousResearch/hermes-agent), that mines the Meta Ad Library for what is actually working in the trading niche, tears it down into marketing mechanics, tests those mechanics against the last month of the open web, writes three cinematic 30–60 second ad scripts for [crowdwisdomtrading.com](https://crowdwisdomtrading.com), and drives [OpenMontage](https://github.com/calesthio/OpenMontage) to render the hero cut.

It does not write text ads. It writes short films.

```bash
pip install -r requirements.txt
python -m cwt_ads.cli run --offline      # full pipeline, no API keys, ~10 seconds
open output/latest/05_storyboard.html    # the animatic actually plays
```

---

## The team

| # | Agent | Hermes profile | Does | Writes |
|---|---|---|---|---|
| 1 | **Ads Manager** | `cwt_ads_manager` | Mines the Meta Ad Library via Apify for trading-niche **video** ads live in the last 30 days; ranks them | `01_winning_ads.json` |
| 2 | **Creative Strategist** | `cwt_insight_miner` | Reverse-engineers the winners into pain / promise / hook device / proof; names the conventions to break | `02_ad_insights.json` |
| 3 | **Market Researcher** | `cwt_market_researcher` | Tests those pains against the last 30 days of the web via Tavily + Exa; returns verbatim trader language | `03_research.json` |
| 4 | **Creative Director** | `cwt_script_writer` | Writes three films — one per mandated angle — with engineered visual hooks and shot-by-shot storyboards | `04_storyboards.json`, `05_storyboard.html` |
| 5 | **Video Director** | `cwt_video_director` | Compiles the hero cut into an OpenMontage production package and drives the render | `06_openmontage_brief.json`, `ad.mp4` |

Each agent is a Hermes profile with its own model, toolset allow-list and skill. The same five agents run two ways — see [Two ways to run the team](#two-ways-to-run-the-team).

---

## Quickstart

### 1. Install

```bash
git clone <this repo> && cd crowdwisdom
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. See what your machine can do

```bash
python -m cwt_ads.cli doctor
```

It reports every component and what is missing. Nothing is required to get a full run — the pipeline degrades honestly and tells you which path it took.

### 3. Run

```bash
# no keys at all: bundled Meta Ad Library fixture + the reference films
python -m cwt_ads.cli run --offline

# live: real Apify mining, real Tavily/Exa research, agent-written scripts
python -m cwt_ads.cli run

# everything except the MP4 render
python -m cwt_ads.cli run --no-render

# re-run a single stage against an existing run
python -m cwt_ads.cli stage script --run run_20260907_182503
```

### 4. Look at the output

```
output/run_YYYYMMDD_HHMMSS/
├── 00_run_summary.json          run manifest: what ran, on which transport
├── 01_winning_ads.json          top ads, last 30 days, with scores + rationale
├── 02_ad_insights.json          teardowns, pain clusters, category whitespace
├── 03_research.json             sourced findings from the last 30 days
├── 04_storyboards.json          three films, shot by shot
├── 05_storyboard.html           ← open this. It plays.
├── 06_openmontage_brief.json    the production brief handed to OpenMontage
└── ad.mp4                       the render (when OpenMontage is configured)
```

`05_storyboard.html` is a self-contained animatic: shots advance on their real timecodes, on-screen text lands where the script says it lands, the palette is the brand palette, and each beat has its own art-directed ground. No build step, no CDN, no keys. It is the fastest honest way to answer *does the first three seconds work?* before spending a cent on generation.

---

## Keys

Everything has a free tier. Nothing is mandatory.

| Variable | For | Get one |
|---|---|---|
| `OPENROUTER_API_KEY` | every agent's reasoning | <https://openrouter.ai/keys> |
| `APIFY_TOKEN` | Meta Ad Library mining | <https://console.apify.com/settings/integrations> |
| `TAVILY_API_KEY` | last-month research | <https://app.tavily.com> |
| `EXA_API_KEY` | last-month research | <https://dashboard.exa.ai> |
| `HERMES_HOME` | in-process Hermes runtime | clone [hermes-agent](https://github.com/NousResearch/hermes-agent) |
| `OPENMONTAGE_HOME` | the MP4 render | clone [OpenMontage](https://github.com/calesthio/OpenMontage), `make setup` |

Missing a key never crashes a run. The Ads Manager falls back to a bundled fixture, the Researcher reports that it ran unsourced, the Creative Director falls back to the reference films, and the Video Director says plainly that no MP4 was produced and why. Every artifact records which transport actually ran in its `_meta` block.

---

## Running on free tiers

Everything here was built and validated against genuinely free accounts, which
surfaced a set of failure modes worth knowing before you re-run it.

**OpenRouter reserves credit against `max_tokens`, not against actual usage.**
A zero-balance account will answer a 20-token probe and then `402` on a real
call, which reads as flakiness and is not. Either fund the account, or set a
free model — `CWT_MODEL=nvidia/nemotron-3.5-lightning:free`. Free models are
also *slow* under load: budget roughly two minutes per agent call.

**`CWT_MODEL` beats `pipeline.yaml`'s `defaults.model`.** That precedence is
deliberate: which models a machine can afford is deployment configuration, not
a creative decision. An explicit per-agent `model:` in `pipeline.yaml` still
wins over both.

**Timeouts are wall-clock, not per-socket.** `requests`' own `timeout` resets on
every chunk, so a throttled provider can trickle bytes indefinitely and hang the
run with no error. Every LLM call is wrapped in a hard deadline
(`CWT_LLM_DEADLINE`, default 240s) and a deadline breach is retried **once** —
a model that cannot finish inside the budget will not finish on the third try.

**Weak models do not respect a schema.** Two failures seen live, both now
handled: the Ads Manager asked for `{"scores":[{"relevance":…}]}` and got
`{"ads":[{"relevance_score":…}]}` — a strict reader was silently discarding a
perfectly good answer; and a teardown came back with `"pain_intensity":
"low|medium|high"`, the schema hint echoed verbatim, which crashed Pydantic
three stages from the end. The score parser now reads five shapes, enum fields
coerce rather than raise, and every report construction has a fallback so one
bad response cannot lose four stages of work.

**Apify's free plan is $5/month of credit, and the actor is pay-per-event.**
A full two-phase mine is roughly $0.20. Check `console.apify.com/billing`
before a demo run; on an exhausted plan the actor returns a bare `403`, which
the client treats as terminal and falls straight through to the fixture.

**Secrets are redacted at the boundary.** Provider errors quote the full request
URL, and Apify puts the token in a query parameter — so it lands in console
output and saved logs. Everything printed or written to an artifact passes
through a redactor first.

## Two ways to run the team

### In-process — `cwt_ads.cli run`

Hermes' `AIAgent` is imported from a local checkout and each agent gets its own system prompt, model and toolset allow-list. Set `HERMES_HOME`, or:

```bash
python -m cwt_ads.cli setup-hermes        # clones hermes-agent into vendor/
cd vendor/hermes-agent && uv sync
```

Without a checkout the runtime falls back to direct OpenRouter calls using the identical prompts, so the repo is useful on a bare machine. `doctor` and every artifact's `_meta` tell you which one ran.

### On the board — Hermes Kanban

The same five agents as five independent profiles claiming tasks off the shared board at `~/.hermes/kanban.db`, with real parent/child dependencies so the dispatcher only starts an agent once its inputs exist.

```bash
python -m cwt_ads.cli kanban plan         # print the exact commands, change nothing
python -m cwt_ads.cli kanban bootstrap    # create the profiles and the linked tasks
hermes kanban watch                       # follow it in the terminal
hermes dashboard                          # or the Kanban tab, live over websocket
```

```
t_ads_manager ──▶ t_insight_agent ──▶ t_research_agent ──▶ t_script_agent ──▶ t_video_agent
cwt_ads_manager   cwt_insight_miner   cwt_market_resea…    cwt_script_writer  cwt_video_director
01_winning_ads    02_ad_insights      03_research          04_storyboards     06_brief + ad.mp4
```

Both paths call the same agent classes and write the same artifacts. The only handoff between agents is the run folder — which is why every stage can also load its inputs from disk. The board graph is documented in [`hermes/kanban/board.yaml`](hermes/kanban/board.yaml); the five skills live in [`hermes/skills/`](hermes/skills/).

---

## How "what is working" is decided

The Meta Ad Library publishes no spend and no performance. So the Ads Manager infers it from two signals that *are* in the payload, plus one the agent judges:

| Signal | Weight | Why |
|---|---|---|
| **Longevity** | 0.45 | A losing ad gets switched off. An ad still running after three weeks is being paid for because it pays back. Log curve — day 7 ≈ 46, day 30 ≈ 76, day 90 = 100. |
| **Scale** | 0.25 | Creative variants collated under one ad. Nobody builds thirty variants of an ad they are about to kill. |
| **ICP relevance** | 0.30 | Judged by the agent, not by keyword match, because "options alerts for busy professionals" and "stop guessing the market" are the same ad wearing different words. |

### Why the mining is two-phase

This is the single least obvious thing in the project, and it only shows up when you look at a live payload rather than the docs.

**Meta's keyword search cannot tell you how long an ad has run.** Every row from `?q=...&search_type=keyword_unordered` comes back with `startDate == endDate == the day you scraped`, a `totalActiveTime` measured in hours, and `collationCount` of 1 — because that view returns *today's delivery record*, not the ad's life. Scoring those rows on longevity would rank a genuine winner below whichever spam ad matched the most keywords.

**Meta's page view does.** A Facebook page URL returns real per-ad `startDate` spanning months. Against `themotleyfool` the captured sample shows ads running 8, 13, 89, 90, 92, 97 and **145** days, with honest collation counts.

So the Ads Manager **discovers advertisers by keyword, then measures them by page**. Every normalised ad carries `longevity_known`; when it is false the scorer drops the longevity term and redistributes its weight proportionally onto scale and relevance rather than crediting a zero. `01_winning_ads.json` records how many rows were affected.

Ads outside the 30-day window are dropped before scoring. `config/pipeline.yaml` sets `mode: pages` by default; `mode: keywords` is available and honestly labelled as longevity-blind.

### The fixture is real

`data/fixtures/meta_ads_sample.json` is **32 genuine Meta ads** captured from the live Apify actor, deliberately spanning both response shapes — 20 keyword rows (longevity absent) and 12 page rows (longevity present) — so the offline path exercises the same normalisation and the same scoring branch as a live run.

---

## The three films

One per mandated angle, all shot for 9:16, all 30–60 seconds, all engineered to work with the sound off.

**`pain_led` — THE LOUD ROOM.** Research-led. A blank phone screen at 06:04 detonates, in a single frame, into forty contradictory alerts that keep growing past the top of frame. Fifteen seconds inside the noise before the product is named. Resolves on a man walking into an ordinary morning — because the promise is calm, not wealth.

**`data_led` — WEIGHTED** *(hero)*. Built on the real CrowdWisdom prediction export in `data/unique/`. Four columns of light are physically weighed in a laboratory; one of them is empty, because Reddit contributed nothing to that call and the platform publishes it as zero rather than padding it. The confidence dial reads 46/100, and the film leads with that. Nobody fakes a weakness.

**`outcome_led` — TWO MONDAYS.** A flawlessly mirrored frame — the same man twice, same desk, same week. At 1.4s only the left one blinks. The only variable is whether he had the consensus, and the hairline divider between the two lives turns out to be the product.

Every number on screen traces to either `config/brand.yaml` `verified_claims` or the prediction export (cited as `data:<ticker>`). Anything else is stripped by the claims audit before the script is saved. Tests assert this.

### The creative constitution

[`config/brand.yaml`](config/brand.yaml) is the single source of truth every agent reads: verified claims with their qualifiers, the ICP, the visual system (palette, grade, lens, motion, texture, typography, sound), the compliance rules — and a **banned list**. No talking heads, no screen recordings, no rising arrows, no profit screenshots, no lambos. If the whole category does it, that is the thing this team is here not to do.

---

## Proprietary data

`data/unique/` holds real CrowdWisdom prediction exports. `tools/unique_data.py` does more than load them — it turns a row into *cinematic facts*: risk/reward computed from the published levels, the spread between the four listening channels, which channels were silent. Because `youtube 10 / x 30 / reddit 0 / groq 60` is a picture, and `confidence 46` is a dial that can move on screen.

Drop more exports into that folder and they are picked up automatically; the Creative Director picks the record with the widest channel spread as the hero, because an ad needs one number that visibly disagrees with another number.

---

## Rendering

OpenMontage is instruction-driven: its Rule Zero is that production goes through a pipeline, never through ad-hoc scripts calling its tools. So this project does not try to be a second orchestrator. The Video Director:

1. compiles the storyboard into a production package (`BRIEF.md` + `shotlist.json`) inside the OpenMontage checkout, with every shot's image prompt already carrying the grade;
2. hands it to a Hermes agent with terminal access working inside that checkout — which is exactly the AI assistant `AGENT_GUIDE.md` expects to be driving it — pointed at the `cinematic` pipeline in atelier mode.

The cut is locked before the render starts. Shot boundaries *are* the edit.

---

## Layout

```
config/brand.yaml            the creative constitution — claims, ICP, look, banned list
config/pipeline.yaml         the agent team and the task graph
data/unique/                 real CrowdWisdom prediction exports
data/fixtures/               32 real Meta Ad Library payloads, both response shapes
hermes/profiles/             one Hermes profile per agent
hermes/skills/               one SKILL.md per stage (generated by _generate.py)
hermes/kanban/               the board definition and its bootstrap
src/cwt_ads/
  hermes_runtime.py          Hermes AIAgent wiring, with an honest fallback
  kanban.py                  the distributed path
  pipeline.py                the in-process path
  schemas.py                 typed contracts for every artifact
  agents/                    the five agents + the reference films
  tools/                     apify, tavily/exa, proprietary data
  render/                    OpenMontage brief + the animatic
tests/                       26 tests over the parts that can be wrong silently
```

---

## Tests

```bash
python -m pytest -q
```

The creative output cannot be unit tested. Everything it depends on can: the 30-day window filter in both directions, the Meta payload normaliser against nested and empty records, the scoring curves, the timeline repair that keeps a film inside 30–60 seconds even when the model returns five minutes with gaps, the claims audit, and the assertion that no banned phrase reached any script.

---

## Compliance

Every script ends on a capital-at-risk / not-financial-advice card. The 74.1% claim never appears without its definition on the same card. No profit is promised, implied, or illustrated. The claims audit runs before any script is written to disk.
