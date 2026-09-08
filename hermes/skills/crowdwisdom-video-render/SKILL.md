---
name: crowdwisdom-video-render
description: Compile the hero storyboard into an OpenMontage production package and drive the cinematic pipeline to a finished MP4.
version: 1.0.0
author: CrowdWisdom Video Ads Agent
license: MIT
metadata:
  hermes:
    tags: [Marketing, Advertising, Video, CrowdWisdom]
    related_skills: [crowdwisdom-ad-mining, crowdwisdom-insight-extraction, crowdwisdom-icp-research, crowdwisdom-script-forge]
required_environment_variables:
  - name: OPENMONTAGE_HOME
    prompt: Path to an OpenMontage checkout
    help: Clone https://github.com/calesthio/OpenMontage and run make setup
    required_for: final render
---

# CrowdWisdom - OpenMontage render

Compile the hero storyboard into an OpenMontage production package and drive the cinematic pipeline to a finished MP4.

## When to Use

The task asks to render, produce, or generate the actual video file.

## Why it is built this way

- OpenMontage is instruction-driven: its Rule Zero is that production goes through a pipeline, never through ad-hoc scripts calling its tools.
- The cut is already locked by the time this stage runs. Shot boundaries are the edit and the per-shot prompts already carry the grade.

## Quick Reference

| What | Command |
|---|---|
| Run this stage | `python -m cwt_ads.cli stage video --run <run_id>` |
| Run it with no API keys | `python -m cwt_ads.cli stage video --run <run_id> --offline` |
| Check configuration | `python -m cwt_ads.cli doctor` |

Run every command from the repository root:

    cd ${HERMES_SKILL_DIR}/../../..

## Procedure

1. Confirm 04_storyboards.json exists and OPENMONTAGE_HOME points at a checkout containing pipeline_defs/cinematic.yaml.
2. Run the stage command below. It writes 06_openmontage_brief.json plus a production package (BRIEF.md + shotlist.json) inside the OpenMontage checkout.
3. Inside OpenMontage, read AGENT_GUIDE.md, then pipeline_defs/cinematic.yaml, then each stage director skill before doing that stage.
4. Announce provider and model before any paid generation call. Prefer free providers that can hold the grade.
5. Deliver the MP4 to output/<run>/ad.mp4 and complete with its absolute path.

## Pitfalls

- Never re-time the cut or rewrite the shot prompts - they were authored against the brand look block.
- ffmpeg must be on PATH for composition. If it is not, block the task and say so.
- If OPENMONTAGE_HOME is unset, the deliverable is the animatic. Report that honestly rather than claiming a render.

## Verification

output/<run>/ad.mp4 exists, is 30-60 seconds long, and matches the aspect ratio in 06_openmontage_brief.json.

Then call `kanban_complete()` with the artifact paths in metadata. If an input
artifact is missing, call `kanban_block()` with the reason - never re-derive
work that belongs to another agent.
