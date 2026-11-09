import streamlit as st
import streamlit.components.v1 as components
from utils import pristupni_kljuc, start

start()
KLJUC = pristupni_kljuc()

# Kisa u pozadini: iframe se rasteze preko cijelog ekrana i ide iza sadrzaja
components.html("""
<!DOCTYPE html>
<html><head><style>
html, body { margin:0; background:transparent; overflow:hidden; }
canvas { position:fixed; inset:0; width:100vw; height:100vh; opacity:.28; }
</style></head>
<body><canvas id="mx"></canvas>
<script>
const cv = document.getElementById('mx'), ctx = cv.getContext('2d');
const chars = '01アイウエオ<>/{}[]ZBT';
const fs = 14;
let drops = [];
function init() {
  cv.width = window.innerWidth; cv.height = window.innerHeight;
  drops = Array(Math.floor(cv.width / fs)).fill(1);
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
</script></body></html>
""", height=0)

st.markdown("""
<style>
.stApp { background: #2F3438 !important; }
iframe[title="streamlit_components.v1.html"], iframe[title="st.iframe"] {
    position: fixed !important; top: 0; left: 0;
    width: 100vw !important; height: 100vh !important;
    z-index: 0; pointer-events: none; border: 0;
}
.block-container { position: relative; z-index: 1; }
a.zbt-card {
    display: block; text-decoration: none !important; background: #FFFFFF;
    border: 1px solid #DDE2E5; border-radius: 14px; padding: 1.1rem 1.25rem;
    margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15,23,42,.05);
    transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
a.zbt-card:hover {
    transform: translateY(-2px); border-color: #3FA9A7;
    box-shadow: 0 8px 20px rgba(15,23,42,.18);
}
.zbt-title { display: block; color: #2F3438 !important; font-weight: 600; font-size: 1rem; }
.zbt-desc  { display: block; color: #6B7378 !important; font-size: .85rem; margin-top: .3rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 3rem 0 1.5rem 0;">
<div style="font-family: monospace; font-size: 12px; letter-spacing: .2em; color: #62C6C4;">ZBT CONSULTING · INTERNI ALAT</div>
<h1 style="color:#FFFFFF; font-size:44px; margin:10px 0 8px; font-weight:700;">Praćenje vijesti</h1>
<p style="color:#CBD5E1; font-size:15px; max-width:560px;">Javne politike, nabave i akteri u Hrvatskoj, BiH i Crnoj Gori, na jednom mjestu.</p>
<div style="margin-top:24px; padding-top:14px; border-top:1px solid rgba(148,163,184,.3); color:#E2E8F0; font-size:13px;">Izradio <b style="color:#fff">Marin Pepić</b>, Account Manager, ZBT Consulting</div>
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
            f'<a href="/{url}?k={KLJUC}" target="_self" class="zbt-card">'
            f'<span class="zbt-title">{naziv}</span>'
            f'<span class="zbt-desc">{opis}</span></a>',
            unsafe_allow_html=True,
        )
