"""Tests for the parts that would silently produce a wrong ad.

The creative output cannot be unit tested. Everything it depends on can:
the 30-day window filter, the winner scoring curve, the timeline repair that
keeps a film inside 30-60 seconds, and the claims audit that stops an invented
number reaching the screen.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from cwt_ads.agents.ads_manager import AdsManagerAgent
from cwt_ads.agents.fallback_scripts import fallback_script
from cwt_ads.agents.script_agent import ScriptAgent
from cwt_ads.config import FIXTURE_DIR, brand, pipeline
from cwt_ads.kanban import plan
from cwt_ads.render import openmontage, previz
from cwt_ads.schemas import AdScript, Shot, StoryboardBundle
from cwt_ads.tools import apify_client, unique_data

TODAY = datetime.now(timezone.utc).date()


# ── the 30-day window ───────────────────────────────────────────────────────
def test_active_ad_with_no_end_date_is_in_window():
    ad = {"start_date": (TODAY - timedelta(days=400)).isoformat(), "end_date": None, "is_active": True}
    assert apify_client.within_window(ad, 30)


def test_ad_that_stopped_last_year_is_out_of_window():
    ad = {
        "start_date": (TODAY - timedelta(days=400)).isoformat(),
        "end_date": (TODAY - timedelta(days=370)).isoformat(),
        "is_active": False,
    }
    assert not apify_client.within_window(ad, 30)


def test_ad_that_stopped_last_week_is_still_in_window():
    ad = {
        "start_date": (TODAY - timedelta(days=60)).isoformat(),
        "end_date": (TODAY - timedelta(days=6)).isoformat(),
        "is_active": False,
    }
    assert apify_client.within_window(ad, 30)


# ── normalisation of Meta payloads ──────────────────────────────────────────
def test_normalise_reads_nested_meta_shape():
    raw = {
        "ad_archive_id": "12345",
        "page_name": "Signal Room",
        "start_date": (TODAY - timedelta(days=10)).isoformat(),
        "is_active": True,
        "total": 8,
        "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
        "snapshot": {
            "body": {"text": "<b>You do not need</b>  more alerts."},
            "cta_text": "Sign up",
            "videos": [{"video_hd_url": "https://v.example.com/a.mp4"}],
        },
        "_cwt_query": "trading signals",
    }
    ad = apify_client.normalise(raw)
    assert ad["ad_archive_id"] == "12345"
    assert ad["ad_copy"] == "You do not need more alerts."  # html stripped, spaces collapsed
    assert ad["media_type"] == "video"
    assert ad["video_urls"] == ["https://v.example.com/a.mp4"]
    assert ad["publisher_platforms"] == ["facebook", "instagram"]
    assert ad["days_running"] == 10
    assert ad["matched_query"] == "trading signals"


def test_normalise_survives_a_payload_with_nothing_in_it():
    ad = apify_client.normalise({})
    assert ad["ad_archive_id"] == ""
    assert ad["days_running"] == 0
    assert ad["media_type"] == "unknown"


def test_search_url_is_a_keyword_ad_library_query():
    url = apify_client.build_search_url("options trading", country="US", media_type="video")
    assert url.startswith("https://www.facebook.com/ads/library/?")
    assert "q=options+trading" in url
    assert "country=US" in url
    assert "media_type=video" in url


# ── scoring ─────────────────────────────────────────────────────────────────
def test_longevity_and_scale_scores_are_monotonic():
    ads = [
        {"days_running": 0, "variant_count": 1},
        {"days_running": 7, "variant_count": 4},
        {"days_running": 30, "variant_count": 12},
        {"days_running": 90, "variant_count": 30},
    ]
    AdsManagerAgent._score_mechanically(ads)
    longevity = [a["longevity_score"] for a in ads]
    scale = [a["scale_score"] for a in ads]
    assert longevity == sorted(longevity)
    assert scale == sorted(scale)
    assert longevity[0] == 0.0 and longevity[-1] == 100.0
    assert scale[0] == 0.0 and scale[-1] == 100.0
    # Diminishing returns: three weeks alive is most of the signal.
    assert longevity[2] > 70.0
    # A 90-day ad must not be worth six times a 30-day ad.
    assert longevity[3] < longevity[2] * 1.5


def test_winner_score_ignores_longevity_it_did_not_observe():
    """A keyword row has no start date. Scoring it as a zero-day ad would rank a
    genuine 145-day winner below spam that matched more keywords."""
    measured = {
        "longevity_known": True,
        "longevity_score": 0.0,
        "scale_score": 80.0,
        "relevance_score": 80.0,
    }
    unmeasured = dict(measured, longevity_known=False)
    assert AdsManagerAgent._winner_score(unmeasured) == 80.0  # reweighted, not punished
    assert AdsManagerAgent._winner_score(measured) == 44.0  # genuinely a one-day ad
    assert AdsManagerAgent._winner_score(unmeasured) > AdsManagerAgent._winner_score(measured)


def test_winner_score_still_rewards_a_long_runner():
    long_runner = {
        "longevity_known": True,
        "longevity_score": 100.0,
        "scale_score": 50.0,
        "relevance_score": 50.0,
    }
    assert AdsManagerAgent._winner_score(long_runner) == 72.5


# ── the real captured fixture ───────────────────────────────────────────────
def _fixture_ads():
    payload = json.loads((FIXTURE_DIR / "meta_ads_sample.json").read_text(encoding="utf-8"))
    return [apify_client.normalise(i) for i in payload["items"]]


def test_fixture_holds_both_meta_response_shapes():
    """Keyword rows report start == end == scrape date; page rows carry real
    lifetimes. The fixture must contain both so the scorer is exercised on each."""
    ads = _fixture_ads()
    known = [a for a in ads if a["longevity_known"]]
    unknown = [a for a in ads if not a["longevity_known"]]
    assert known and unknown, "fixture must contain both Meta response shapes"
    assert all(a["discovery_source"] == "page" for a in known)
    assert max(a["days_running"] for a in known) > 30


def test_normaliser_reads_the_live_camelcase_schema():
    """Meta returns ctaText / videoHdUrl / startDateFormatted, not snake_case."""
    ads = _fixture_ads()
    assert len(ads) >= 20
    assert all(a["ad_archive_id"] for a in ads), "every real row must yield an id"
    assert all(a["ad_copy"] for a in ads), "body text must survive normalisation"
    assert all(a["cta_text"] for a in ads), "ctaText must be found"
    assert all(a["video_urls"] or a["image_urls"] for a in ads), "media urls must be found"
    assert {a["media_type"] for a in ads} <= {"video", "image"}


# ── timeline repair ─────────────────────────────────────────────────────────
def _script_with(shots: list[tuple[float, float]]) -> AdScript:
    data = fallback_script("pain_led", 45.0, "9:16")
    data["shots"] = [
        {
            "n": i + 1,
            "t_start": a,
            "t_end": b,
            "beat": "hook",
            "visual": "x",
            "image_prompt": "x",
        }
        for i, (a, b) in enumerate(shots)
    ]
    return AdScript(**data)


def test_repair_closes_gaps_and_lands_on_the_target_runtime():
    script = _script_with([(0, 3), (5, 9), (12, 20)])  # gaps, wrong total
    ScriptAgent._repair_timeline(script, 45.0)
    assert script.shots[0].t_start == 0.0
    for a, b in zip(script.shots, script.shots[1:]):
        assert a.t_end == b.t_start, "shots must be contiguous"
    assert script.duration_seconds == pytest.approx(45.0, abs=0.2)


def test_repair_clamps_a_runaway_script_into_the_brief():
    script = _script_with([(0, 40), (40, 90), (90, 200)])
    ScriptAgent._repair_timeline(script, 300.0)  # asked for five minutes
    assert 30.0 <= script.duration_seconds <= 60.0


def test_shot_rejects_a_negative_duration():
    with pytest.raises(ValueError):
        Shot(n=1, t_start=5.0, t_end=5.0, beat="hook", visual="x", image_prompt="x")


# ── claims audit ────────────────────────────────────────────────────────────
def test_audit_drops_invented_claims_but_keeps_dataset_references():
    script = AdScript(**fallback_script("data_led", 45.0, "9:16"))
    script.claims_used = ["hit_rate", "data:SNOW", "profits_guaranteed_300_percent"]
    ScriptAgent._audit_claims(script)
    assert "hit_rate" in script.claims_used
    assert "data:SNOW" in script.claims_used
    assert "profits_guaranteed_300_percent" not in script.claims_used
    assert any("removed during audit" in n for n in script.compliance_notes)


def test_every_claim_in_the_reference_scripts_is_traceable():
    allowed = {c["id"] for c in brand()["product"]["verified_claims"]}
    for angle in ("pain_led", "data_led", "outcome_led"):
        script = AdScript(**fallback_script(angle, 45.0, "9:16"))
        for claim in script.claims_used:
            assert claim in allowed or claim.startswith("data:"), (angle, claim)


# ── the reference scripts themselves ────────────────────────────────────────
@pytest.mark.parametrize("angle", ["pain_led", "data_led", "outcome_led"])
def test_reference_script_is_a_shootable_film(angle):
    script = AdScript(**fallback_script(angle, 45.0, "9:16"))
    assert 30.0 <= script.total_shot_time <= 60.0
    assert len(script.shots) >= 6
    assert script.visual_hook.the_event and script.visual_hook.first_frame
    assert script.shots[0].t_start == 0.0
    for a, b in zip(script.shots, script.shots[1:]):
        assert a.t_end == b.t_start
    for shot in script.shots:
        assert len(shot.image_prompt) > 60, "every shot needs a standalone model prompt"
    assert script.shots[-1].beat == "cta"
    assert any("risk" in n.lower() for n in script.compliance_notes)


@pytest.mark.parametrize("angle", ["pain_led", "data_led", "outcome_led"])
def test_reference_script_avoids_banned_language(angle):
    script = AdScript(**fallback_script(angle, 45.0, "9:16"))
    text = json.dumps(script.model_dump(mode="json")).lower()
    for word in brand()["voice"]["forbidden_words"]:
        assert word.lower() not in text, "banned phrase reached the script: " + word


def test_the_hook_happens_inside_three_seconds():
    for angle in ("pain_led", "data_led", "outcome_led"):
        script = AdScript(**fallback_script(angle, 45.0, "9:16"))
        assert script.shots[0].beat == "hook"
        assert script.shots[0].t_end <= 4.0


# ── proprietary data ────────────────────────────────────────────────────────
def test_unique_data_derives_risk_reward_from_the_published_levels():
    rows = unique_data.dataset()
    assert rows, "data/unique/ must contain at least one prediction export"
    snow = next((r for r in rows if r["ticker"] == "SNOW"), None)
    assert snow is not None
    assert snow["confidence"] == 46.0
    assert snow["risk_reward"] == pytest.approx(1.44, abs=0.02)
    assert "Reddit" in snow["silent_channels"]


def test_cinematic_brief_picks_the_record_with_the_widest_channel_spread():
    brief = unique_data.cinematic_brief()
    assert brief["available"]
    weights = list(brief["hero"]["source_weights"].values())
    assert max(weights) - min(weights) == 60.0
    assert brief["talking_points"]


# ── render brief + animatic ─────────────────────────────────────────────────
def test_render_brief_covers_every_shot(tmp_path: Path):
    script = AdScript(**fallback_script("data_led", 45.0, "9:16"))
    brief = openmontage.build_brief(script, tmp_path / "ad.mp4")
    assert len(brief.timeline) == len(script.shots)
    visual_assets = [a for a in brief.assets if a.kind in ("image", "video")]
    assert len(visual_assets) == len(script.shots)
    assert brief.look["palette"]["signal"] == brand()["look"]["palette"]["signal"]
    assert "cinematic" in brief.engine


def test_animatic_is_self_contained(tmp_path: Path):
    scripts = [AdScript(**fallback_script(a, 45.0, "9:16")) for a in ("pain_led", "data_led")]
    bundle = StoryboardBundle(
        generated_at=datetime.now(timezone.utc), hero_script_id="data_led", scripts=scripts
    )
    out = previz.write_animatic(bundle, tmp_path / "storyboard.html")
    html = out.read_text(encoding="utf-8")
    assert "THE LOUD ROOM" in html and "WEIGHTED" in html
    assert "http://" not in html.replace("http://www.w3.org", "")  # no external fetches
    assert brand()["look"]["palette"]["signal"] in html


# ── the board ───────────────────────────────────────────────────────────────
def test_board_graph_is_a_chain_in_dependency_order():
    tasks = plan("run_test")
    assert [t["agent"] for t in tasks] == [
        "ads_manager",
        "insight_agent",
        "research_agent",
        "script_agent",
        "video_agent",
    ]
    seen: set[str] = set()
    for task in tasks:
        for dep in task["depends_on"]:
            assert dep in seen, "a task depends on one that has not been created yet"
        seen.add(task["agent"])
    assert "stage mine --run run_test" in tasks[0]["body"]


def test_pipeline_config_and_board_agree_on_the_agents():
    configured = [a["id"] for a in pipeline()["agents"]]
    assert configured == [t["agent"] for t in plan("run_test")]


# ── tolerant score parsing ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    "payload",
    [
        {"scores": [{"id": "a1", "relevance": 70, "rationale": "on brief"}]},
        {"ads": [{"id": "a1", "relevance_score": 70, "reason": "on brief"}]},
        {"results": [{"ad_archive_id": "a1", "score": 70, "why": "on brief"}]},
        [{"id": "a1", "rating": 70, "explanation": "on brief"}],
        {"a1": 70},
    ],
)
def test_score_parser_survives_model_renaming_the_schema(payload):
    """A weak model renames the wrapper and the fields. Discarding a good answer
    silently is worse than any of the shapes it might invent."""
    parsed = AdsManagerAgent._parse_scores(payload)
    assert "a1" in parsed
    assert parsed["a1"][0] == 70.0


def test_score_parser_clamps_and_rejects_junk():
    parsed = AdsManagerAgent._parse_scores(
        {"scores": [
            {"id": "hi", "relevance": 900},
            {"id": "lo", "relevance": -5},
            {"id": "", "relevance": 50},
            {"relevance": 50},
            "not a dict",
        ]}
    )
    assert parsed["hi"][0] == 100.0
    assert parsed["lo"][0] == 0.0
    assert len(parsed) == 2, "rows without an id must be dropped"


def test_score_parser_returns_empty_on_nonsense():
    assert AdsManagerAgent._parse_scores({"summary": "I could not comply"}) == {}
    assert AdsManagerAgent._parse_scores(None) == {}


# ── weak-model output coercion ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "given,expected",
    [
        ("low|medium|high", "low"),   # model echoed the schema hint verbatim
        ("Medium.", "medium"),
        ("very high", "high"),
        ("HIGH", "high"),
        ("banana", "medium"),          # unmappable falls back to the default
    ],
)
def test_intensity_is_coerced_rather_than_crashing(given, expected):
    from cwt_ads.schemas import PainCluster

    cluster = PainCluster(id="a", label="b", description="c", intensity=given)
    assert cluster.intensity == expected


def test_insight_report_accepts_a_teardown_that_echoed_the_hint():
    """This exact payload crashed a live run before the coercion existed."""
    from cwt_ads.schemas import InsightReport

    report = InsightReport(
        generated_at=datetime.now(timezone.utc),
        ads_analysed=1,
        teardowns=[
            {
                "ad_archive_id": "1",
                "advertiser": "x",
                "hook_device": "h",
                "core_pain": "p",
                "pain_intensity": "low|medium|high",
                "promise": "q",
                "proof_type": "none",
                "emotional_arc": "a->b",
                "why_it_works": "w",
                "transferable_to_crowdwisdom": "t",
            }
        ],
        pain_clusters=[{"id": "i", "label": "l", "description": "d", "intensity": "low|medium|high"}],
    )
    assert report.teardowns[0].pain_intensity in {"low", "medium", "high"}
    assert report.pain_clusters[0].intensity in {"low", "medium", "high"}


def test_keyword_heuristic_cannot_outscore_an_agent_judgement():
    """Topicality is not fit. A keyword-stuffed spam ad scoring 100 on the
    heuristic outranked a 145-day incumbent the agent had scored 25."""
    agent = AdsManagerAgent(Path("output"))
    stuffed = {"ad_copy": " ".join(AdsManagerAgent._LEXICON), "title": ""}
    assert agent._keyword_relevance(stuffed) == AdsManagerAgent.HEURISTIC_CEILING
    assert AdsManagerAgent.HEURISTIC_CEILING < 100.0
    # An empty ad still scores zero, so ordering within heuristic ads survives.
    assert agent._keyword_relevance({"ad_copy": "buy shoes", "title": ""}) == 0.0


# ── the echoed-schema guard ─────────────────────────────────────────────────
def test_echoed_schema_is_detected():
    """A model that returns the template instead of an answer parses AND
    validates, so only a content check catches it. This is the exact payload a
    live run produced."""
    from cwt_ads.agents.base import looks_like_echoed_schema
    from cwt_ads.agents.insight_agent import SCHEMA

    echoed = {
        "teardowns": [
            {
                "ad_archive_id": "string",
                "advertiser": "string",
                "hook_device": "the mechanism used in the first 3 seconds",
                "core_pain": "string",
                "promise": "string",
                "why_it_works": "string",
                "transferable_to_crowdwisdom": "the one idea worth stealing",
            }
        ],
        "whitespace": "the angle nobody in the niche is running, and why it is open",
        "icp_refinement": "a sharper ICP statement than we started with",
        "category_conventions": ["what nearly every ad in this niche does"],
    }
    assert looks_like_echoed_schema(echoed, SCHEMA)


def test_a_real_teardown_is_not_mistaken_for_an_echo():
    from cwt_ads.agents.base import looks_like_echoed_schema
    from cwt_ads.agents.insight_agent import SCHEMA

    real = {
        "teardowns": [
            {
                "ad_archive_id": "985960704059881",
                "advertiser": "The Motley Fool",
                "hook_device": "Authority claim stacked on a dated deadline",
                "core_pain": "Fear of missing the next Nvidia",
                "promise": "One ticker, picked before the crowd",
                "why_it_works": "It has run 145 days, which in this niche means it converts",
                "transferable_to_crowdwisdom": "Specificity of a single named call",
            }
        ],
        "whitespace": "Nobody dramatises the noise itself; every ad sells the answer",
        "icp_refinement": "Self-directed trader, 28-45, over-subscribed and under-decided",
        "category_conventions": ["Screen recording of a rising chart", "Presenter to camera"],
    }
    assert not looks_like_echoed_schema(real, SCHEMA)


def test_empty_response_counts_as_an_echo():
    from cwt_ads.agents.base import looks_like_echoed_schema

    assert looks_like_echoed_schema({}, '{"a": "b"}')
    assert looks_like_echoed_schema({"x": "   "}, '{"a": "b"}')


def test_a_timeout_is_not_retried_three_times(monkeypatch):
    """`budget` originally gated only the backoff sleep, not the loop, so a
    timeout still burned all three attempts - tripling the wait before the
    fallback that was always going to run."""
    from cwt_ads import llm

    calls = {"n": 0}

    def always_stall(*_args, **_kwargs):
        calls["n"] += 1
        raise llm.LLMTimeout("stalled")

    monkeypatch.setattr(llm, "_post_with_deadline", always_stall)
    monkeypatch.setattr(llm, "_provider", lambda: ("openrouter", "http://x", "k"))
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    with pytest.raises(llm.LLMError):
        llm.chat("sys", "user", retries=3)
    assert calls["n"] == 1, "a timeout must cost one attempt, not three"


def test_an_ordinary_error_still_gets_its_retries(monkeypatch):
    from cwt_ads import llm

    calls = {"n": 0}

    def flaky(*_args, **_kwargs):
        calls["n"] += 1
        raise llm.LLMError("503")

    monkeypatch.setattr(llm, "_post_with_deadline", flaky)
    monkeypatch.setattr(llm, "_provider", lambda: ("openrouter", "http://x", "k"))
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    with pytest.raises(llm.LLMError):
        llm.chat("sys", "user", retries=3)
    assert calls["n"] == 3


def test_a_credit_refusal_is_never_retried(monkeypatch):
    from cwt_ads import llm

    calls = {"n": 0}

    class Resp:
        status_code = 402
        text = "insufficient credits"

    def refuse(*_args, **_kwargs):
        calls["n"] += 1
        return Resp()

    monkeypatch.setattr(llm, "_post_with_deadline", refuse)
    monkeypatch.setattr(llm, "_provider", lambda: ("openrouter", "http://x", "k"))
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    with pytest.raises(llm.LLMCredit):
        llm.chat("sys", "user", retries=3)
    assert calls["n"] == 1


def test_log_lines_do_not_eat_bracketed_run_ids(capsys):
    """Rich reads [..] as a style tag, so a task titled '[run_x] Ads Manager'
    printed as ' Ads Manager' - the run id vanished from every log line."""
    from cwt_ads.logging_utils import step

    step("pipeline", "hermes kanban create [run_20260908_151614] Ads Manager - mine")
    out = capsys.readouterr().out
    assert "run_20260908_151614" in out


# ── the mp4 animatic ────────────────────────────────────────────────────────
def test_animatic_video_renders_a_real_mp4(tmp_path: Path):
    """Needs ffmpeg; skipped where it is absent."""
    from cwt_ads.render import animatic_video, openmontage as om

    if not om.ffmpeg_available():
        pytest.skip("ffmpeg not installed")

    script = AdScript(**fallback_script("data_led", 45.0, "9:16"))
    out = tmp_path / "ad.mp4"
    result = animatic_video.render(script, out, fps=12)  # low fps keeps the test quick
    assert result["rendered"], result
    assert out.exists() and out.stat().st_size > 50_000
    assert result["shots"] == len(script.shots)


def test_animatic_video_reports_cleanly_with_no_shots(tmp_path: Path):
    from cwt_ads.render import animatic_video

    empty = AdScript(**{**fallback_script("data_led", 45.0, "9:16"), "shots": []})
    result = animatic_video.render(empty, tmp_path / "x.mp4")
    assert not result["rendered"] and "reason" in result
