import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from utils import start

start()

st.markdown("""
<style>
#matrix-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: #2F3438;
}
#matrix-bg canvas { width: 100%; height: 100%; opacity: .28; }
.stApp { background: transparent !important; }
.stApp > header { background: transparent !important; }
.block-container { position: relative; z-index: 1; }
</style>
<div id="matrix-bg"><canvas id="mx"></canvas></div>
<script>
const cv = document.getElementById('mx'), ctx = cv.getContext('2d');
const chars = '01アイウエオ<>/{}[]ZBT';
const fs = 14;
let cols = 0, drops = [];
function init() {
  cv.width = window.innerWidth; cv.height = window.innerHeight;
  cols = Math.floor(cv.width / fs);
  drops = Array(cols).fill(1);
}
init();
window.addEventListener('resize', init);
function draw() {
  ctx.fillStyle = 'rgba(47,52,56,0.12)';
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = '#62C6C4';
  ctx.font = fs + 'px monospace';
  for (let i = 0; i < drops.length; i++) {
    ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * fs, drops[i] * fs);
    if (drops[i] * fs > cv.height && Math.random() > 0.975) drops[i] = 0;
    drops[i]++;
  }
}
setInterval(draw, 50);
</script>
""", unsafe_allow_html=True)

BG_FILE = Path(__file__).parent / "assets" / "sabor.jpg"
if BG_FILE.exists():
    bg_url = "data:image/jpeg;base64," + base64.b64encode(BG_FILE.read_bytes()).decode()
else:
    bg_url = ""  # bez slike ostaje tamni gradijent

HERO = """
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono&display=swap');
html, body { margin:0; height:100%; background:#2F3438; overflow:hidden; font-family:Inter, sans-serif; }
.hero {
  position:relative; height:100%; width:100%;
  background: linear-gradient rgba(47,52,56,.55), rgba(47,52,56,.92)), url('__BG__') center/cover no-repeat, #050B14;
}
canvas { position:absolute; inset:0; width:100%; height:100%; opacity:.35; mix-blend-mode:screen; }
.scan { position:absolute; inset:0; pointer-events:none;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.03) 0 1px, transparent 1px 3px); }
.content { position:absolute; inset:0; display:flex; flex-direction:column; justify-content:center; padding:0 48px; color:#E2E8F0; }
.kicker { font-family:'JetBrains Mono', monospace; font-size:12px; letter-spacing:.2em; color:#62C6C4; }
h1 { font-size:44px; font-weight:700; letter-spacing:-.02em; margin:10px 0 8px; color:#fff;
     text-shadow:0 0 18px rgba(98,198,196,.35); }
p { margin:0; color:#94A3B8; font-size:15px; max-width:560px; line-height:1.6; }
.credit { margin-top:28px; padding-top:16px; border-top:1px solid rgba(148,163,184,.25); font-size:13px; color:#CBD5E1; }
.credit b { color:#fff; }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#62C6C4;
       box-shadow:0 0 8px #62C6C4; margin-right:8px; }
</style></head>
<body>
<div class="hero">
  <canvas id="c"></canvas>
  <div class="scan"></div>
  <div class="content">
    <div class="kicker">ZBT CONSULTING · INTERNI ALAT</div>
    <h1>Praćenje vijesti</h1>
    <p>Javne politike, nabave i akteri u Hrvatskoj, BiH i Crnoj Gori, na jednom mjestu.</p>
    <div class="credit"><span class="dot"></span>Izradio <b>Marin Pepić</b>, Account Manager, ZBT Consulting</div>
  </div>
</div>
<script>
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const chars = '01アイウエオ<>/{}[]ZBT';
const fs = 14;
let cols = 0, drops = [];
function init() {
  cv.width = cv.offsetWidth; cv.height = cv.offsetHeight;
  cols = Math.floor(cv.width / fs);
  drops = Array(cols).fill(1);
}
init();
window.addEventListener('resize', init);
function draw() {
  ctx.fillStyle = 'rgba(47,52,56,0.12)';
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = '#38BDF8';
  ctx.font = fs + 'px JetBrains Mono, monospace';
  for (let i = 0; i < drops.length; i++) {
    ctx.fillText(chars[Math.floor(Math.random() * chars.length)], i * fs, drops[i] * fs);
    if (drops[i] * fs > cv.height && Math.random() > 0.975) drops[i] = 0;
    drops[i]++;
  }
}
setInterval(draw, 50);
</script>
</body></html>
"""

st.markdown("""
<div style="padding: 3rem 0 1.5rem 0;">
  <div style="font-family: monospace; font-size: 12px; letter-spacing: .2em; color: #62C6C4;">ZBT CONSULTING · INTERNI ALAT</div>
  <h1 style="color:#FFFFFF; font-size:44px; margin:10px 0 8px; font-weight:700;">Praćenje vijesti</h1>
  <p style="color:#CBD5E1; font-size:15px; max-width:560px;">Javne politike, nabave i akteri u Hrvatskoj, BiH i Crnoj Gori, na jednom mjestu.</p>
  <div style="margin-top:24px; padding-top:14px; border-top:1px solid rgba(148,163,184,.3); color:#E2E8F0; font-size:13px;">
    Izradio <b style="color:#fff">Marin Pepić</b>, Account Manager, ZBT Consulting
  </div>
</div>
""", unsafe_allow_html=True)

st.write("")

NAV = [
    ("Airbnb", "pages/1_Airbnb.py", "Regulativa i tržište kratkoročnog najma"),
    ("Huawei", "pages/2_Huawei.py", "CSA2, NIS2 i geopolitika"),
    ("WEYTEC", "pages/3_WEYTEC.py", "Nabave kontrolnih soba i centara"),
    ("Envoid", "pages/4_Envoid.py", "Mobilna sigurnost i spyware"),
    ("Akteri", "pages/5_Akteri.py", "Institucije i državna poduzeća"),
    ("Arhiva", "pages/6_Arhiva.py", "Spremljene vijesti i bilješke"),
]

cols = st.columns(3)
for i, (naziv, path, opis) in enumerate(NAV):
    with cols[i % 3]:
        with st.container(border=True):
            st.markdown(f"**{naziv}**")
            st.caption(opis)
            st.page_link(path, label="Otvori →")
