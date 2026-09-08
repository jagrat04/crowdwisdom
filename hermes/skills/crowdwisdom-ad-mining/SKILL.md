---
name: crowdwisdom-ad-mining
description: Mine the Meta Ad Library through Apify for trading-niche video ads live in the last 30 days and rank them by longevity, scale and ICP relevance.
version: 1.0.0
author: CrowdWisdom Video Ads Agent
license: MIT
metadata:
  hermes:
    tags: [Marketing, Advertising, Video, CrowdWisdom]
    related_skills: [crowdwisdom-insight-extraction, crowdwisdom-icp-research, crowdwisdom-script-forge, crowdwisdom-video-render]
required_environment_variables:
  - name: APIFY_TOKEN
    prompt: Apify API token
    help: Free token at https://console.apify.com/settings/integrations
    required_for: Meta Ad Library scraping
---

# CrowdWisdom - Meta Ad Library mining

Mine the Meta Ad Library through Apify for trading-niche video ads live in the last 30 days and rank them by longevity, scale and ICP relevance.

## When to Use

The task asks for winning ads, competitor ads, ad research, or swipe-file mining in the trading / investing niche.

## Why it is built this way

- The Ad Library publishes no spend and no performance, so what-is-working has to be inferred from two signals that ARE in the payload: how long an ad has been running, and how many creative variants are collated under it.
- Relevance is judged by the agent rather than by keyword match, because the same ad appears under many different vocabularies.

## Quick Reference

| What | Command |
|---|---|
| Run this stage | `python -m cwt_ads.cli stage mine --run <run_id>` |
| Run it with no API keys | `python -m cwt_ads.cli stage mine --run <run_id> --offline` |
| Check configuration | `python -m cwt_ads.cli doctor` |

Run every command from the repository root:

    cd ${HERMES_SKILL_DIR}/../../..

## Procedure

1. Confirm APIFY_TOKEN is set. If it is not, run with --offline and say so in the completion summary - never fabricate ads.
2. Run the stage command below. It builds one Meta Ad Library search URL per configured keyword, runs apify/facebook-ads-scraper, normalises the payload and filters to the 30-day window.
3. Read output/<run>/01_winning_ads.json and sanity-check the top three: does the copy actually target a self-directed retail trader?
4. Complete the task with the artifact path and the number of ads that survived the window filter.

## Pitfalls

- Meta returns several field spellings for the same value. Use the normaliser in src/cwt_ads/tools/apify_client.py rather than reading raw keys.
- An ad with no end_date and is_active true is still running - it counts as inside the window.
- Do not raise resultsLimit without checking the Apify billing dashboard first.

## Verification

output/<run>/01_winning_ads.json exists, total_in_window is greater than zero, and every ad in the ads array has a non-zero winner_score.

Then call `kanban_complete()` with the artifact paths in metadata. If an input
artifact is missing, call `kanban_block()` with the reason - never re-derive
work that belongs to another agent.
