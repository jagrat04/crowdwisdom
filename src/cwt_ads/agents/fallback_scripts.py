"""Reference storyboards.

These are the scripts the Creative Director falls back to when the LLM is
unavailable (offline mode, no API key, a failed generation). They are not
placeholders - they are hand-directed reference films written to the same
brief, and they double as few-shot quality bar for what the live agent should
be producing.

Every shot carries a self-contained image_prompt with the look block baked in,
so each frame can be handed to an image or video model on its own.
"""

from __future__ import annotations

from typing import Any

LOOK = (
    "shot on 35mm anamorphic, shallow depth of field, deep crushed blacks, "
    "teal and amber grade, heavy volumetric haze, practical light sources only, "
    "35mm film grain, subtle chromatic aberration at frame edges, cinematic, "
    "2.39:1 feel in a 9:16 frame, no text artifacts, no watermark"
)

INK = "#05070D"
SIGNAL = "#00E5A0"


def _shot(
    n: int,
    t0: float,
    t1: float,
    beat: str,
    size: str,
    camera: str,
    visual: str,
    prompt: str,
    motion: str,
    text: str = "",
    vo: str = "",
    sfx: str = "",
    music: str = "",
    out: str = "cut",
) -> dict[str, Any]:
    return {
        "n": n,
        "t_start": t0,
        "t_end": t1,
        "beat": beat,
        "shot_size": size,
        "camera": camera,
        "visual": visual,
        "image_prompt": prompt + ", " + LOOK,
        "motion_prompt": motion,
        "on_screen_text": text,
        "voiceover": vo,
        "sfx": sfx,
        "music": music,
        "transition_out": out,
    }


# ── 1 · pain-led ────────────────────────────────────────────────────────────
def _pain_led() -> dict[str, Any]:
    return {
        "id": "pain_led",
        "angle": "Pain / ICP led",
        "angle_source": "research",
        "title": "THE LOUD ROOM",
        "logline": (
            "A trader wakes at 6am into a room that fills with every opinion he follows, "
            "until the noise collapses into the single line he actually needed."
        ),
        "target_pain": "Information obesity - forty inputs, zero conviction.",
        "icp": "Self-directed active trader, 28-45, over-subscribed and under-decided.",
        "visual_hook": {
            "concept": "A blank phone screen detonates into forty contradictory alerts in one frame.",
            "first_frame": (
                "Extreme close-up of a phone face-up on a dark duvet at 06:04. The screen is "
                "pure, empty white - wrong for the hour, and too quiet."
            ),
            "the_event": (
                "On frame 30 the white is buried, in a single cut, under a stack of forty "
                "notification cards that keep growing past the top of the frame. Half say BUY. "
                "Half say SELL. The stack does not stop."
            ),
            "why_it_stops_the_scroll": (
                "The eye is already trained to dismiss a notification stack; it is not trained "
                "for one that keeps growing. The unresolved motion - it has not finished - is "
                "what holds the thumb. No words are required to feel it."
            ),
            "sound_at_zero": "Room tone. One notification chime. Then thirty-nine in half a second.",
            "text_overlay": "",
        },
        "shots": [
            _shot(
                1, 0.0, 3.0, "hook", "ECU",
                "Macro lens, locked off, top-down on the phone",
                "A phone face-up on a dark duvet at 06:04. Blank white screen. Then it fills, in "
                "one frame, with a growing stack of contradictory alerts.",
                "extreme close-up macro of a smartphone lying face up on dark rumpled bedding at "
                "dawn, screen glowing pure white, cold blue ambient light from a window, dust in "
                "the air",
                "Locked off. At 1.0s the screen content changes in a single frame; the card stack "
                "then scrolls upward continuously and never resolves.",
                text="06:04",
                sfx="One chime. Then thirty-nine chimes inside half a second, layered into a wall.",
                music="None yet.",
                out="hard cut",
            ),
            _shot(
                2, 3.0, 7.0, "escalation", "WS",
                "24mm, low and wide, slow dolly in",
                "The trader sits on the edge of the bed, lit only by the phone. Behind and around "
                "him, out of focus, dozens of translucent screens hover in the dark - each one a "
                "mouth mid-sentence, no eyes.",
                "wide low-angle shot of a man sitting on the edge of a bed in a dark bedroom, face "
                "underlit by a phone, dozens of translucent floating screens suspended in the air "
                "around him receding into haze, each showing a talking mouth, teal and amber",
                "Slow 30cm dolly in. The floating screens drift at different speeds, none in sync.",
                vo="Everyone you follow is certain.",
                sfx="Forty overlapping voices, none intelligible. A rising tinnitus tone underneath.",
                music="Low drone entering at 3.5s.",
            ),
            _shot(
                3, 7.0, 11.0, "escalation", "montage",
                "Handheld, 50mm, hard 3-frame cuts",
                "Rapid montage: mouths, a red candle, a green candle, a countdown, a thumb hovering "
                "over a BUY button, a chart drawn three contradictory ways.",
                "rapid montage frames: extreme close-up of a mouth mid-word, a red candlestick "
                "chart on a cracked monitor, a countdown timer, a thumb hovering over a glowing buy "
                "button, three contradictory trend lines drawn over the same chart",
                "Cuts every 3 frames, accelerating to every 2. Slight handheld drift on every frame.",
                sfx="The voice wall compresses and pitches up.",
                music="Drone rising in pitch, no rhythm - deliberately unresolved.",
                out="whip",
            ),
            _shot(
                4, 11.0, 14.5, "escalation", "CU",
                "85mm, locked, shallow",
                "He taps. The chart runs the other way. His face does not react - which is worse.",
                "close-up of a mans face lit only by a screen, pupils reflecting a falling chart, "
                "absolutely no expression, cold blue key light, warm amber rim from a lamp behind",
                "Locked off. The reflection in his eyes falls. He blinks once, slowly.",
                vo="Half of them have to be wrong. Nobody tells you which half.",
                sfx="The voices continue. A single low heartbeat under them.",
            ),
            _shot(
                5, 14.5, 17.0, "turn", "WS",
                "24mm, locked, absolutely still",
                "Everything stops. Every floating screen freezes mid-word. Total silence. The most "
                "expensive beat in the film.",
                "wide shot of a man sitting still in a dark room surrounded by dozens of frozen "
                "translucent floating screens, all motion arrested, volumetric haze, a single shaft "
                "of light from a window",
                "Absolute freeze. Nothing moves except haze drifting through the light shaft.",
                sfx="Silence. A full beat of it.",
                music="Out.",
                out="hard cut",
            ),
            _shot(
                6, 17.0, 22.0, "turn", "WS",
                "24mm, slow push",
                "The screens begin to slide toward each other, overlapping, collapsing inward - "
                "forty rectangles compressing into one clean panel of signal-green text.",
                "dozens of translucent floating screens converging and overlapping into a single "
                "glowing panel in a dark room, green light emerging from the collision, long "
                "exposure light trails, volumetric haze",
                "The screens converge over 3.5s with easing, then snap into register in 4 frames.",
                vo="CrowdWisdom listens to sixteen thousand of them.",
                sfx="A single deep sub-bass hit on the snap.",
                music="One clean pulse enters at 90bpm.",
            ),
            _shot(
                7, 22.0, 29.0, "proof", "insert",
                "100mm macro, slow push, locked horizon",
                "The single card. Monospace, tabular figures, on ink black: direction, entry, "
                "target one, target two, stop. Nothing else on screen.",
                "extreme close-up of a single dark glass panel with precise monospace text and "
                "hairline green rules, tabular numbers, shallow focus falling off at the edges, "
                "one warm practical light raking across the glass",
                "Slow 15cm push in. Each line resolves into focus in sequence, top to bottom.",
                text="DIRECTION - ENTRY - TARGET 1 - TARGET 2 - STOP",
                vo="And gives you the one thing they agree on. With a level to enter, and a level to leave.",
                sfx="Four soft mechanical clicks as each line lands.",
                music="Pulse continues, a low string enters.",
            ),
            _shot(
                8, 29.0, 35.0, "proof", "MS",
                "50mm, locked, symmetrical",
                "A measured bar draws itself across frame to 74.1%. Beneath it, in small mono, the "
                "definition of a win. Restraint, not celebration.",
                "a single precise horizontal bar of green light drawing across a black glass "
                "surface, small monospace annotation beneath it, brass hairline ruler marks, "
                "laboratory precision, no glow bloom",
                "The bar draws left to right over 1.5s with a slight ease-out, then holds.",
                text="74.1% of tracked directions hit\nwin = target 1/2 reached, or a 2% move in the forecast direction",
                vo="Published. Auditable. For over a year.",
                sfx="A single tone at the end of the draw.",
                music="String swells slightly.",
            ),
            _shot(
                9, 35.0, 41.0, "resolution", "WS",
                "35mm, steady, tracking behind",
                "He stands, pockets the phone, and walks out of the bedroom into flat morning "
                "daylight. The floating screens are simply gone. He is not triumphant. He is calm.",
                "a man walking away from camera out of a dark bedroom into a bright doorway, warm "
                "morning daylight flooding through, dust motes, empty room behind him, no screens",
                "Tracking behind at walking pace. Exposure rides up as he crosses into the light.",
                vo="Same market. Same morning. One decision instead of forty.",
                sfx="A door. Birds. Ordinary life.",
                music="The pulse drops to a single sustained note.",
                out="dissolve",
            ),
            _shot(
                10, 41.0, 45.0, "cta", "MS",
                "Locked, centred",
                "End card on ink black. Wordmark. A signal-green underline draws in over 12 frames. "
                "URL in mono beneath. Legal line, small, honest.",
                "minimal end card on near-black background, clean grotesque wordmark centred, a "
                "thin green horizontal rule beneath it, small monospace url, generous negative "
                "space, no gradient",
                "Underline draws left to right over 12 frames, then a 2-second hold.",
                text="CROWDWISDOM TRADING\ncrowdwisdomtrading.com\nNot financial advice. Capital at risk.",
                vo="CrowdWisdom Trading.",
                sfx="One soft close.",
                music="Resolves to silence.",
            ),
        ],
        "voiceover_full": (
            "Everyone you follow is certain. Half of them have to be wrong - and nobody tells you "
            "which half. CrowdWisdom listens to sixteen thousand of them, and gives you the one "
            "thing they agree on: with a level to enter, and a level to leave. Published. "
            "Auditable. For over a year. Same market, same morning - one decision instead of "
            "forty. CrowdWisdom Trading."
        ),
        "on_screen_text_full": [
            "06:04",
            "DIRECTION - ENTRY - TARGET 1 - TARGET 2 - STOP",
            "74.1% of tracked directions hit",
            "win = target 1/2 reached, or a 2% move in the forecast direction",
            "CROWDWISDOM TRADING / crowdwisdomtrading.com",
            "Not financial advice. Capital at risk.",
        ],
        "cta": "Read this week's consensus free at crowdwisdomtrading.com",
        "end_card": "Wordmark on ink, green underline drawing in, url in mono, legal line beneath.",
        "music_direction": (
            "No music for the first 3.5s. An unresolved drone through the chaos, rising in pitch "
            "and never landing. Everything out at the freeze. A single sub-bass hit on the "
            "collapse, then a clean 90bpm pulse and one low string to the end."
        ),
        "sound_design_direction": (
            "The whole film is carried by density. Forty voices become one voice; forty chimes "
            "become one click. The silence at 14.5s is the product demo."
        ),
        "claims_used": ["traders_tracked", "hit_rate", "track_record"],
        "compliance_notes": [
            "The 74.1% claim appears with its definition on the same card.",
            "No profit, income or guarantee is stated or implied.",
            "End card carries not-financial-advice and capital-at-risk.",
        ],
        "why_this_works": (
            "Every competitor ad in this niche sells the answer. None of them make you feel the "
            "question. This film spends fifteen seconds inside the pain before the product is "
            "even named, which buys the right to be believed at the turn. The hook is pure "
            "motion, so it survives a muted autoplay. And the resolution is deliberately "
            "unglamorous - a man walking into a normal morning - because the promise is calm, "
            "not wealth, and calm is the one thing this category never sells."
        ),
    }


# ── 2 · data-led ────────────────────────────────────────────────────────────
def _data_led(brief: dict[str, Any]) -> dict[str, Any]:
    hero = brief.get("hero") or {}
    ticker = str(hero.get("ticker", "SNOW"))
    conf = int(hero.get("confidence") or 46)
    weights = hero.get("source_weights_labelled") or {
        "YouTube": 10,
        "X / Twitter": 30,
        "Reddit": 0,
        "News + LLM synthesis": 60,
    }
    entry = hero.get("price")
    t1 = hero.get("target_1")
    t2 = hero.get("target_2")
    stop = hero.get("stop_1")
    rr = hero.get("risk_reward")
    silent = (hero.get("silent_channels") or ["Reddit"])[0]
    weights_line = "  ".join(str(k).upper() + " " + str(int(v)) for k, v in weights.items())
    levels_line = "ENTRY {e}   T1 {a}   T2 {b}   STOP {s}".format(
        e=entry, a=t1, b=t2, s=stop
    )

    return {
        "id": "data_led",
        "angle": "Unique data led",
        "angle_source": "unique_data",
        "title": "WEIGHTED",
        "logline": (
            "Four channels of market chatter are physically weighed in a laboratory until they "
            "collapse into one honest number - including the channel that had nothing to say."
        ),
        "target_pain": "Paying for confident signals that never show their working.",
        "icp": "The signal-fatigued subscriber who cannot audit what they already pay for.",
        "visual_hook": {
            "concept": "Four columns of light are weighed against each other - and one of them is empty.",
            "first_frame": (
                "Pure black. Four vertical columns of pale light stand in a row, exactly equal "
                "height, humming at the same pitch. Perfect, suspicious symmetry."
            ),
            "the_event": (
                "At 1.2s the symmetry breaks violently: one column collapses to nothing, another "
                "surges to double height. The hum becomes a chord. Something has just been measured."
            ),
            "why_it_stops_the_scroll": (
                "Perfect symmetry reads as a still image, so the thumb relaxes for a beat - and "
                "then it breaks. The break is a measurement, not a transition, which makes the "
                "viewer want the result. It is a bar chart with the soul of a guillotine."
            ),
            "sound_at_zero": "Four sine tones at the same pitch. One cuts out dead.",
            "text_overlay": "",
        },
        "shots": [
            _shot(
                1, 0.0, 3.5, "hook", "MS",
                "50mm, locked, dead centre",
                "Four equal columns of light in a void. At 1.2s one collapses to nothing and "
                "another doubles.",
                "four vertical columns of pale volumetric light standing in a row in absolute "
                "darkness, perfectly equal height, faint haze, laboratory cleanliness, no floor "
                "visible",
                "Locked off. At 1.2s column three drops to zero over 6 frames; column four rises "
                "to double height over the same 6 frames. Everything else holds.",
                sfx="Four sine tones in unison. One cuts dead; one drops an octave.",
                music="None.",
                out="hard cut",
            ),
            _shot(
                2, 3.5, 8.0, "escalation", "WS",
                "35mm, slow pull back",
                "The columns are inside a glass cylinder on a brass laboratory table. Amber "
                "practical lamp. This is a measuring instrument, not a chart.",
                "a tall glass cylinder on a brass laboratory bench containing four columns of "
                "coloured light of unequal height, single warm practical lamp raking from the left, "
                "dark laboratory interior, volumetric haze, scientific instruments out of focus "
                "behind",
                "Slow pull back revealing the apparatus over 4.5s, ending on a symmetrical frame.",
                vo="Every call we publish shows you what it listened to.",
                sfx="Room tone, a faint electrical hum, a distant tick.",
                music="Single sustained low string enters at 4s.",
            ),
            _shot(
                3, 8.0, 13.0, "escalation", "ECU",
                "100mm macro, lateral track",
                "Engraved brass labels beneath each column, tracked left to right.",
                "extreme macro of engraved brass nameplates beneath columns of light, letterpress "
                "depth in the metal, shallow focus, warm rake light picking out the engraving",
                "Lateral track left to right at constant speed; each label passes through the focal "
                "plane in turn.",
                text=weights_line,
                vo="Where the signal came from, and how much of it there was.",
                sfx="Four soft mechanical clicks as each label passes.",
                music="String holds.",
            ),
            _shot(
                4, 13.0, 18.0, "turn", "MS",
                "50mm, locked",
                "Hold on the empty column. The gap where " + silent + " should be. Nothing fills it.",
                "a conspicuous empty gap between columns of light where a fourth column should "
                "stand, the void deliberately lit, faint dust drifting through the empty space, "
                "brass nameplate beneath reading zero",
                "Absolutely locked. Only dust moves. Hold uncomfortably long.",
                text=silent.upper() + ": 0\nA channel with nothing to say is published as zero.\nNot padded.",
                vo="Including the ones that had nothing to say.",
                sfx="The hum of three tones. The fourth is a hole in the sound.",
                music="String thins to a single note.",
            ),
            _shot(
                5, 18.0, 24.0, "turn", "MS",
                "50mm, slow push",
                "The columns pour downward into a single vessel as liquid light, mixing, settling "
                "at a marked line.",
                "columns of coloured light pouring down into a single glass vessel like liquid, "
                "the liquid settling and finding a level against etched graduation marks, green "
                "and amber mixing, long exposure trails",
                "Pour over 3s with real fluid weight, then a 2s settle with a visible wobble before "
                "it finds the line.",
                sfx="A pour. A glass ring. Then stillness.",
                music="Sub-bass hit as the liquid lands.",
            ),
            _shot(
                6, 24.0, 30.0, "proof", "ECU",
                "100mm macro, locked",
                "The graduation mark the liquid settled on: a confidence dial reading "
                + str(conf)
                + " out of 100. Not rounded up.",
                "extreme close-up of an etched graduation scale on laboratory glass with a "
                "precisely machined brass needle resting against a numbered mark, condensation on "
                "the glass, single warm rake light",
                "Locked. The needle settles with two tiny corrections, then stops.",
                text="CONFIDENCE " + str(conf) + "/100",
                vo="Most services tell you they are sure. This one tells you how sure.",
                sfx="Two faint needle ticks.",
                music="Clean pulse enters at 90bpm.",
            ),
            _shot(
                7, 30.0, 37.0, "proof", "insert",
                "85mm, slow push, locked horizon",
                "The levels etch themselves into the glass, one line at a time. Monospace, tabular. "
                + ticker
                + ".",
                "precise monospace text being etched into dark laboratory glass line by line, "
                "hairline green rules, tabular figures, a brass straightedge resting alongside, "
                "shallow focus falling away at the frame edges",
                "Each line etches in over 8 frames, in order, with a 6-frame pause between.",
                text=ticker + "\n" + levels_line + ("\nR:R " + str(rr) + ":1" if rr else ""),
                vo="An entry. Two targets. A stop. Written down before the trade, not after.",
                sfx="Four etching strokes, one per line.",
                music="Pulse plus a low string.",
            ),
            _shot(
                8, 37.0, 42.0, "resolution", "WS",
                "35mm, crane up",
                "Pull back: this vessel is one of thousands on a rack that runs into the dark, each "
                "one dated, each one still standing. A public record.",
                "a vast dark archive of identical glass vessels on brass racks receding into "
                "darkness, each faintly lit from within, dated brass plates, cathedral scale, "
                "volumetric shafts of light from above",
                "Crane up and back, revealing scale over 5s. The rack never ends.",
                text="16,564 traders listened to\n74.1% of tracked directions hit\nwin = target 1/2 reached, or a 2% move in the forecast direction",
                vo="Sixteen thousand traders, weighed every week, on the record.",
                sfx="Room tone of a very large space.",
                music="Strings open up.",
                out="dissolve",
            ),
            _shot(
                9, 42.0, 45.0, "cta", "MS",
                "Locked, centred",
                "End card on ink. Wordmark, green underline drawing in, url in mono, legal line.",
                "minimal end card on near-black, clean grotesque wordmark centred, thin green "
                "horizontal rule drawing beneath it, small monospace url, generous negative space",
                "Underline draws over 12 frames, then holds.",
                text="CROWDWISDOM TRADING\ncrowdwisdomtrading.com\nNot financial advice. Capital at risk.",
                vo="CrowdWisdom Trading.",
                sfx="One soft close.",
                music="Resolves.",
            ),
        ],
        "voiceover_full": (
            "Every call we publish shows you what it listened to - where the signal came from, and "
            "how much of it there was. Including the ones that had nothing to say. Most services "
            "tell you they are sure. This one tells you how sure. An entry. Two targets. A stop. "
            "Written down before the trade, not after. Sixteen thousand traders, weighed every "
            "week, on the record. CrowdWisdom Trading."
        ),
        "on_screen_text_full": [
            weights_line,
            silent.upper() + ": 0 - a channel with nothing to say is published as zero, not padded.",
            "CONFIDENCE " + str(conf) + "/100",
            ticker + " - " + levels_line,
            "16,564 traders listened to",
            "74.1% of tracked directions hit",
            "CROWDWISDOM TRADING / crowdwisdomtrading.com",
        ],
        "cta": "See the full prediction record at crowdwisdomtrading.com",
        "end_card": "Wordmark on ink, green underline drawing in, url in mono, legal line beneath.",
        "music_direction": (
            "Sine tones only until 4s. A single low string from 4s. Sub-bass hit when the liquid "
            "lands at 21s. Clean 90bpm pulse from 24s. Strings open at 37s and resolve on the card."
        ),
        "sound_design_direction": (
            "The instrument is the sound designer: tones, clicks, a pour, a needle, an etching "
            "stroke. Nothing synthetic, nothing triumphant. The missing fourth tone at 13s is a "
            "hole in the mix, and the audience should notice."
        ),
        "claims_used": ["traders_tracked", "hit_rate", "data:" + ticker],
        "compliance_notes": [
            "All ticker-level numbers are read directly from the CrowdWisdom prediction export in "
            "data/unique/ and are shown as a past published call, not a forecast to the viewer.",
            "The 74.1% claim appears with its definition on the same card.",
            "No profit or guarantee is stated or implied.",
            "End card carries not-financial-advice and capital-at-risk.",
        ],
        "why_this_works": (
            "The category sells confidence. This film sells calibration - and calibration is only "
            "credible if you are willing to show a low number. Leading with a confidence of "
            + str(conf)
            + " out of 100 and an empty channel is a costly signal: nobody fakes a weakness. "
            "Making the dataset physical - glass, brass, liquid, an archive that runs into the "
            "dark - turns an audit trail into a cathedral, which is the exact feeling a public "
            "track record is supposed to produce and never does in a screenshot."
        ),
    }


# ── 3 · outcome-led ─────────────────────────────────────────────────────────
def _outcome_led() -> dict[str, Any]:
    return {
        "id": "outcome_led",
        "angle": "How CrowdWisdom changes the result",
        "angle_source": "product",
        "title": "TWO MONDAYS",
        "logline": (
            "The same trader lives the same week twice in a perfectly mirrored frame. The only "
            "variable is whether he had the consensus."
        ),
        "target_pain": "Acting without a plan, then paying for it on Friday.",
        "icp": "Active trader who does the work and still cannot tell if the work is helping.",
        "visual_hook": {
            "concept": "A perfectly mirrored frame - the same man twice - and only one half blinks.",
            "first_frame": (
                "A flawlessly symmetrical frame: the same man, twice, at the same desk, mirrored "
                "down the centre line. Identical to the pixel. Both completely still."
            ),
            "the_event": (
                "At 1.4s the left man blinks and shifts. The right man does not. The symmetry is "
                "broken by a human being, not by a cut."
            ),
            "why_it_stops_the_scroll": (
                "Faces are processed before anything else, and a mirrored face is processed as an "
                "error. The viewer holds on the frame trying to find the difference - which is "
                "exactly the question the ad is about to answer."
            ),
            "sound_at_zero": "A single room tone, doubled and slightly phased. Uncanny.",
            "text_overlay": "MONDAY",
        },
        "shots": [
            _shot(
                1, 0.0, 3.5, "hook", "MS",
                "50mm, locked, perfect symmetry, split down the centre",
                "The same man, twice, mirrored. Both still. At 1.4s only the left one moves.",
                "perfectly symmetrical mirrored composition of the same man sitting at the same "
                "desk on both halves of a vertical frame, identical posture, a hairline vertical "
                "divider down the exact centre, single overhead practical lamp on each side",
                "Absolutely locked. At 1.4s the left figure blinks and shifts weight; the right "
                "figure holds perfectly still for another full second.",
                text="MONDAY",
                sfx="Doubled, slightly phased room tone.",
                music="None.",
            ),
            _shot(
                2, 3.5, 9.0, "escalation", "MS",
                "50mm, locked, split frame maintained",
                "Left: forty-one browser tabs, three chat windows, cold coffee, 2am on the clock. "
                "Right: one card on the desk, laptop closed, lamp off.",
                "split composition, left half a cluttered desk at night with a monitor covered in "
                "browser tabs and chat windows and a cold coffee, right half the same desk almost "
                "empty with a single printed card and a closed laptop, one warm lamp, deep shadow",
                "Both halves locked. Left half has constant micro-motion - notifications, cursor, "
                "flicker. Right half is completely still.",
                text="41 TABS          1 CARD",
                vo="Same trader. Same week.",
                sfx="Left: keyboard, notification stack, a fan. Right: one clock.",
                music="Low pulse enters, 90bpm, only under the left half.",
            ),
            _shot(
                3, 9.0, 14.5, "escalation", "CU",
                "85mm, locked, split frame",
                "Left: he clicks BUY at the top of a green candle, jaw tight. Right: he does "
                "nothing, and a marked level on a chart waits below price.",
                "split composition close-up, left half a hand clicking a glowing buy button with a "
                "green candlestick spiking, right half a hand resting still beside a chart with a "
                "single horizontal marked level drawn below current price",
                "Left half accelerates - three quick cuts inside the half-frame. Right half never "
                "cuts.",
                vo="One of them chased it.",
                sfx="Left: a click, a spike, a breath in. Right: silence.",
                music="Pulse tightens.",
            ),
            _shot(
                4, 14.5, 20.0, "turn", "MS",
                "50mm, locked, split frame",
                "Left: red, and the small physical collapse of someone who knew better. Right: "
                "price comes down to the marked level and fills it. No celebration.",
                "split composition, left half a mans shoulders dropping in front of a red falling "
                "chart, right half the same man unchanged as a price line quietly touches a marked "
                "horizontal level, restrained lighting on both sides",
                "Left half slumps over 2s. Right half does not move at all.",
                vo="One of them had a level.",
                sfx="Left: the pulse drops out abruptly. Right: one soft tone as the level fills.",
                music="Left channel of the mix goes dead.",
            ),
            _shot(
                5, 20.0, 26.0, "turn", "ECU",
                "100mm macro on the divider, rack focus",
                "The hairline divider between the two halves is revealed to be a single thread of "
                "signal-green light. It is the only difference between the two lives.",
                "extreme macro of a single hairline vertical thread of green light running down the "
                "centre of a dark frame, everything else falling out of focus, faint haze, the "
                "thread perfectly straight and impossibly thin",
                "Rack focus from both sides onto the thread. The thread brightens by one stop.",
                text="One had the consensus.",
                vo="The only difference is what he was holding on Monday morning.",
                sfx="A single sustained tone.",
                music="Everything else out.",
                out="match cut",
            ),
            _shot(
                6, 26.0, 33.0, "proof", "insert",
                "85mm, slow push",
                "The thread widens into the card itself: direction, entry, targets, stop, and a "
                "confidence level that is honest about itself.",
                "a thin line of green light widening into a dark glass card carrying precise "
                "monospace trade levels and a confidence readout, hairline rules, tabular figures, "
                "warm rake light across the glass",
                "The thread widens over 10 frames into the card, then a slow 12cm push in.",
                text="16,564 traders\n74.1% of tracked directions hit\nwin = target 1/2 reached, or a 2% move in the forecast direction",
                vo="Sixteen and a half thousand traders, distilled into one plan a week.",
                sfx="Four soft clicks as the lines land.",
                music="Pulse returns, fuller.",
            ),
            _shot(
                7, 33.0, 39.5, "resolution", "WS",
                "35mm, the left half fades, the right expands",
                "The left half of the frame goes to black and the right half expands to fill the "
                "screen. He closes the laptop and leaves. The desk stays lit.",
                "a dark room where one half of the image falls to black and the other expands to "
                "full frame, a man closing a laptop and walking out of frame, single warm lamp left "
                "burning on an almost empty desk",
                "The divider slides left over 1.5s as the left half loses exposure. Then a static "
                "hold on the empty desk.",
                vo="Five minutes on Monday. The rest of the week is yours.",
                sfx="A laptop closing. A door. Room tone.",
                music="One sustained note.",
                out="dissolve",
            ),
            _shot(
                8, 39.5, 45.0, "cta", "MS",
                "Locked, centred",
                "End card on ink. Wordmark, green underline drawing in, url in mono, legal line.",
                "minimal end card on near-black, clean grotesque wordmark centred, thin green "
                "horizontal rule drawing beneath, small monospace url, generous negative space",
                "Underline draws over 12 frames, then a 3-second hold.",
                text="CROWDWISDOM TRADING\ncrowdwisdomtrading.com\nNot financial advice. Capital at risk.",
                vo="CrowdWisdom Trading.",
                sfx="One soft close.",
                music="Resolves to silence.",
            ),
        ],
        "voiceover_full": (
            "Same trader. Same week. One of them chased it. One of them had a level. The only "
            "difference is what he was holding on Monday morning: sixteen and a half thousand "
            "traders, distilled into one plan a week. Five minutes on Monday - the rest of the "
            "week is yours. CrowdWisdom Trading."
        ),
        "on_screen_text_full": [
            "MONDAY",
            "41 TABS / 1 CARD",
            "One had the consensus.",
            "16,564 traders",
            "74.1% of tracked directions hit",
            "win = target 1/2 reached, or a 2% move in the forecast direction",
            "CROWDWISDOM TRADING / crowdwisdomtrading.com",
        ],
        "cta": "Get this week's consensus free at crowdwisdomtrading.com",
        "end_card": "Wordmark on ink, green underline drawing in, url in mono, legal line beneath.",
        "music_direction": (
            "Silence to 3.5s. A 90bpm pulse that lives only in the left channel while the two "
            "timelines run in parallel - so the mix itself is asymmetric. Everything out at 20s. "
            "Full return at 26s, resolving on the card."
        ),
        "sound_design_direction": (
            "Hard stereo separation: chaos left, discipline right. When the left half dies at 20s "
            "the audience feels the mix collapse to mono before they consciously see it."
        ),
        "claims_used": ["traders_tracked", "hit_rate", "research_compression"],
        "compliance_notes": [
            "The two timelines are explicitly illustrative and no monetary outcome is shown.",
            "The 74.1% claim appears with its definition on the same card.",
            "No profit, income or guarantee is stated or implied.",
            "End card carries not-financial-advice and capital-at-risk.",
        ],
        "why_this_works": (
            "Every rival ad shows the winner. This one shows the same person twice, which removes "
            "the excuse - the viewer cannot say the winner was smarter, luckier or richer, because "
            "the winner is him. The split frame is also the media buy: it reads at thumbnail size, "
            "it works muted, and the asymmetric mix means the ad is doing something even for the "
            "twenty percent who watch with sound."
        ),
    }


_BUILDERS = {
    "pain_led": lambda brief: _pain_led(),
    "data_led": _data_led,
    "outcome_led": lambda brief: _outcome_led(),
}


def fallback_script(
    angle_id: str, duration: float, aspect: str, data_brief: dict[str, Any] | None = None
) -> dict[str, Any]:
    builder = _BUILDERS.get(angle_id, _BUILDERS["pain_led"])
    script = builder(data_brief or {})
    script["duration_seconds"] = duration
    script["aspect_ratio"] = aspect
    return script
