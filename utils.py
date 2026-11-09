import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import requests
import streamlit as st
from exa_py import Exa
from openai import OpenAI

DANA_UNAZAD = 3
MIN_RELEVANTNOST = 2.5
PARALELNO = 8

ISKLJUCENI_IZVORI = [
    "xinhuanet.com", "news.cn", "english.news.cn", "globaltimes.cn",
    "chinadaily.com.cn", "cgtn.com", "chinamil.com.cn", "people.com.cn", "ecns.cn",
]

ZASTAVE = {"HR": "🇭🇷", "BA": "🇧🇦", "ME": "🇲🇪", "EU": "🇪🇺", "OSTALO": "🌍"}
TLD_ZEMLJA = {".hr": "HR", ".ba": "BA", ".me": "ME"}

CLIENTS = {
    "airbnb": {
        "naziv": "Airbnb",
        "kontekst": (
            "Tim prati kratkoročni (turistički) najam u Hrvatskoj: Airbnb, privatne iznajmljivače, "
            "obiteljski smještaj. Visoka relevantnost: zakoni i propisi o najmu, porezi i paušali za "
            "iznajmljivače, odluke vlada, ministarstava, gradova i županija o turističkom najmu, "
            "javna savjetovanja o planovima upravljanja destinacijom i turizmom, stavovi udruga "
            "iznajmljivača, statistika HTZ-a o smještaju i noćenjima, stambena politika povezana s najmom. "
            "Niska relevantnost: opće turističke priče bez veze s najmom."
        ),
        "upiti": [
            "savjetovanje o planu upravljanja turizmom i destinacijom lokalna zajednica",
            "plan upravljanja destinacijom javno savjetovanje grad županija turizam",
            "kratkoročni najam apartmani zabrana ograničenje odluka grada",
            "zakon o turističkom najmu izmjene Hrvatska iznajmljivači paušalni porez",
            "zakon o upravljanju i održavanju zgrada suglasnost suvlasnika kratkoročni najam",
            "Hrvatska udruga obiteljskog smještaja iznajmljivači Airbnb",
            "Ministarstvo turizma i sporta kratkoročni najam propisi",
            "HTZ statistika dolasci noćenja smještaj Hrvatska",
        ],
        "akteri": [
            "Tonči Glavina", "Ministarstvo turizma i sporta",
            "Hrvatska turistička zajednica", "Hrvatska udruga obiteljskog smještaja",
        ],
    },
    "huawei": {
        "naziv": "Huawei",
        "kontekst": (
            "Tim prati Huawei i kinesku opremu u Hrvatskoj, BiH i Crnoj Gori, te geopolitiku između "
            "SAD-a, EU-a i Kine. Visoka relevantnost: pregovori o CSA2 (Akt o kibernetičkoj sigurnosti) "
            "i NIS2, zahtjevi za visokorizične dobavljače, javne nabave u kojima se spominje Huawei ili "
            "kineska oprema, odnos SAD–Kina, EU–Kina, EU–Huawei i Kina–Hrvatska (ulaganja, diplomacija, "
            "posjeti), stavovi Sabora, Vlade i ministarstava o toj temi. "
            "Niska relevantnost: tehnološke vijesti bez veze s Hrvatskom, regijom ili politikom."
        ),
        "upiti": [
            "CSA2 Akt o kibernetičkoj sigurnosti Hrvatska pregovori visokorizični dobavljači",
            "NIS2 zakon o kibernetičkoj sigurnosti Hrvatska Sabor",
            "Huawei Hrvatska",
            "Huawei 5G oprema Hrvatska nabava telekomunikacije",
            "SAD Kina odnos EU Kina Hrvatska",
            "EU Huawei visokorizični dobavljači 5G zabrana",
            "kineska ulaganja u Hrvatsku diplomacija",
            "javna nabava kineska oprema državna infrastruktura Hrvatska",
        ],
        "akteri": ["Huawei", "Hrvatski sabor", "CARNET", "Hrvatska regulatorna agencija HAKOM"],
    },
    "weytec": {
        "naziv": "WEYTEC",
        "kontekst": (
            "Tim prati tržište za WEYTEC, švicarskog proizvođača opreme za kontrolne sobe i trgovinske "
            "podove (smartTOUCH, smartVISUAL, WDP MX, KVM). Visoka relevantnost: javne nabave u Hrvatskoj, "
            "BiH i Crnoj Gori za kontrolne sobe, centre upravljanja, prometne centre, energetiku, zračni promet, "
            "sigurnosne službe i banke; tehnički natječaji za video zidove, KVM, radna mjesta; projekti u regiji "
            "(NEK, DARS, ELES, EMS, DEM, Gastrans). "
            "Niska relevantnost: opće vijesti o kontrolnim sobama bez nabave ili investicije."
        ),
        "upiti": [
            "javna nabava kontrolne sobe centar upravljanja Hrvatska",
            "tender video zid kontrolna soba nabava",
            "javna nabava kontrolni centar HAC HŽ HEP HOPS nabava opreme",
            "javna nabava zračna luka kontrola zračnog prometa oprema Hrvatska",
            "nabava sigurnosni centar MUP MORH kontrolna soba",
            "javna nabava kontrolna soba Bosna i Hercegovina tender",
            "javna nabava kontrolna soba Crna Gora tender",
            "DARS ELES NEK Gastrans nabava sustav upravljanja",
        ],
        "akteri": ["HAC Hrvatske autoceste", "HEP", "Croatia Control", "HŽ Infrastruktura", "DARS", "ELES"],
    },
    "envoid": {
        "naziv": "Envoid",
        "kontekst": (
            "Tim prati tržište za Envoid, zaštitu mobilnih uređaja za visokorizične organizacije. "
            "Visoka relevantnost: mobilni spyware i napadi (Pegasus, DarkSword, Coruna) u Hrvatskoj, BiH, "
            "Crnoj Gori i EU, posebno ako se tiču državnih službenika, vojske, diplomacije; regulativa "
            "(NIS2, CSA2, zaštita klasificiranih podataka); upozorenja CERT.hr, ENISA, ZSIS; javne nabave "
            "i tenderi za zaštitu mobitela, MDM i MTD rješenja u javnom sektoru (MUP, MORH, ministarstva, "
            "sudovi, državna poduzeća). "
            "Niska relevantnost: opći tehnološki članci bez veze s javnim sektorom ili Hrvatskom."
        ),
        "upiti": [
            "Pegasus spyware Hrvatska mobilni telefoni državni službenici",
            "špijunski softver mobiteli napad Hrvatska",
            "mobilna sigurnost MDM zaštita mobitela državna tijela nabava",
            "NIS2 mobilni uređaji zaštita institucija Hrvatska",
            "CERT.hr upozorenje mobilni uređaji napad",
            "ZSIS zaštita klasificiranih podataka mobiteli",
            "javna nabava zaštita mobilnih uređaja ministarstvo MORH MUP",
            "mobile spyware zero-click iOS Android ranjivost",
        ],
        "akteri": ["CERT.hr", "ZSIS", "ENISA", "MORH", "MUP"],
    },
}

CSS = """
#MainMenu, footer {visibility: hidden;}
html, body, [class*="css"] {font-family: "Segoe UI", "Source Sans Pro", Helvetica, Arial, sans-serif;}
.block-container {max-width: 900px; padding-top: 2.5rem; padding-bottom: 3rem;}
h1 {font-weight: 600; letter-spacing: -0.02em; color: #1B2A41;}
h5 {margin-top: 0.2rem; margin-bottom: 0.3rem;}
h5 a {color: #1B2A41; text-decoration: none; font-weight: 600;}
h5 a:hover {color: #1F5F8B; text-decoration: underline;}
a {color: #1F5F8B;}
[data-testid="stCaptionContainer"] {color: #6B7280;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 10px; border-color: #E5E7EB;}
button[kind="secondary"] {border-radius: 8px;}
hr {margin: 1rem 0; border-color: #E5E7EB;}
"""

META_RE = re.compile(
    r'<meta[^>]+(?:property|name|itemprop)=["\']'
    r'(?:article:published_time|og:published_time|datePublished|pubdate|date)["\']'
    r'[^>]*content=["\']([^"\']+)["\']',
    re.I,
)
HR_DATUM_RE = re.compile(r'\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\.?')


def check_password():
    if st.session_state.get("password_correct"):
        return True
    st.title("Prijava")
    pw = st.text_input("Lozinka", type="password")
    if pw:
        if pw == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        st.error("Netočna lozinka.")
    return False


def start():
    """Postavlja stranicu, CSS i prijavu. Mora biti prvi poziv na svakoj stranici."""
    st.set_page_config(page_title="Praćenje vijesti", page_icon="▪", layout="centered")
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    if not check_password():
        st.stop()


@st.cache_resource
def get_clients():
    return (
        Exa(api_key=st.secrets["EXA_API_KEY"]),
        OpenAI(api_key=st.secrets["OPENAI_API_KEY"]),
    )


def parse_date(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def zemlja_iz_url(url):
    host = urlparse(url).netloc.lower()
    for tld, zemlja in TLD_ZEMLJA.items():
        if host.endswith(tld):
            return zemlja
    return None


def stvarni_datum(url, text):
    """Datum čita sa stranice (meta oznake), pa iz teksta (dd.mm.yyyy.)."""
    try:
        html = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}).text
        m = META_RE.search(html)
        if m:
            d = parse_date(m.group(1))
            if d:
                return d
    except Exception:
        pass
    m = HR_DATUM_RE.search((text or "")[:1500])
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def ai_ocjena(oai, model, kontekst, title, text):
    today = date.today()
    cutoff = today - timedelta(days=DANA_UNAZAD)
    prompt = f"""Ocijeni vijest za praćenje klijenta.

DANAŠNJI DATUM: {today:%d.%m.%Y.}
Ako je vijest starija od {cutoff:%d.%m.%Y.} ili se ne može datirati, ocijeni s 1.

KONTEKST KLIJENTA:
{kontekst}

PRAVILA:
- relevantnost: broj od 1 do 5, može s decimalom (npr. 2.5).
  5 = ključno, 4 = izravno relevantno, 3 = relevantno, 2 = površno povezano, 1 = nema veze.
- Oglasi za nekretnine, sadržaj agencija, sport i crna kronika: 1.
- Vijesti iz izvora koji nisu hrvatski, bosanski ni crnogorski: 1, osim ako se tiču HR, BA, ME ili EU politike relevantne za klijenta.
- zemlja: država o kojoj vijest govori. Dopušteno: HR, BA, ME, EU, OSTALO.
- oznaka: "Nabava" za javne nabave i tendere, "Javno savjetovanje" za javna savjetovanja, inače prazan niz.

Odgovori isključivo JSON objektom:
{{"relevantnost": <broj>, "zemlja": "<HR|BA|ME|EU|OSTALO>", "oznaka": "<tekst>", "sazetak": "<2 rečenice na hrvatskom>"}}

Naslov: {title}
Sadržaj: {text[:3000]}"""

    response = oai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Ti si analitičar vijesti. Odgovaraš isključivo JSON-om."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=250,
        temperature=0,
    )
    data = json.loads(response.choices[0].message.content)
    score = max(1.0, min(5.0, float(data.get("relevantnost", 1))))
    zemlja = str(data.get("zemlja", "OSTALO")).upper()
    if zemlja not in ZASTAVE:
        zemlja = "OSTALO"
    return score, data.get("oznaka", "").strip(), zemlja, data.get("sazetak", "").strip()


def _obradi(url, item, oai, model, kontekst, start, today):
    pub = stvarni_datum(url, item.text)
    if not pub or pub < start or pub > today or not item.text:
        return "datum", None
    try:
        score, oznaka, zemlja, sazetak = ai_ocjena(oai, model, kontekst, item.title, item.text)
    except Exception as e:
        return "greska", f"OpenAI, {url}: {e}"
    if score < MIN_RELEVANTNOST:
        return "relevantnost", None
    return "ok", {
        "title": item.title or url,
        "url": url,
        "source": urlparse(url).netloc.replace("www.", ""),
        "date": pub.strftime("%d.%m.%Y."),
        "sort_date": pub.isoformat(),
        "relevantnost": score,
        "oznaka": oznaka,
        "zemlja": zemlja_iz_url(url) or zemlja,
        "summary": sazetak or "Pregledajte članak za detalje.",
    }


def _pipeline(kontekst, upiti):
    exa, oai = get_clients()
    model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
    start = (datetime.now() - timedelta(days=DANA_UNAZAD)).date()
    today = date.today()

    greske, rezultati = [], {}
    for q in upiti:
        try:
            resp = exa.search_and_contents(
                q,
                type="auto",
                category="news",
                num_results=10,
                start_published_date=start.isoformat(),
                exclude_domains=ISKLJUCENI_IZVORI,
                text={"max_characters": 3000},
            )
            for r in resp.results:
                rezultati.setdefault(r.url, r)
        except Exception as e:
            greske.append(f"Exa, upit '{q[:45]}…': {e}")

    stats = {"dohvaceno": len(rezultati), "datum": 0, "relevantnost": 0}
    vijesti = []
    with ThreadPoolExecutor(max_workers=PARALELNO) as ex:
        futures = [
            ex.submit(_obradi, url, item, oai, model, kontekst, start, today)
            for url, item in rezultati.items()
        ]
        for f in futures:
            status, payload = f.result()
            if status == "ok":
                vijesti.append(payload)
            elif status == "datum":
                stats["datum"] += 1
            elif status == "relevantnost":
                stats["relevantnost"] += 1
            elif status == "greska":
                greske.append(payload)

    # Prvo po relevantnosti, pa unutar istog ranga po datumu (najnovije prvo)
    vijesti.sort(key=lambda v: (v["relevantnost"], v["sort_date"]), reverse=True)
    return {"vijesti": vijesti, "greske": greske, **stats}


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def fetch_news(client_key):
    cfg = CLIENTS[client_key]
    return _pipeline(cfg["kontekst"], tuple(cfg["upiti"]))


ZBT_KONTEKST = (
    "Tim je PA i GR agencija ZBT Consulting u Hrvatskoj, BiH i Crnoj Gori. Pratimo aktere "
    "(institucije, regulatore, državna poduzeća, lokalnu upravu, udruge) radi javnih politika, "
    "nabava i poslovnog razvoja. Visoka relevantnost: izjave, odluke, nacrti propisa, javna "
    "savjetovanja, nabave i ugovori koje izravno pokreće ili potpisuje navedeni akter. "
    "Niska relevantnost: samo spominjanje imena bez veze s odlukom, javnom politikom ili nabavom."
)


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def fetch_akteri(akteri):
    upiti = tuple(f"{a} izjava odluka nabava savjetovanje" for a in akteri)
    return _pipeline(ZBT_KONTEKST, upiti)


# ---------- ARHIVA (Supabase) ----------

def _sb_url():
    return f"{st.secrets['SUPABASE_URL']}/rest/v1/arhiva"


def _sb_headers():
    key = st.secrets["SUPABASE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def arhiviraj(v, klijent):
    body = {
        "url": v["url"], "klijent": klijent, "naslov": v["title"], "izvor": v["source"],
        "datum": v["date"], "relevantnost": v["relevantnost"], "zemlja": v["zemlja"],
        "oznaka": v["oznaka"], "sazetak": v["summary"], "biljeska": "",
    }
    r = requests.post(
        _sb_url(),
        headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates"},
        json=body, timeout=10,
    )
    r.raise_for_status()


def arhiva_lista(klijent=None):
    params = {"select": "*", "order": "arhivirano_at.desc"}
    if klijent:
        params["klijent"] = f"eq.{klijent}"
    r = requests.get(_sb_url(), headers=_sb_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def arhiva_urls():
    return {a["url"] for a in arhiva_lista()}


def arhiva_biljeska(url, tekst):
    r = requests.patch(_sb_url(), headers=_sb_headers(),
                       params={"url": f"eq.{url}"}, json={"biljeska": tekst}, timeout=10)
    r.raise_for_status()


def arhiva_obrisi(url):
    r = requests.delete(_sb_url(), headers=_sb_headers(), params={"url": f"eq.{url}"}, timeout=10)
    r.raise_for_status()


# ---------- PRIKAZ ----------

def _kljuc(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]


def prikazi_vijesti(vijesti, klijent, prefix):
    arhivirani = arhiva_urls()
    for v in vijesti:
        zastava = ZASTAVE.get(v["zemlja"], "🌍")
        meta = f"{zastava} {v['zemlja']}  ·  {v['date']}  ·  {v['source']}  ·  relevantnost {v['relevantnost']}"
        if v["oznaka"]:
            meta += f"  ·  {v['oznaka']}"

        with st.container(border=True):
            st.markdown(f"##### [{v['title']}]({v['url']})")
            st.caption(meta)
            st.write(v["summary"])
            c1, c2 = st.columns([5, 1])
            with c2:
                if v["url"] in arhivirani:
                    st.button("Arhivirano", key=f"{prefix}_{_kljuc(v['url'])}", disabled=True)
                elif st.button("Arhiviraj", key=f"{prefix}_{_kljuc(v['url'])}"):
                    arhiviraj(v, klijent)
                    st.toast("Spremljeno u arhivu")


def render_client_page(client_key):
    cfg = CLIENTS[client_key]
    st.title(cfg["naziv"])
    st.caption(f"Zadnja {DANA_UNAZAD} dana · prag relevantnosti {MIN_RELEVANTNOST} · sortirano po relevantnosti")

    with st.spinner("Pretražujem izvore…"):
        r = fetch_news(client_key)

    st.caption(
        f"Dohvaćeno {r['dohvaceno']}  ·  izbačeno (datum) {r['datum']}  ·  "
        f"izbačeno (relevantnost) {r['relevantnost']}  ·  prikazano {len(r['vijesti'])}"
    )
    if st.button("Osvježi"):
        fetch_news.clear()
        st.rerun()

    if r["greske"]:
        with st.expander(f"Greške pri dohvaćanju ({len(r['greske'])})"):
            for g in r["greske"][:30]:
                st.code(g)

    st.divider()
    if not r["vijesti"]:
        st.info(f"Nema relevantnih objava u zadnja {DANA_UNAZAD} dana.")
        return
    prikazi_vijesti(r["vijesti"], cfg["naziv"], prefix=client_key)
