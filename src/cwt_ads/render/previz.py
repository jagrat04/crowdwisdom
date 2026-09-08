"""The animatic.

Renders the storyboard bundle into one self-contained HTML file that actually
plays: shots advance on their real timecodes, on-screen text lands where the
script says it lands, the voiceover runs as subtitles, and the palette is the
brand palette. It is a previz - not the finished film - but it is the fastest
honest way to answer "does the first three seconds work?" before spending a
cent on generation.

No build step, no CDN, no keys. Open the file.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import brand
from ..logging_utils import ok
from ..schemas import StoryboardBundle

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --ink:__INK__; --signal:__SIGNAL__; --noise:__NOISE__;
  --paper:__PAPER__; --brass:__BRASS__;
  --line:rgba(234,240,255,.14); --dim:rgba(234,240,255,.52);
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:"Helvetica Neue",Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--ink);color:var(--paper);font-family:var(--sans);
  -webkit-font-smoothing:antialiased}
body{padding:0 0 96px}
a{color:var(--signal)}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}

/* header */
header{padding:56px 0 28px;border-bottom:1px solid var(--line);margin-bottom:32px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.34em;text-transform:uppercase;
  color:var(--dim)}
h1{font-size:clamp(34px,6vw,64px);line-height:.94;letter-spacing:-.03em;margin:14px 0 10px;
  font-weight:300;text-transform:uppercase}
.logline{max-width:66ch;color:var(--dim);font-size:17px;line-height:1.55;margin:0}
.meta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.chip{font-family:var(--mono);font-size:11px;letter-spacing:.08em;padding:6px 11px;
  border:1px solid var(--line);border-radius:2px;color:var(--dim);text-transform:uppercase}
.chip.on{border-color:var(--signal);color:var(--signal)}

/* script switcher */
.tabs{display:flex;gap:0;flex-wrap:wrap;margin:0 0 34px;border-bottom:1px solid var(--line)}
.tab{appearance:none;background:none;border:0;border-bottom:2px solid transparent;color:var(--dim);
  font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  padding:14px 20px;cursor:pointer;transition:.18s}
.tab:hover{color:var(--paper)}
.tab[aria-selected="true"]{color:var(--paper);border-bottom-color:var(--signal)}
.tab .hero{color:var(--brass);margin-left:8px;font-size:10px}

/* stage */
.stage-row{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:36px;
  align-items:start}
@media(max-width:820px){.stage-row{grid-template-columns:1fr}}
.stage{position:relative;aspect-ratio:9/16;border-radius:3px;overflow:hidden;
  background:radial-gradient(120% 90% at 50% 18%,#101a2a 0%,#05070d 62%,#000 100%);
  border:1px solid var(--line);box-shadow:0 40px 90px -50px #000}
.stage::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(120% 80% at 50% 50%,transparent 42%,rgba(0,0,0,.72) 100%)}
/* the ground under each beat - the animatic's only "art direction" */
.ground{position:absolute;inset:0;transition:background 600ms ease, opacity 400ms ease;z-index:1}
.stage[data-beat="hook"] .ground{
  background:radial-gradient(70% 45% at 50% 38%,rgba(234,240,255,.16),transparent 70%);
  animation:pulse 1.1s ease-in-out infinite}
.stage[data-beat="escalation"] .ground{
  background:
    repeating-linear-gradient(105deg,rgba(255,59,92,.10) 0 2px,transparent 2px 9px),
    radial-gradient(80% 50% at 50% 45%,rgba(255,59,92,.13),transparent 72%);
  animation:jitter .22s steps(2) infinite}
.stage[data-beat="turn"] .ground{
  background:radial-gradient(52% 34% at 50% 46%,rgba(0,229,160,.14),transparent 74%)}
.stage[data-beat="proof"] .ground{
  background:
    repeating-linear-gradient(0deg,rgba(200,169,106,.10) 0 1px,transparent 1px 26px),
    repeating-linear-gradient(90deg,rgba(200,169,106,.10) 0 1px,transparent 1px 26px),
    radial-gradient(70% 45% at 50% 50%,rgba(0,229,160,.07),transparent 76%)}
.stage[data-beat="resolution"] .ground{
  background:linear-gradient(190deg,rgba(234,240,255,.13),transparent 58%)}
.stage[data-beat="cta"] .ground{
  background:radial-gradient(60% 34% at 50% 50%,rgba(0,229,160,.10),transparent 72%)}
@keyframes pulse{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes jitter{0%{transform:translate(0,0)}50%{transform:translate(-1px,1px)}
  100%{transform:translate(1px,0)}}
.scan{position:absolute;left:0;right:0;height:1px;background:rgba(0,229,160,.5);
  filter:blur(.4px);z-index:2;pointer-events:none;opacity:.5;
  animation:scan 5.5s linear infinite}
@keyframes scan{0%{top:-2%}100%{top:102%}}
.grain{position:absolute;inset:-120%;opacity:.055;pointer-events:none;mix-blend-mode:screen;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3'/></filter><rect width='140' height='140' filter='url(%23n)'/></svg>");
  animation:grain 900ms steps(4) infinite}
@keyframes grain{0%{transform:translate(0,0)}25%{transform:translate(-3%,2%)}
  50%{transform:translate(2%,-3%)}75%{transform:translate(-2%,-2%)}100%{transform:translate(0,0)}}
.frame{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:space-between;
  padding:22px 20px;z-index:2}
.frame-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.beat{font-family:var(--mono);font-size:10px;letter-spacing:.24em;text-transform:uppercase;
  color:var(--signal)}
.tc{font-family:var(--mono);font-size:10px;letter-spacing:.12em;color:var(--dim)}
.frame-mid{flex:1;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:14px 4px}
.ost{font-size:clamp(17px,2.6vw,26px);line-height:1.24;letter-spacing:-.01em;font-weight:300;
  text-transform:uppercase;white-space:pre-line;text-wrap:balance}
.ost .fine{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.06em;
  text-transform:none;color:var(--dim);margin-top:12px;line-height:1.5}
.visual-note{color:var(--dim);font-size:12.5px;line-height:1.5;max-width:34ch;white-space:pre-line}
.frame-bot{display:flex;flex-direction:column;gap:10px}
.vo{font-family:var(--mono);font-size:11.5px;line-height:1.6;color:var(--paper);
  border-left:2px solid var(--signal);padding-left:10px;min-height:18px}
.sfx{font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.04em}
.flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none;z-index:3}

/* transport */
.transport{margin-top:14px}
.bar{position:relative;height:3px;background:rgba(234,240,255,.12);cursor:pointer;border-radius:2px}
.fill{position:absolute;left:0;top:0;bottom:0;background:var(--signal);border-radius:2px;width:0}
.ticks{position:absolute;inset:0}
.tick{position:absolute;top:-4px;width:1px;height:11px;background:rgba(234,240,255,.3)}
.controls{display:flex;align-items:center;gap:14px;margin-top:12px}
button.ctl{appearance:none;background:none;border:1px solid var(--line);color:var(--paper);
  font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  padding:9px 16px;cursor:pointer;border-radius:2px;transition:.18s}
button.ctl:hover{border-color:var(--signal);color:var(--signal)}
.clock{font-family:var(--mono);font-size:11px;color:var(--dim);margin-left:auto}

/* side panels */
.panel{border:1px solid var(--line);border-radius:3px;padding:22px 24px;margin-bottom:18px}
.panel h3{margin:0 0 14px;font-family:var(--mono);font-size:10.5px;letter-spacing:.26em;
  text-transform:uppercase;color:var(--dim);font-weight:400}
.panel p{margin:0 0 12px;line-height:1.62;font-size:14.5px}
.panel p:last-child{margin-bottom:0}
.kv{display:grid;grid-template-columns:130px minmax(0,1fr);gap:10px 18px;font-size:14px;
  line-height:1.55}
.kv dt{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim);padding-top:3px}
.kv dd{margin:0}
.hook{border-color:rgba(0,229,160,.34);background:linear-gradient(180deg,rgba(0,229,160,.05),transparent 70%)}
ul.clean{margin:0;padding-left:18px;line-height:1.62;font-size:14px}
ul.clean li{margin-bottom:7px}
.tagrow{display:flex;flex-wrap:wrap;gap:7px}
.tag{font-family:var(--mono);font-size:10px;letter-spacing:.1em;padding:5px 9px;border-radius:2px;
  border:1px solid var(--brass);color:var(--brass);text-transform:uppercase}

/* shot table */
section.shots{margin-top:46px}
h2{font-size:12px;font-family:var(--mono);letter-spacing:.3em;text-transform:uppercase;
  color:var(--dim);font-weight:400;margin:0 0 20px;padding-bottom:12px;
  border-bottom:1px solid var(--line)}
.shot{display:grid;grid-template-columns:64px minmax(0,1fr);gap:22px;padding:22px 0;
  border-bottom:1px solid var(--line);cursor:pointer;transition:.18s}
.shot:hover{background:rgba(234,240,255,.028)}
.shot.active{background:rgba(0,229,160,.055)}
.shot-n{font-family:var(--mono);font-size:11px;color:var(--dim);letter-spacing:.1em}
.shot-n b{display:block;color:var(--signal);font-size:22px;font-weight:300;letter-spacing:0;
  margin-bottom:5px}
.shot-body h4{margin:0 0 6px;font-size:16px;font-weight:400;line-height:1.4}
.shot-body .sub{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--dim);
  text-transform:uppercase;margin-bottom:11px}
.prompt{font-family:var(--mono);font-size:11.5px;line-height:1.65;color:var(--dim);
  border-left:1px solid var(--line);padding-left:13px;margin-top:11px;white-space:pre-wrap}
.prompt b{color:var(--paper);font-weight:400}
footer{margin-top:60px;padding-top:24px;border-top:1px solid var(--line);
  font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--dim);line-height:2}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">CrowdWisdom Trading &middot; Storyboard &amp; Animatic</div>
    <h1 id="title"></h1>
    <p class="logline" id="logline"></p>
    <div class="meta" id="meta"></div>
  </header>

  <div class="tabs" id="tabs" role="tablist"></div>

  <div class="stage-row">
    <div>
      <div class="stage" id="stage" data-beat="hook">
        <div class="ground"></div>
        <div class="scan"></div>
        <div class="grain"></div>
        <div class="flash" id="flash"></div>
        <div class="frame">
          <div class="frame-top">
            <span class="beat" id="beat"></span>
            <span class="tc" id="tc"></span>
          </div>
          <div class="frame-mid">
            <div>
              <div class="ost" id="ost"></div>
              <div class="visual-note" id="visual"></div>
            </div>
          </div>
          <div class="frame-bot">
            <div class="vo" id="vo"></div>
            <div class="sfx" id="sfx"></div>
          </div>
        </div>
      </div>
      <div class="transport">
        <div class="bar" id="bar"><div class="ticks" id="ticks"></div><div class="fill" id="fill"></div></div>
        <div class="controls">
          <button class="ctl" id="play">Play</button>
          <button class="ctl" id="restart">Restart</button>
          <span class="clock" id="clock">0.0 / 0.0s</span>
        </div>
      </div>
    </div>

    <div>
      <div class="panel hook">
        <h3>The visual hook &mdash; first 3 seconds</h3>
        <dl class="kv" id="hook"></dl>
      </div>
      <div class="panel">
        <h3>Why this film</h3>
        <p id="why"></p>
      </div>
      <div class="panel">
        <h3>Sound</h3>
        <dl class="kv" id="sound"></dl>
      </div>
      <div class="panel">
        <h3>Claims audit &amp; compliance</h3>
        <div class="tagrow" id="claims"></div>
        <ul class="clean" id="compliance" style="margin-top:14px"></ul>
      </div>
    </div>
  </div>

  <section class="shots">
    <h2>Shot list</h2>
    <div id="shotlist"></div>
  </section>

  <footer id="footer"></footer>
</div>

<script id="payload" type="application/json">__DATA__</script>
<script>
(function(){
  const DATA = JSON.parse(document.getElementById("payload").textContent);
  const scripts = DATA.scripts || [];
  const $ = (id) => document.getElementById(id);
  let idx = 0, t = 0, playing = false, last = 0, raf = null;

  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

  function current(){ return scripts[idx] || {shots:[]}; }
  function runtime(){ const s = current().shots; return s.length ? s[s.length-1].t_end : 0; }
  function shotAt(time){
    const s = current().shots;
    for (const sh of s) if (time >= sh.t_start && time < sh.t_end) return sh;
    return s[s.length-1] || null;
  }

  function buildTabs(){
    $("tabs").innerHTML = scripts.map((s,i) =>
      '<button class="tab" role="tab" data-i="'+i+'" aria-selected="'+(i===idx)+'">'+
      esc(s.angle||s.id)+(s.id===DATA.hero_script_id?'<span class="hero">HERO</span>':'')+
      '</button>').join("");
    $("tabs").querySelectorAll(".tab").forEach(b =>
      b.onclick = () => {
        stop(); idx = +b.dataset.i; select();
        document.querySelector(".stage-row").scrollIntoView({behavior:"smooth", block:"center"});
      });
  }

  function fine(text){
    // Lines that read as legal/qualifier copy render small, like they would on screen.
    return String(text||"").split("\\n").map(line =>
      /^(win =|not financial|capital at risk|[a-z])/.test(line.trim())
        ? '<span class="fine">'+esc(line)+'</span>'
        : esc(line)
    ).join("\\n");
  }

  function select(){
    const s = current();
    $("title").textContent = s.title || "";
    $("logline").textContent = s.logline || "";
    $("meta").innerHTML = [
      ['chip on', (s.duration_seconds||0)+"s"],
      ['chip', s.aspect_ratio||""],
      ['chip', (s.shots||[]).length+" shots"],
      ['chip', s.angle_source||""],
      ['chip', "ICP: "+(s.icp||"")]
    ].filter(x=>x[1]).map(x=>'<span class="'+x[0]+'">'+esc(x[1])+'</span>').join("");

    const h = s.visual_hook || {};
    $("hook").innerHTML = [
      ["Concept", h.concept], ["Frame 0", h.first_frame], ["The event", h.the_event],
      ["Mechanism", h.why_it_stops_the_scroll], ["Sound at 0", h.sound_at_zero]
    ].filter(r=>r[1]).map(r=>"<dt>"+esc(r[0])+"</dt><dd>"+esc(r[1])+"</dd>").join("");

    $("why").textContent = s.why_this_works || "";
    $("sound").innerHTML = [
      ["Music", s.music_direction], ["Design", s.sound_design_direction], ["CTA", s.cta]
    ].filter(r=>r[1]).map(r=>"<dt>"+esc(r[0])+"</dt><dd>"+esc(r[1])+"</dd>").join("");

    $("claims").innerHTML = (s.claims_used||[]).map(c=>'<span class="tag">'+esc(c)+"</span>").join("");
    $("compliance").innerHTML = (s.compliance_notes||[]).map(c=>"<li>"+esc(c)+"</li>").join("");

    $("shotlist").innerHTML = (s.shots||[]).map(sh =>
      '<div class="shot" data-t="'+sh.t_start+'">'+
        '<div class="shot-n"><b>'+String(sh.n).padStart(2,"0")+"</b>"+
          esc(sh.t_start.toFixed(1))+"s<br>"+esc((sh.t_end-sh.t_start).toFixed(1))+"s</div>"+
        '<div class="shot-body">'+
          "<h4>"+esc(sh.visual)+"</h4>"+
          '<div class="sub">'+esc(sh.beat)+" &middot; "+esc(sh.shot_size||"")+" &middot; "+
            esc(sh.camera||"")+" &middot; out: "+esc(sh.transition_out||"cut")+"</div>"+
          (sh.on_screen_text?'<div class="prompt"><b>ON SCREEN</b>\\n'+esc(sh.on_screen_text)+"</div>":"")+
          (sh.voiceover?'<div class="prompt"><b>VO</b>\\n'+esc(sh.voiceover)+"</div>":"")+
          '<div class="prompt"><b>IMAGE PROMPT</b>\\n'+esc(sh.image_prompt)+"</div>"+
          (sh.motion_prompt?'<div class="prompt"><b>MOTION</b>\\n'+esc(sh.motion_prompt)+"</div>":"")+
          (sh.sfx?'<div class="prompt"><b>SFX</b>\\n'+esc(sh.sfx)+"</div>":"")+
        "</div></div>").join("");
    $("shotlist").querySelectorAll(".shot").forEach(el =>
      el.onclick = () => { t = parseFloat(el.dataset.t)+0.01; draw(); });

    const total = runtime();
    $("ticks").innerHTML = (s.shots||[]).map(sh =>
      '<span class="tick" style="left:'+(total?(sh.t_start/total*100):0)+'%"></span>').join("");

    buildTabs();
    t = 0; draw();
  }

  let lastShotN = null;
  function draw(){
    const s = current(), total = runtime(), sh = shotAt(t);
    $("fill").style.width = (total ? (t/total*100) : 0) + "%";
    $("clock").textContent = t.toFixed(1) + " / " + total.toFixed(1) + "s";
    if (!sh) return;
    $("stage").dataset.beat = (sh.beat || "hook").toLowerCase();
    $("beat").textContent = sh.beat || "";
    $("tc").textContent = "SHOT " + String(sh.n).padStart(2,"0") + "  " +
      sh.t_start.toFixed(1) + "-" + sh.t_end.toFixed(1) + "s";
    $("ost").innerHTML = fine(sh.on_screen_text);
    $("visual").textContent = sh.visual || "";
    $("vo").textContent = sh.voiceover || "";
    $("sfx").textContent = [sh.sfx, sh.music].filter(Boolean).join("   |   ");
    document.querySelectorAll(".shot").forEach(el =>
      el.classList.toggle("active", Math.abs(parseFloat(el.dataset.t) - sh.t_start) < 0.001));
    if (sh.n !== lastShotN){
      lastShotN = sh.n;
      const f = $("flash");
      f.style.transition = "none"; f.style.opacity = sh.beat === "hook" ? .22 : .08;
      requestAnimationFrame(() => { f.style.transition = "opacity 260ms ease-out"; f.style.opacity = 0; });
    }
  }

  function tick(now){
    if (!playing) return;
    const dt = (now - last)/1000; last = now; t += dt;
    if (t >= runtime()){ t = runtime(); stop(); }
    draw(); raf = requestAnimationFrame(tick);
  }
  function play(){ if(playing) return; if(t>=runtime()) t=0; playing=true;
    $("play").textContent="Pause"; last=performance.now(); raf=requestAnimationFrame(tick); }
  function stop(){ playing=false; $("play").textContent="Play"; if(raf) cancelAnimationFrame(raf); }

  $("play").onclick = () => playing ? stop() : play();
  $("restart").onclick = () => { t=0; draw(); play(); };
  $("bar").onclick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    t = Math.max(0, Math.min(runtime(), (e.clientX-r.left)/r.width*runtime())); draw();
  };
  document.addEventListener("keydown", e => {
    if (e.code === "Space"){ e.preventDefault(); playing ? stop() : play(); }
  });

  $("footer").innerHTML = "Generated " + esc(DATA.generated_at||"") +
    " &middot; hero cut: " + esc(DATA.hero_script_id||"-") +
    "<br>Animatic only. Final render is produced by the Video Agent through OpenMontage." +
    "<br>Not financial advice. Capital at risk.";
  select();
})();
</script>
</body>
</html>
"""


def write_animatic(bundle: StoryboardBundle, path: Path) -> Path:
    palette = brand()["look"]["palette"]
    payload = bundle.model_dump(mode="json")
    html = (
        TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, default=str))
        .replace("__TITLE__", "CrowdWisdom - Storyboard")
        .replace("__INK__", palette["ink"])
        .replace("__SIGNAL__", palette["signal"])
        .replace("__NOISE__", palette["noise"])
        .replace("__PAPER__", palette["paper"])
        .replace("__BRASS__", palette["brass"])
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    ok("wrote " + path.name + "  (playable animatic - open it in a browser)")
    return path
