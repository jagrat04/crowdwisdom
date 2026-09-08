---
name: crowdwisdom-insight-extraction
description: Reverse-engineer winning ads into pain, promise, hook device and proof structure, and name the category conventions worth breaking.
version: 1.0.0
author: CrowdWisdom Video Ads Agent
license: MIT
metadata:
  hermes:
    tags: [Marketing, Advertising, Video, CrowdWisdom]
    related_skills: [crowdwisdom-ad-mining, crowdwisdom-icp-research, crowdwisdom-script-forge, crowdwisdom-video-render]
required_environment_variables:
  - name: OPENROUTER_API_KEY
    prompt: OpenRouter API key
    help: https://openrouter.ai/keys
    required_for: agent reasoning
---

# CrowdWisdom - marketing teardown

Reverse-engineer winning ads into pain, promise, hook device and proof structure, and name the category conventions worth breaking.

## When to Use

The task asks what is working in competitor ads and why, or asks for pain clusters, ICP refinement, or creative whitespace.

## Why it is built this way

- A teardown that only summarises copy is worthless. The output has to name the mechanism: what the ad DOES to a viewer in the first three seconds.
- The two fields that matter downstream are category_conventions (what everybody does) and whitespace (what nobody does). The film is built out of the gap.

## Quick Reference

| What | Command |
|---|---|
| Run this stage | `python -m cwt_ads.cli stage insight --run <run_id>` |
| Run it with no API keys | `python -m cwt_ads.cli stage insight --run <run_id> --offline` |
| Check configuration | `python -m cwt_ads.cli doctor` |

Run every command from the repository root:

    cd ${HERMES_SKILL_DIR}/../../..

## Procedure

1. Confirm 01_winning_ads.json exists in the run folder. If it does not, block the task - do not re-scrape.
2. Run the stage command below.
3. Read 02_ad_insights.json. If whitespace reads like a slogan rather than an observation, the teardown is too shallow; re-run it.
4. Complete with the number of pain clusters and the whitespace statement.

## Pitfalls

- Do not let the model invent a pain that no ad in the set expresses.
- An ad that wins on spend rather than craft should be labelled as such, not credited with technique it does not have.

## Verification

02_ad_insights.json has at least three pain_clusters, a non-empty whitespace, and 5-7 search_queries_for_research.

Then call `kanban_complete()` with the artifact paths in metadata. If an input
artifact is missing, call `kanban_block()` with the reason - never re-derive
work that belongs to another agent.
