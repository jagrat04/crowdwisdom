"""Typed contracts for every artifact the team writes to disk.

Each agent validates its own output against these models before saving, so a
malformed LLM response fails at the boundary that produced it rather than three
agents downstream.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class _Base(BaseModel):
    model_config = {"populate_by_name": True, "extra": "allow"}


def coerce_choice(allowed: tuple[str, ...], default: str):
    """Build a before-validator that forces a value into an allowed set.

    Weaker models routinely echo the schema hint back verbatim - a field
    documented as "low|medium|high" comes back containing the literal string
    "low|medium|high" - or answer "Medium." with a capital and a full stop.
    None of that is worth crashing a pipeline over three stages from the end,
    so normalise what can be normalised and fall back to a stated default.
    """

    def _coerce(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = value.strip().strip(".").lower()
        if cleaned in allowed:
            return cleaned
        # "low|medium|high" (echoed hint) or "very high" - take the first match.
        for option in allowed:
            if option in cleaned.split("|")[0] or cleaned.split("|")[0] in option:
                return option
        for option in allowed:
            if option in cleaned:
                return option
        return default

    return _coerce


# ── 01 · winning ads ────────────────────────────────────────────────────────
class WinningAd(_Base):
    ad_archive_id: str
    page_name: str = "unknown"
    page_id: str | None = None
    ad_copy: str = ""
    title: str | None = None
    cta_text: str | None = None
    link_url: str | None = None
    media_type: str = "unknown"
    video_urls: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    publisher_platforms: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    days_running: int = 0
    longevity_known: bool = False
    variant_count: int = 1
    is_active: bool = True
    impressions_text: str | None = None
    matched_query: str = ""
    discovery_source: str = "unknown"
    ad_library_url: str | None = None

    # Scoring, filled by the Ads Manager Agent.
    longevity_score: float = 0.0
    scale_score: float = 0.0
    relevance_score: float = 0.0
    winner_score: float = 0.0
    score_rationale: str = ""


class WinningAdsReport(_Base):
    generated_at: datetime
    source: str = "apify:facebook-ads-scraper"
    window_days: int = 30
    window_start: date
    window_end: date
    queries: list[str] = Field(default_factory=list)
    total_scraped: int = 0
    total_in_window: int = 0
    ads: list[WinningAd] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ── 02 · marketing insight ──────────────────────────────────────────────────
class AdTeardown(_Base):
    ad_archive_id: str
    advertiser: str
    hook_device: str = Field(description="The mechanical trick used in the first 3s")
    hook_transcript: str = ""
    core_pain: str
    pain_intensity: Literal["low", "medium", "high"] = "medium"
    _fix_intensity = field_validator("pain_intensity", mode="before")(
        coerce_choice(("low", "medium", "high"), "medium")
    )
    promise: str
    proof_type: str = Field(description="track record | testimonial | authority | demo | none")
    emotional_arc: str
    icp_signals: list[str] = Field(default_factory=list)
    why_it_works: str
    transferable_to_crowdwisdom: str
    do_not_copy: str = ""


class PainCluster(_Base):
    id: str
    label: str
    description: str
    frequency: int = 0
    intensity: Literal["low", "medium", "high"] = "medium"
    _fix_intensity = field_validator("intensity", mode="before")(
        coerce_choice(("low", "medium", "high"), "medium")
    )
    example_phrases: list[str] = Field(default_factory=list)
    crowdwisdom_answer: str = ""


class InsightReport(_Base):
    generated_at: datetime
    ads_analysed: int
    teardowns: list[AdTeardown] = Field(default_factory=list)
    pain_clusters: list[PainCluster] = Field(default_factory=list)
    hook_devices_ranked: list[str] = Field(default_factory=list)
    icp_refinement: str = ""
    category_conventions: list[str] = Field(
        default_factory=list, description="What every ad in this niche does — i.e. what to break"
    )
    whitespace: str = Field("", description="The angle nobody in the niche is running")
    search_queries_for_research: list[str] = Field(default_factory=list)


# ── 03 · research ───────────────────────────────────────────────────────────
class ResearchFinding(_Base):
    query: str
    provider: Literal["tavily", "exa", "fixture"] = "fixture"
    _fix_provider = field_validator("provider", mode="before")(
        coerce_choice(("tavily", "exa", "fixture"), "fixture")
    )
    title: str
    url: str
    published_date: str | None = None
    snippet: str = ""
    relevance: float = 0.0


class ResearchReport(_Base):
    generated_at: datetime
    window_days: int
    window_start: date
    providers_used: list[str] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    synthesis: str = ""
    evidenced_pains: list[str] = Field(default_factory=list)
    quotable_lines: list[str] = Field(default_factory=list)
    icp_language: list[str] = Field(
        default_factory=list, description="Verbatim phrases real traders used in the last month"
    )


# ── 04 · scripts + storyboards ──────────────────────────────────────────────
class Shot(_Base):
    n: int
    t_start: float
    t_end: float
    beat: str = Field(description="hook | escalation | turn | proof | resolution | cta")
    shot_size: str = ""
    camera: str = ""
    visual: str = Field(description="Human-readable description of what is on screen")
    image_prompt: str = Field("", description="Prompt for the image/video model, style baked in")
    motion_prompt: str = Field("", description="How the frame should move")
    on_screen_text: str = ""
    voiceover: str = ""
    sfx: str = ""
    music: str = ""
    transition_out: str = "cut"

    @field_validator("t_end")
    @classmethod
    def _end_after_start(cls, v: float, info: Any) -> float:
        start = info.data.get("t_start", 0.0)
        if v <= start:
            raise ValueError(f"shot ends at {v}s but starts at {start}s")
        return v

    @property
    def duration(self) -> float:
        return round(self.t_end - self.t_start, 2)


class VisualHook(_Base):
    concept: str = Field(description="The stop-scroll idea in one sentence")
    first_frame: str = Field(description="What is on screen at t=0, before anything moves")
    the_event: str = Field(description="The physical change that happens inside 3 seconds")
    why_it_stops_the_scroll: str
    sound_at_zero: str = ""
    text_overlay: str = ""


class AdScript(_Base):
    id: str
    angle: str
    angle_source: Literal["research", "unique_data", "product"] = "product"
    _fix_source = field_validator("angle_source", mode="before")(
        coerce_choice(("research", "unique_data", "product"), "product")
    )
    title: str
    logline: str
    duration_seconds: float
    aspect_ratio: str = "9:16"
    target_pain: str
    icp: str
    visual_hook: VisualHook
    shots: list[Shot] = Field(default_factory=list)
    voiceover_full: str = ""
    on_screen_text_full: list[str] = Field(default_factory=list)
    cta: str = ""
    end_card: str = ""
    music_direction: str = ""
    sound_design_direction: str = ""
    claims_used: list[str] = Field(default_factory=list, description="ids from brand.verified_claims")
    compliance_notes: list[str] = Field(default_factory=list)
    why_this_works: str = ""

    @property
    def total_shot_time(self) -> float:
        return round(max((s.t_end for s in self.shots), default=0.0), 2)


class StoryboardBundle(_Base):
    generated_at: datetime
    brand: str = "CrowdWisdom Trading"
    hero_script_id: str = ""
    scripts: list[AdScript] = Field(default_factory=list)
    director_notes: str = ""


# ── 06 · render brief ───────────────────────────────────────────────────────
class RenderAsset(_Base):
    shot: int
    kind: Literal["image", "video", "voiceover", "music", "sfx"] = "image"
    _fix_kind = field_validator("kind", mode="before")(
        coerce_choice(("image", "video", "voiceover", "music", "sfx"), "image")
    )
    prompt: str = ""
    duration: float = 0.0
    provider_hint: str = ""


class RenderBrief(_Base):
    generated_at: datetime
    script_id: str
    title: str
    duration_seconds: float
    aspect_ratio: str
    fps: int = 30
    engine: str = "openmontage"
    look: dict[str, Any] = Field(default_factory=dict)
    timeline: list[Shot] = Field(default_factory=list)
    assets: list[RenderAsset] = Field(default_factory=list)
    narration_script: str = ""
    output_path: str = ""
    instructions: str = ""
