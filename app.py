import streamlit as st
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

.zbt-card {
    display: block; text-decoration: none; background: #FFFFFF;
    border: 1px solid #DDE2E5; border-radius: 14px; padding: 1.1rem 1.25rem;
    margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15,23,42,.05);
    transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.zbt-card:hover { transform: translateY(-2px); border-color: #3FA9A7;
    box-shadow: 0 8px 20px rgba(15,23,42,.10); }
.zbt-title { color: #2F3438; font-weight: 600; font-size: 1rem; }
.zbt-desc  { color: #6B7378; font-size: .85rem; margin-top: .3rem; }
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

NAV = [
    ("Airbnb", "Airbnb", "Regulativa i tržište kratkoročnog najma"),
    ("Huawei", "Huawei", "CSA2, NIS2 i geopolitika"),
    ("WEYTEC", "WEYTEC", "Nabave kontrolnih soba i centara"),
    ("Envoid", "Envoid", "Mobilna sigurnost i spyware"),
    ("Akteri", "Akteri", "Institucije i državna poduzeća"),
    ("Arhiva", "Arhiva", "Spremljene vijesti i bilješke"),
]

cols = st.columns(3)
for i, (naziv, url, opis) in enumerate(NAV):
    with cols[i % 3]:
        st.markdown(
            f'<a href="/{url}" target="_self" class="zbt-card">'
            f'<div class="zbt-title">{naziv}</div>'
            f'<div class="zbt-desc">{opis}</div></a>',
            unsafe_allow_html=True,
        )
