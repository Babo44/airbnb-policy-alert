"""Prikaz u Streamlit aplikaciji. Pretraga se radi u osvjezi.py (GitHub Actions),
a aplikacija cita gotove rezultate iz Supabasea."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta

import streamlit as st

import core
from core import CLIENTS, DANA_UNAZAD, MIN_RELEVANTNOST, ZASTAVE, parse_date, razdoblje

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #F4F6F7;
    --surface: #FFFFFF;
    --ink: #2F3438;
    --muted: #6B7378;
    --line: #DDE2E5;
    --accent: #3FA9A7;
    --accent-soft: #E8F6F5;
    --brand-gray: #545A5E;
}
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--ink);
}
.stApp { background: var(--bg); }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 960px; padding-top: 2.5rem; padding-bottom: 4rem; }
h1 { font-weight: 700; font-size: 1.9rem; letter-spacing: -0.03em; color: var(--ink); }
h5 { font-size: 1.02rem; font-weight: 600; line-height: 1.4; margin: 0 0 0.35rem 0; }
h5 a { color: var(--ink); text-decoration: none; }
h5 a:hover { color: var(--accent); }
a { color: var(--accent); }
[data-testid="stCaptionContainer"] { color: var(--muted); font-size: 0.82rem; }
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: var(--surface);
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 4px 12px rgba(15,23,42,.03);
}
.stButton > button {
    border-radius: 8px; border: 1px solid var(--line); background: var(--surface);
    color: var(--ink); font-weight: 500; font-size: 0.85rem;
}
.stButton > button:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
section[data-testid="stSidebar"] { background: var(--brand-gray); }
section[data-testid="stSidebar"] * { color: #E2E8F0; }
hr { margin: 1.25rem 0; border: none; border-top: 1px solid var(--line); }
.zbt-rok { display:inline-block; background:#FFF4E5; color:#9A5B00; border-radius:6px;
           padding:1px 8px; font-size:.78rem; font-weight:600; margin-left:4px; }
"""

KLJUCEVI = ["ANTHROPIC_API_KEY", "EXA_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "CLAUDE_MODEL"]


def pristupni_kljuc():
    """Kljuc izveden iz lozinke. Nalazi se u adresi stranice nakon prijave, pa oznaka (bookmark)
    i poveznice s naslovnice otvaraju aplikaciju bez ponovnog upisivanja lozinke.
    Promjena APP_PASSWORD ponistava sve stare poveznice."""
    return hmac.new(st.secrets["APP_PASSWORD"].encode(), b"zbt-pracenje", hashlib.sha256).hexdigest()[:24]


def check_password():
    kljuc = pristupni_kljuc()
    if st.session_state.get("password_correct") or hmac.compare_digest(st.query_params.get("k", ""), kljuc):
        st.session_state["password_correct"] = True
        if st.query_params.get("k") != kljuc:
            st.query_params["k"] = kljuc  # adresa uvijek nosi kljuc, pa se moze spremiti kao oznaka
        return True
    st.title("Prijava")
    pw = st.text_input("Lozinka", type="password")
    if pw:
        if pw == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.query_params["k"] = kljuc
            st.rerun()
        st.error("Netočna lozinka.")
    return False


def start():
    """Prvi poziv na svakoj stranici: postavke, CSS, kljucevi i prijava."""
    st.set_page_config(page_title="Praćenje vijesti", page_icon="▪", layout="centered")
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    for k in KLJUCEVI:
        if k in st.secrets and not os.environ.get(k):
            os.environ[k] = str(st.secrets[k])
    if not check_password():
        st.stop()


def _fmt_datum(raw):
    d = parse_date(raw)
    return d.strftime("%d.%m.%Y.") if d else (raw or "")


def _kljuc(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]


# ---------- ARHIVA ----------

def arhiva_lista(klijent=None):
    return core.sb_arhiva_lista(klijent)


def arhiva_biljeska(url, tekst):
    core.sb_arhiva_biljeska(url, tekst)


def arhiva_obrisi(url):
    core.sb_arhiva_obrisi(url)


# ---------- PRIKAZ ----------

def prikazi_vijesti(vijesti, klijent, prefix):
    try:
        arhivirani = {a["url"] for a in core.sb_arhiva_lista()}
    except Exception:
        arhivirani = set()

    for v in vijesti:
        zastava = ZASTAVE.get(v.get("zemlja"), "🌍")
        dijelovi = [f"{zastava} {v.get('zemlja', '')}", _fmt_datum(v.get("datum")),
                    v.get("izvor", ""), f"relevantnost {float(v.get('relevantnost', 0)):g}"]
        if v.get("oznaka"):
            dijelovi.append(f"**{v['oznaka']}**")
        meta = "  ·  ".join(d for d in dijelovi if d)
        rok = _fmt_datum(v.get("rok")) if v.get("rok") else ""

        with st.container(border=True):
            st.markdown(f"##### [{v['naslov']}]({v['url']})")
            st.caption(meta)
            if rok:
                st.markdown(f'<span class="zbt-rok">Rok: {rok}</span>', unsafe_allow_html=True)
            st.write(v.get("sazetak") or "Pregledajte članak za detalje.")
            _, c2 = st.columns([5, 1])
            with c2:
                k = f"{prefix}_{_kljuc(v['url'])}"
                if v["url"] in arhivirani:
                    st.button("Arhivirano", key=k, disabled=True)
                elif st.button("Arhiviraj", key=k):
                    core.sb_arhiviraj(v, klijent)
                    st.toast("Spremljeno u arhivu")


@st.cache_data(ttl=timedelta(minutes=10), show_spinner=False)
def _ucitaj(client_key):
    start_d, _ = razdoblje()
    return core.sb_vijesti(client_key, start_d), core.sb_zadnje_osvjezavanje(client_key)


def render_client_page(client_key):
    cfg = CLIENTS[client_key]
    st.title(cfg["naziv"])
    st.caption(f"Zadnja {DANA_UNAZAD} dana · prag relevantnosti {MIN_RELEVANTNOST} · sortirano po relevantnosti")

    try:
        vijesti, zadnje = _ucitaj(client_key)
    except Exception as e:
        st.error(f"Ne mogu učitati vijesti iz baze: {e}")
        return

    if zadnje:
        t = datetime.fromisoformat(zadnje["pokrenuto_at"].replace("Z", "+00:00")).astimezone()
        st.caption(
            f"Zadnje osvježavanje {t:%d.%m.%Y. u %H:%M}  ·  pretraga {zadnje.get('pretrage', 0)}  ·  "
            f"pronađeno {zadnje.get('pronadeno', 0)}  ·  spremljeno {zadnje.get('spremljeno', 0)}"
        )
        if zadnje.get("greske"):
            with st.expander("Greške pri zadnjem osvježavanju"):
                st.code(zadnje["greske"])
    else:
        st.info("Osvježavanje još nije pokrenuto. Pokrenite ga na GitHubu: Actions → Osvjezavanje vijesti → Run workflow.")

    st.divider()
    if not vijesti:
        st.info(f"Nema relevantnih objava u zadnja {DANA_UNAZAD} dana.")
        return
    prikazi_vijesti(vijesti, cfg["naziv"], prefix=client_key)


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def fetch_akteri(akteri):
    """Pretraga na zahtjev (stranica Akteri). Svaka nova kombinacija aktera trosi pretrage."""
    start_d, today = razdoblje()
    vijesti, _ = core.trazi_aktere(list(akteri), start_d, today)
    return {"vijesti": vijesti, "dohvaceno": len(vijesti)}
