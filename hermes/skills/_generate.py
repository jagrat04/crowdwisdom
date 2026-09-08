"""Generates the SKILL.md for each CrowdWisdom Hermes skill.

Kept in the repo so the five skills stay consistent with each other and with
config/pipeline.yaml. Run it from the repository root:

    python hermes/skills/_generate.py
"""

from __future__ import annotations

from pathlib import Path

REPO_TOKEN = "${HERMES_SKILL_DIR}/../../.."

SKILLS = [
    dict(
        stage="mine",
        name="crowdwisdom-ad-mining",
        title="CrowdWisdom - Meta Ad Library mining",
        desc=(
            "Mine the Meta Ad Library through Apify for trading-niche video ads live in the "
            "last 30 days and rank them by longevity, scale and ICP relevance."
        ),
        env=[
            (
                "APIFY_TOKEN",
                "Apify API token",
                "Free token at https://console.apify.com/settings/integrations",
                "Meta Ad Library scraping",
            )
        ],
        when=(
            "The task asks for winning ads, competitor ads, ad research, or swipe-file mining "
            "in the trading / investing niche."
        ),
        why=[
            "The Ad Library publishes no spend and no performance, so what-is-working has to "
            "be inferred from two signals that ARE in the payload: how long an ad has been "
            "running, and how many creative variants are collated under it.",
            "Relevance is judged by the agent rather than by keyword match, because the same "
            "ad appears under many different vocabularies.",
        ],
        steps=[
            "Confirm APIFY_TOKEN is set. If it is not, run with --offline and say so in the "
            "completion summary - never fabricate ads.",
            "Run the stage command below. It builds one Meta Ad Library search URL per "
            "configured keyword, runs apify/facebook-ads-scraper, normalises the payload and "
            "filters to the 30-day window.",
            "Read output/<run>/01_winning_ads.json and sanity-check the top three: does the "
            "copy actually target a self-directed retail trader?",
            "Complete the task with the artifact path and the number of ads that survived the "
            "window filter.",
        ],
        pitfalls=[
            "Meta returns several field spellings for the same value. Use the normaliser in "
            "src/cwt_ads/tools/apify_client.py rather than reading raw keys.",
            "An ad with no end_date and is_active true is still running - it counts as inside "
            "the window.",
            "Do not raise resultsLimit without checking the Apify billing dashboard first.",
        ],
        verify=(
            "output/<run>/01_winning_ads.json exists, total_in_window is greater than zero, "
            "and every ad in the ads array has a non-zero winner_score."
        ),
    ),
    dict(
        stage="insight",
        name="crowdwisdom-insight-extraction",
        title="CrowdWisdom - marketing teardown",
        desc=(
            "Reverse-engineer winning ads into pain, promise, hook device and proof structure, "
            "and name the category conventions worth breaking."
        ),
        env=[
            (
                "OPENROUTER_API_KEY",
                "OpenRouter API key",
                "https://openrouter.ai/keys",
                "agent reasoning",
            )
        ],
        when=(
            "The task asks what is working in competitor ads and why, or asks for pain "
            "clusters, ICP refinement, or creative whitespace."
        ),
        why=[
            "A teardown that only summarises copy is worthless. The output has to name the "
            "mechanism: what the ad DOES to a viewer in the first three seconds.",
            "The two fields that matter downstream are category_conventions (what everybody "
            "does) and whitespace (what nobody does). The film is built out of the gap.",
        ],
        steps=[
            "Confirm 01_winning_ads.json exists in the run folder. If it does not, block the "
            "task - do not re-scrape.",
            "Run the stage command below.",
            "Read 02_ad_insights.json. If whitespace reads like a slogan rather than an "
            "observation, the teardown is too shallow; re-run it.",
            "Complete with the number of pain clusters and the whitespace statement.",
        ],
        pitfalls=[
            "Do not let the model invent a pain that no ad in the set expresses.",
            "An ad that wins on spend rather than craft should be labelled as such, not "
            "credited with technique it does not have.",
        ],
        verify=(
            "02_ad_insights.json has at least three pain_clusters, a non-empty whitespace, and "
            "5-7 search_queries_for_research."
        ),
    ),
    dict(
        stage="research",
        name="crowdwisdom-icp-research",
        title="CrowdWisdom - last-month ICP research",
        desc=(
            "Test hypothesised trader pains against the last 30 days of the open web via "
            "Tavily and Exa, and return verbatim language with sources."
        ),
        env=[
            (
                "TAVILY_API_KEY",
                "Tavily API key",
                "Free tier at https://app.tavily.com",
                "time-boxed web search",
            ),
            ("EXA_API_KEY", "Exa API key", "Free tier at https://dashboard.exa.ai", "neural search"),
        ],
        when=(
            "The task asks to validate pains, find ICP language, or gather evidence from the "
            "last month."
        ),
        why=[
            "Ads tell you what marketers believe. The open web tells you what traders actually "
            "said. The script needs the second one.",
            "Every query is constrained to the last 30 days, per the brief - a two-year-old "
            "forum thread is not evidence about this month.",
        ],
        steps=[
            "Confirm 02_ad_insights.json exists. Its search_queries_for_research field is the "
            "query set - do not invent your own.",
            "Run the stage command below. Tavily and Exa both run when both keys are present; "
            "results are de-duplicated by URL.",
            "Read 03_research.json. If icp_language is empty the search returned nothing "
            "usable - say so rather than padding it.",
            "Complete with the number of findings and the providers actually used.",
        ],
        pitfalls=[
            "Never invent a quote. If the evidence is thin, the synthesis must say so.",
            "Tavily and Exa take different date parameters; use the client in "
            "src/cwt_ads/tools/search.py.",
        ],
        verify="03_research.json lists providers_used, and every finding carries a URL.",
    ),
    dict(
        stage="script",
        name="crowdwisdom-script-forge",
        title="CrowdWisdom - cinematic script forge",
        desc=(
            "Write three cinematic 30-60s ad scripts with engineered visual hooks and "
            "shot-by-shot storyboards a video model can execute."
        ),
        env=[
            (
                "OPENROUTER_API_KEY",
                "OpenRouter API key",
                "https://openrouter.ai/keys",
                "agent reasoning",
            )
        ],
        when="The task asks for ad scripts, storyboards, a creative concept, or a visual hook.",
        why=[
            "Three mandated angles: pain and ICP from research, CrowdWisdom proprietary data, "
            "and how the product changes the trading result.",
            "The hook must be a visual EVENT inside three seconds and work with the sound off. "
            "A hook that needs its words read is a caption.",
            "No number reaches the screen unless it is in config/brand.yaml verified_claims or "
            "in the prediction export in data/unique/.",
        ],
        steps=[
            "Confirm 02_ad_insights.json and 03_research.json exist. Block if either is missing.",
            "Run the stage command below. It writes 04_storyboards.json and a playable animatic "
            "at 05_storyboard.html.",
            "Open the animatic and watch the first three seconds of each film. If you can "
            "imagine scrolling past it, the hook has failed and the stage should be re-run.",
            "Complete with the three script ids, their runtimes, and which one is the hero.",
        ],
        pitfalls=[
            "Models drift on timing and leave gaps between shots. The timeline repairer snaps "
            "shots contiguous and rescales into the 30-60s window - do not hand-edit timecodes.",
            "Watch for banned tropes from brand.yaml creeping back in: talking heads, screen "
            "recordings, rising arrows, profit screenshots.",
        ],
        verify=(
            "04_storyboards.json has three scripts, each 30-60s, each with a visual_hook and "
            "contiguous shots; 05_storyboard.html opens and plays."
        ),
    ),
    dict(
        stage="video",
        name="crowdwisdom-video-render",
        title="CrowdWisdom - OpenMontage render",
        desc=(
            "Compile the hero storyboard into an OpenMontage production package and drive the "
            "cinematic pipeline to a finished MP4."
        ),
        env=[
            (
                "OPENMONTAGE_HOME",
                "Path to an OpenMontage checkout",
                "Clone https://github.com/calesthio/OpenMontage and run make setup",
                "final render",
            )
        ],
        when="The task asks to render, produce, or generate the actual video file.",
        why=[
            "OpenMontage is instruction-driven: its Rule Zero is that production goes through a "
            "pipeline, never through ad-hoc scripts calling its tools.",
            "The cut is already locked by the time this stage runs. Shot boundaries are the "
            "edit and the per-shot prompts already carry the grade.",
        ],
        steps=[
            "Confirm 04_storyboards.json exists and OPENMONTAGE_HOME points at a checkout "
            "containing pipeline_defs/cinematic.yaml.",
            "Run the stage command below. It writes 06_openmontage_brief.json plus a production "
            "package (BRIEF.md + shotlist.json) inside the OpenMontage checkout.",
            "Inside OpenMontage, read AGENT_GUIDE.md, then pipeline_defs/cinematic.yaml, then "
            "each stage director skill before doing that stage.",
            "Announce provider and model before any paid generation call. Prefer free providers "
            "that can hold the grade.",
            "Deliver the MP4 to output/<run>/ad.mp4 and complete with its absolute path.",
        ],
        pitfalls=[
            "Never re-time the cut or rewrite the shot prompts - they were authored against the "
            "brand look block.",
            "ffmpeg must be on PATH for composition. If it is not, block the task and say so.",
            "If OPENMONTAGE_HOME is unset, the deliverable is the animatic. Report that "
            "honestly rather than claiming a render.",
        ],
        verify=(
            "output/<run>/ad.mp4 exists, is 30-60 seconds long, and matches the aspect ratio in "
            "06_openmontage_brief.json."
        ),
    ),
]


def render(skill: dict, others: list[str]) -> str:
    lines = [
        "---",
        "name: " + skill["name"],
        "description: " + skill["desc"],
        "version: 1.0.0",
        "author: CrowdWisdom Video Ads Agent",
        "license: MIT",
        "metadata:",
        "  hermes:",
        "    tags: [Marketing, Advertising, Video, CrowdWisdom]",
        "    related_skills: [" + ", ".join(others) + "]",
    ]
    if skill["env"]:
        lines.append("required_environment_variables:")
        for name, prompt, help_text, required_for in skill["env"]:
            lines += [
                "  - name: " + name,
                "    prompt: " + prompt,
                "    help: " + help_text,
                "    required_for: " + required_for,
            ]
    lines += [
        "---",
        "",
        "# " + skill["title"],
        "",
        skill["desc"],
        "",
        "## When to Use",
        "",
        skill["when"],
        "",
        "## Why it is built this way",
        "",
    ]
    lines += ["- " + w for w in skill["why"]]
    lines += [
        "",
        "## Quick Reference",
        "",
        "| What | Command |",
        "|---|---|",
        "| Run this stage | `python -m cwt_ads.cli stage " + skill["stage"] + " --run <run_id>` |",
        "| Run it with no API keys | `python -m cwt_ads.cli stage "
        + skill["stage"]
        + " --run <run_id> --offline` |",
        "| Check configuration | `python -m cwt_ads.cli doctor` |",
        "",
        "Run every command from the repository root:",
        "",
        "    cd " + REPO_TOKEN,
        "",
        "## Procedure",
        "",
    ]
    lines += [str(i + 1) + ". " + s for i, s in enumerate(skill["steps"])]
    lines += ["", "## Pitfalls", ""]
    lines += ["- " + p for p in skill["pitfalls"]]
    lines += [
        "",
        "## Verification",
        "",
        skill["verify"],
        "",
        "Then call `kanban_complete()` with the artifact paths in metadata. If an input",
        "artifact is missing, call `kanban_block()` with the reason - never re-derive",
        "work that belongs to another agent.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parent
    for skill in SKILLS:
        others = [s["name"] for s in SKILLS if s is not skill]
        target = root / skill["name"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(render(skill, others), encoding="utf-8")
        print("wrote", (target / "SKILL.md").as_posix())


if __name__ == "__main__":
    main()
