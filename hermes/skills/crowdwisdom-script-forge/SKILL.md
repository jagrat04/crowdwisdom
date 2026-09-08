---
name: crowdwisdom-script-forge
description: Write three cinematic 30-60s ad scripts with engineered visual hooks and shot-by-shot storyboards a video model can execute.
version: 1.0.0
author: CrowdWisdom Video Ads Agent
license: MIT
metadata:
  hermes:
    tags: [Marketing, Advertising, Video, CrowdWisdom]
    related_skills: [crowdwisdom-ad-mining, crowdwisdom-insight-extraction, crowdwisdom-icp-research, crowdwisdom-video-render]
required_environment_variables:
  - name: OPENROUTER_API_KEY
    prompt: OpenRouter API key
    help: https://openrouter.ai/keys
    required_for: agent reasoning
---

# CrowdWisdom - cinematic script forge

Write three cinematic 30-60s ad scripts with engineered visual hooks and shot-by-shot storyboards a video model can execute.

## When to Use

The task asks for ad scripts, storyboards, a creative concept, or a visual hook.

## Why it is built this way

- Three mandated angles: pain and ICP from research, CrowdWisdom proprietary data, and how the product changes the trading result.
- The hook must be a visual EVENT inside three seconds and work with the sound off. A hook that needs its words read is a caption.
- No number reaches the screen unless it is in config/brand.yaml verified_claims or in the prediction export in data/unique/.

## Quick Reference

| What | Command |
|---|---|
| Run this stage | `python -m cwt_ads.cli stage script --run <run_id>` |
| Run it with no API keys | `python -m cwt_ads.cli stage script --run <run_id> --offline` |
| Check configuration | `python -m cwt_ads.cli doctor` |

Run every command from the repository root:

    cd ${HERMES_SKILL_DIR}/../../..

## Procedure

1. Confirm 02_ad_insights.json and 03_research.json exist. Block if either is missing.
2. Run the stage command below. It writes 04_storyboards.json and a playable animatic at 05_storyboard.html.
3. Open the animatic and watch the first three seconds of each film. If you can imagine scrolling past it, the hook has failed and the stage should be re-run.
4. Complete with the three script ids, their runtimes, and which one is the hero.

## Pitfalls

- Models drift on timing and leave gaps between shots. The timeline repairer snaps shots contiguous and rescales into the 30-60s window - do not hand-edit timecodes.
- Watch for banned tropes from brand.yaml creeping back in: talking heads, screen recordings, rising arrows, profit screenshots.

## Verification

04_storyboards.json has three scripts, each 30-60s, each with a visual_hook and contiguous shots; 05_storyboard.html opens and plays.

Then call `kanban_complete()` with the artifact paths in metadata. If an input
artifact is missing, call `kanban_block()` with the reason - never re-derive
work that belongs to another agent.
