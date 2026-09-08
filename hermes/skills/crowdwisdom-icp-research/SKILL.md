---
name: crowdwisdom-icp-research
description: Test hypothesised trader pains against the last 30 days of the open web via Tavily and Exa, and return verbatim language with sources.
version: 1.0.0
author: CrowdWisdom Video Ads Agent
license: MIT
metadata:
  hermes:
    tags: [Marketing, Advertising, Video, CrowdWisdom]
    related_skills: [crowdwisdom-ad-mining, crowdwisdom-insight-extraction, crowdwisdom-script-forge, crowdwisdom-video-render]
required_environment_variables:
  - name: TAVILY_API_KEY
    prompt: Tavily API key
    help: Free tier at https://app.tavily.com
    required_for: time-boxed web search
  - name: EXA_API_KEY
    prompt: Exa API key
    help: Free tier at https://dashboard.exa.ai
    required_for: neural search
---

# CrowdWisdom - last-month ICP research

Test hypothesised trader pains against the last 30 days of the open web via Tavily and Exa, and return verbatim language with sources.

## When to Use

The task asks to validate pains, find ICP language, or gather evidence from the last month.

## Why it is built this way

- Ads tell you what marketers believe. The open web tells you what traders actually said. The script needs the second one.
- Every query is constrained to the last 30 days, per the brief - a two-year-old forum thread is not evidence about this month.

## Quick Reference

| What | Command |
|---|---|
| Run this stage | `python -m cwt_ads.cli stage research --run <run_id>` |
| Run it with no API keys | `python -m cwt_ads.cli stage research --run <run_id> --offline` |
| Check configuration | `python -m cwt_ads.cli doctor` |

Run every command from the repository root:

    cd ${HERMES_SKILL_DIR}/../../..

## Procedure

1. Confirm 02_ad_insights.json exists. Its search_queries_for_research field is the query set - do not invent your own.
2. Run the stage command below. Tavily and Exa both run when both keys are present; results are de-duplicated by URL.
3. Read 03_research.json. If icp_language is empty the search returned nothing usable - say so rather than padding it.
4. Complete with the number of findings and the providers actually used.

## Pitfalls

- Never invent a quote. If the evidence is thin, the synthesis must say so.
- Tavily and Exa take different date parameters; use the client in src/cwt_ads/tools/search.py.

## Verification

03_research.json lists providers_used, and every finding carries a URL.

Then call `kanban_complete()` with the artifact paths in metadata. If an input
artifact is missing, call `kanban_block()` with the reason - never re-derive
work that belongs to another agent.
