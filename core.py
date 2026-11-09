"""Zajednicka logika: prikupljanje vijesti, odabir preko Claudea, provjera i Supabase.

Nacin rada:
1. Prikupljanje (jeftino): Exa pretraga, RSS feedovi medija i institucija, Google News.
2. Predfiltar po kljucnim rijecima (besplatno).
3. Claude (zadano Sonnet) kao urednik: bira relevantno, ocjenjuje, pise sazetke
   i predlaze dodatne upite za drugi krug.
4. Provjera URL-a i datuma.

Koriste je osvjezi.py (GitHub Actions) i Streamlit aplikacija. Kljucevi iz varijabli okruzenja:
ANTHROPIC_API_KEY, EXA_API_KEY, SUPABASE_URL, SUPABASE_KEY, CLAUDE_MODEL (neobavezno).
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree as ET

import anthropic
import requests

# ---------- POSTAVKE ----------

DANA_UNAZAD = 3
MIN_RELEVANTNOST = 2.5

EXA_REZULTATA = 10          # po upitu
MAX_KANDIDATA = 120         # koliko naslova po klijentu ide Claudeu na odabir
DODATNIH_UPITA = 3          # drugi krug: koliko upita Claude smije predložiti

UA = {"User-Agent": "Mozilla/5.0 (compatible; ZBT-pracenje/1.0)"}

BLOKIRANO = [
    "xinhuanet.com", "news.cn", "globaltimes.cn", "chinadaily.com.cn",
    "cgtn.com", "chinamil.com.cn", "people.com.cn", "ecns.cn",
]

ZASTAVE = {"HR": "🇭🇷", "BA": "🇧🇦", "ME": "🇲🇪", "EU": "🇪🇺", "OSTALO": "🌍"}
TLD_ZEMLJA = {".hr": "HR", ".ba": "BA", ".me": "ME"}

INSTITUCIJE_DOMENE = [
    "esavjetovanja.gov.hr", "vlada.gov.hr", "sabor.hr", "narodne-novine.nn.hr",
    "mint.gov.hr", "mfin.gov.hr", "mingo.gov.hr", "mup.gov.hr", "morh.gov.hr",
    "porezna-uprava.gov.hr", "hakom.hr", "hanfa.hr", "hera.hr", "halmed.hr", "aztn.hr",
    "cert.hr", "htz.hr", "zagreb.hr", "split.hr", "rijeka.hr", "dubrovnik.hr",
    "zadar.hr", "pula.hr", "porec.hr", "makarska.hr", "osijek.hr",
]
INSTITUCIJE_UPITI = [
    "javno savjetovanje nacrt zakona pravilnika",
    "sjednica Vlade odluke",
    "javno savjetovanje grad plan upravljanja destinacijom",
]

# (url, izvor, potvrden). Nepotvrdeni su pokusaj: ako ne rade, preskacu se i vide se u logu.
RSS_FEEDOVI = [
    ("https://www.index.hr/rss/vijesti-hrvatska", "index.hr", True),
    ("https://www.index.hr/rss/vijesti-novac", "index.hr", True),
    ("https://www.index.hr/rss/vijesti-eu", "index.hr", True),
    ("https://www.index.hr/rss/vijesti-regija", "index.hr", True),
    ("https://www.vecernji.hr/feeds/latest", "vecernji.hr", True),
    ("https://www.poslovni.hr/feed", "poslovni.hr", True),
    ("https://vlada.gov.hr/RSS?id=8", "vlada.gov.hr", True),
    ("https://vlada.gov.hr/RSS?id=9", "vlada.gov.hr", True),   # sjednice Vlade
    ("https://www.jutarnji.hr/feed", "jutarnji.hr", False),
    ("https://n1info.hr/feed/", "n1info.hr", False),
    ("https://www.tportal.hr/rss", "tportal.hr", False),
    ("https://www.telegram.hr/feed/", "telegram.hr", False),
    ("https://www.netokracija.com/feed", "netokracija.com", False),
    ("https://www.novilist.hr/feed/", "novilist.hr", False),
]

CLIENTS = {
    "airbnb": {
        "naziv": "Airbnb",
        "kontekst": (
            "Kratkoročni (turistički) najam u Hrvatskoj: Airbnb, privatni iznajmljivači, obiteljski smještaj. "
            "Visoko: zakoni i propisi o najmu, paušalni porez i porez na nekretnine, odluke Vlade, ministarstava, "
            "gradova i županija o turističkom najmu, javna savjetovanja o planovima upravljanja destinacijom, "
            "stavovi udruga iznajmljivača, statistika HTZ-a, stambena politika povezana s najmom. "
            "Nisko: opće turističke priče bez veze s najmom."
        ),
        "exa_upiti": [
            "javno savjetovanje plan upravljanja destinacijom grad",
            "odluka grada o ograničenju kratkoročnog najma apartmana",
            "paušalni porez iznajmljivači izmjene zakona",
            "Zakon o upravljanju i održavanju zgrada suglasnost suvlasnika najam",
            "udruga iznajmljivača obiteljski smještaj",
        ],
        "gn_upiti": ["kratkoročni najam", "iznajmljivači paušal", "plan upravljanja destinacijom",
                     "turistički najam zakon", "Airbnb Hrvatska"],
        "kljucne_rijeci": ["najam", "iznajmljiva", "apartman", "airbnb", "smještaj", "paušal", "noćenj",
                           "turizam", "turist", "destinacij"],
    },
    "huawei": {
        "naziv": "Huawei",
        "kontekst": (
            "Huawei i kineska oprema u Hrvatskoj, BiH i Crnoj Gori te odnosi SAD–Kina, EU–Kina, EU–Huawei i Kina–Hrvatska. "
            "Visoko: pregovori o CSA2 (revizija Akta o kibernetičkoj sigurnosti) i NIS2, visokorizični dobavljači, "
            "5G i telekomi, javne nabave s kineskom opremom, kineska ulaganja i diplomacija, stavovi Vlade, Sabora i HAKOM-a. "
            "Nisko: tehnološke vijesti bez veze s regijom ili politikom."
        ),
        "exa_upiti": [
            "EU Cybersecurity Act revision high-risk suppliers Huawei",
            "Huawei Hrvatska",
            "NIS2 provedba Hrvatska kibernetička sigurnost",
            "EU China trade relations",
            "kineska ulaganja Hrvatska",
        ],
        "gn_upiti": ["Huawei", "Kina Hrvatska", "EU Kina", "kibernetička sigurnost NIS2", "5G Hrvatska"],
        "kljucne_rijeci": ["huawei", "kina", "kines", "kinesk", "peking", "5g", "kibernet", "nis2",
                           "telekom", "hakom", "china"],
    },
    "weytec": {
        "naziv": "WEYTEC",
        "kontekst": (
            "WEYTEC, švicarski proizvođač opreme za kontrolne sobe i trgovinske podove (KVM, video zidovi, radna mjesta operatera). "
            "Visoko: javne nabave i investicije u Hrvatskoj, BiH i Crnoj Gori za kontrolne sobe, centre upravljanja, "
            "prometne centre, energetiku (HEP, HOPS), zračni promet (Croatia Control, zračne luke), sigurnosne službe, "
            "obranu i kritičnu infrastrukturu te banke. "
            "Nisko: opće vijesti bez nabave ili investicije."
        ),
        "exa_upiti": [
            "javna nabava centar upravljanja kontrolni centar",
            "nabava video zid kontrolna soba",
            "HOPS HEP investicija centar upravljanja",
            "Croatia Control zračna luka investicija",
            "kritična infrastruktura nabava opreme obrana",
        ],
        "gn_upiti": ["javna nabava centar upravljanja", "HOPS nabava", "Croatia Control",
                     "MORH nabava", "kritična infrastruktura"],
        "kljucne_rijeci": ["nabav", "tender", "kontroln", "centar upravljanja", "hep", "hops", "autocest",
                           "zračn", "morh", "infrastruktur", "croatia control"],
    },
    "envoid": {
        "naziv": "Envoid",
        "kontekst": (
            "Envoid, zaštita mobilnih uređaja za visokorizične organizacije. "
            "Visoko: mobilni spyware i napadi (Pegasus, DarkSword, Coruna) u Hrvatskoj, BiH, Crnoj Gori i EU, "
            "posebno ako se tiču državnih dužnosnika, vojske i diplomacije; NIS2, CSA2, zaštita klasificiranih podataka; "
            "upozorenja CERT.hr, ENISA, ZSIS; nabave zaštite mobitela, MDM i MTD u javnom sektoru. "
            "Nisko: opći tehnološki članci bez veze s javnim sektorom ili regijom."
        ),
        "exa_upiti": [
            "spyware mobile phones government officials Europe",
            "špijunski softver mobitel",
            "CERT.hr upozorenje",
            "NIS2 javni sektor mobilni uređaji",
            "Pegasus spyware investigation EU",
        ],
        "gn_upiti": ["špijunski softver", "Pegasus", "kibernetički napad", "CERT.hr", "hakerski napad mobitel"],
        "kljucne_rijeci": ["spyware", "pegasus", "špijun", "mobitel", "mobiln", "kibernet", "hak", "cert",
                           "nis2", "napad"],
    },
}

ZBT_KONTEKST = (
    "ZBT Consulting je PA i GR agencija u Hrvatskoj, BiH i Crnoj Gori. Prate se akteri (institucije, regulatori, "
    "državna poduzeća, lokalna uprava, udruge) radi javnih politika, nabava i poslovnog razvoja. "
    "Visoko: izjave, odluke, nacrti propisa, javna savjetovanja, nabave i ugovori koje izravno pokreće navedeni akter. "
    "Nisko: samo spominjanje imena bez veze s odlukom, politikom ili nabavom."
)


# ---------- DATUMI ----------

def razdoblje():
    today = date.today()
    return today - timedelta(days=DANA_UNAZAD), today


def parse_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _rss_datum(raw):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError):
        return parse_date(raw)


META_RE = re.compile(
    r'<meta[^>]+(?:property|name|itemprop)=["\']'
    r'(?:article:published_time|og:published_time|datePublished|pubdate|date|DC.date.issued)["\']'
    r'[^>]*content=["\']([^"\']+)["\']',
    re.I,
)
META_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']'
    r'(?:article:published_time|og:published_time|datePublished|pubdate)["\']',
    re.I,
)
JSONLD_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
TIME_RE = re.compile(r'<time[^>]+datetime=["\']([^"\']+)["\']', re.I)
URL_DATUM_RE = [
    re.compile(r'/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:[/-]|$)'),
    re.compile(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)'),
]
MJESECI = {
    "siječnja": 1, "veljače": 2, "ožujka": 3, "travnja": 4, "svibnja": 5, "lipnja": 6,
    "srpnja": 7, "kolovoza": 8, "rujna": 9, "listopada": 10, "studenoga": 11, "studenog": 11, "prosinca": 12,
}
HR_BROJ_RE = re.compile(r'(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(20\d{2})\.?')
HR_RIJEC_RE = re.compile(r'(?<!\d)(\d{1,2})\.\s+(' + "|".join(MJESECI) + r')\s+(20\d{2})', re.I)


def _dt(g, m, d):
    try:
        return date(int(g), int(m), int(d))
    except ValueError:
        return None


def datum_iz_url(url):
    for rx in URL_DATUM_RE:
        m = rx.search(url)
        if m and (d := _dt(*m.groups())):
            return d
    return None


def datum_iz_teksta(html):
    """Prvi datum u tekstu ispod naslova (h1) clanka."""
    i = html.lower().find("<h1")
    if i == -1:
        return None
    tekst = re.sub(r"<[^>]+>", " ", html[i:i + 6000])
    m = HR_BROJ_RE.search(tekst)
    if m:
        return _dt(m.group(3), m.group(2), m.group(1))
    m = HR_RIJEC_RE.search(tekst)
    if m:
        return _dt(m.group(3), MJESECI[m.group(2).lower()], m.group(1))
    return None


def _preuzmi(url, rok_s=15, max_bajtova=400_000):
    """Preuzima stranicu uz strogo ukupno vremensko ogranicenje. None ako nije dostupna."""
    kraj = time.monotonic() + rok_s
    with requests.get(url, timeout=(5, 8), headers=UA, stream=True) as r:
        if r.status_code >= 400:
            return None
        dijelovi, ukupno = [], 0
        for dio in r.iter_content(chunk_size=16_384):
            dijelovi.append(dio)
            ukupno += len(dio)
            if ukupno >= max_bajtova or time.monotonic() > kraj:
                break
        enc = r.encoding or "utf-8"
    return b"".join(dijelovi).decode(enc, errors="replace")


def _datum_sa_stranice(url):
    """Vraca (postoji, datum). postoji=False ako stranica nije dostupna."""
    try:
        html = _preuzmi(url)
        if html is None:
            return False, None
        m = META_RE.search(html) or META_RE2.search(html) or JSONLD_RE.search(html) or TIME_RE.search(html)
        d = parse_date(m.group(1)) if m else None
        return True, d or datum_iz_teksta(html)
    except Exception:
        return False, None


# ---------- POMOĆNE ----------

def _domena(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def _norm_url(url):
    return url.strip().rstrip("/")


def _norm_naslov(t):
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t or "")  # Google News dodaje " - Izvor"
    return re.sub(r"\W+", " ", t.lower()).strip()


def zemlja_iz_url(url):
    host = urlparse(url).netloc.lower()
    for tld, z in TLD_ZEMLJA.items():
        if host.endswith(tld):
            return z
    return None


def _json_iz_teksta(tekst, vrsta="lista"):
    """Izvlaci JSON polje (vrsta='lista') ili objekt (vrsta='objekt') iz odgovora."""
    otv, zat, tip = ("[", "]", list) if vrsta == "lista" else ("{", "}", dict)
    blokovi = re.findall(r"```(?:json)?\s*(.*?)```", tekst or "", re.S)
    for k in list(reversed(blokovi)) + [tekst or ""]:
        a, b = k.find(otv), k.rfind(zat)
        if a != -1 and b > a:
            try:
                data = json.loads(k[a:b + 1])
                if isinstance(data, tip):
                    return data
            except json.JSONDecodeError:
                continue
    return tip()


def _kandidat(url, naslov, izvor, opis="", datum=None, pouzdan=False, porijeklo=""):
    return {"url": url, "naslov": (naslov or url).strip()[:300], "izvor": izvor or _domena(url),
            "opis": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", opis or "")).strip()[:350],
            "datum": datum.isoformat() if datum else "", "pouzdan": pouzdan, "porijeklo": porijeklo}


# ---------- POTROŠNJA ----------

CIJENE = {  # $ po milijunu tokena (ulaz, izlaz), platform.claude.com/docs/about-claude/pricing
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
CIJENA_EXA = 0.005  # gruba procjena po upitu sa sadrzajem
POTROSNJA = {"exa_upiti": 0}


def _zabiljezi(model, usage):
    p = POTROSNJA.setdefault(model, {"ulaz": 0, "izlaz": 0})
    p["ulaz"] += (getattr(usage, "input_tokens", 0) or 0) \
        + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
        + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
    p["izlaz"] += getattr(usage, "output_tokens", 0) or 0


def sazetak_potrosnje():
    redovi, ukupno = [], 0.0
    for model, p in POTROSNJA.items():
        if model == "exa_upiti":
            continue
        ul, iz = CIJENE.get(model, (None, None))
        if ul is None:
            redovi.append(f"{model}: ulaz {p['ulaz']:,} tok, izlaz {p['izlaz']:,} tok (cijena nepoznata)")
            continue
        trosak = p["ulaz"] / 1e6 * ul + p["izlaz"] / 1e6 * iz
        ukupno += trosak
        redovi.append(f"{model}: ulaz {p['ulaz']:,} tok, izlaz {p['izlaz']:,} tok, ~{trosak:.3f} $")
    exa = POTROSNJA["exa_upiti"] * CIJENA_EXA
    ukupno += exa
    redovi.append(f"Exa: {POTROSNJA['exa_upiti']} upita, ~{exa:.3f} $ (iz Exa kredita)")
    redovi.append(f"Procijenjeni trošak pokretanja: ~{ukupno:.3f} $ (dvaput dnevno ~{ukupno * 60:.0f} $ mjesečno)")
    return redovi


# ---------- PRIKUPLJANJE ----------

def _exa():
    from exa_py import Exa  # uvoz tek kad zatreba
    return Exa(api_key=os.environ["EXA_API_KEY"])


def exa_pretraga(upiti, start, institucije=False):
    """Vraca (kandidati, greske)."""
    if not os.environ.get("EXA_API_KEY"):
        return [], ["EXA_API_KEY nije postavljen, Exa preskočena"]
    exa, out, greske = _exa(), [], []
    for q in upiti:
        kw = dict(num_results=EXA_REZULTATA, start_published_date=start.isoformat(),
                  text={"max_characters": 600})
        if institucije:
            kw["include_domains"] = INSTITUCIJE_DOMENE
        else:
            kw["category"] = "news"
            kw["exclude_domains"] = BLOKIRANO
        try:
            try:
                resp = exa.search_and_contents(q, type="auto", **kw)
            except Exception:
                resp = exa.search_and_contents(q, type="neural", **kw)
            POTROSNJA["exa_upiti"] += 1
            for r in resp.results:
                out.append(_kandidat(r.url, r.title, _domena(r.url), getattr(r, "text", "") or "",
                                     porijeklo="Exa institucije" if institucije else "Exa"))
        except Exception as e:
            greske.append(f"Exa '{q[:40]}': {e}")
    return out, greske


def _citaj_rss(url, izvor, start, today, porijeklo):
    r = requests.get(url, timeout=15, headers=UA)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        d = _rss_datum(it.findtext("pubDate"))
        if not link or not d or not (start <= d <= today):
            continue
        izv = izvor
        src = it.find("source")
        naslov = it.findtext("title") or ""
        if src is not None and (src.text or "").strip():
            izv = src.text.strip()  # Google News navodi stvarni izvor
            if naslov.endswith(f" - {izv}"):
                naslov = naslov[: -len(izv) - 3]
        out.append(_kandidat(link, naslov, izv, it.findtext("description") or "",
                             datum=d, pouzdan=True, porijeklo=porijeklo))
    return out


def rss_stavke(start, today):
    """Svi RSS feedovi, jednom za sve klijente. Vraca (kandidati, napomene)."""
    out, napomene = [], []
    for url, izvor, potvrden in RSS_FEEDOVI:
        try:
            st = _citaj_rss(url, izvor, start, today, "RSS")
            out += st
            napomene.append(f"RSS {izvor}: {len(st)} stavki")
        except Exception as e:
            napomene.append(f"RSS {izvor} {'GREŠKA' if potvrden else 'ne radi (preskočeno)'}: {str(e)[:80]}")
    return out, napomene


def google_news(upiti, start, today, dana=DANA_UNAZAD):
    out, greske = [], []
    for q in upiti:
        url = (f"https://news.google.com/rss/search?q={quote_plus(q + f' when:{dana}d')}"
               "&hl=hr&gl=HR&ceid=HR:hr")
        try:
            out += _citaj_rss(url, "Google News", start, today, "Google News")
        except Exception as e:
            greske.append(f"Google News '{q}': {str(e)[:80]}")
    return out, greske


def _izvorni_url(url):
    """Google News poveznicu pokusa pretvoriti u izvornu adresu clanka."""
    if "news.google.com" not in url:
        return url
    try:
        r = requests.get(url, timeout=(5, 8), headers=UA, allow_redirects=True)
        if "news.google.com" not in r.url:
            return r.url
        m = re.search(r'data-n-au="([^"]+)"', r.text) or re.search(r'<a[^>]+href="(https?://(?!news\.google)[^"]+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return url


def filtriraj(kandidati, kljucne):
    kw = [k.lower() for k in kljucne]
    return [k for k in kandidati if any(w in f"{k['naslov']} {k['opis']}".lower() for w in kw)]


def spoji_kandidate(*liste):
    """Uklanja duplikate po URL-u i po naslovu (isti clanak iz vise izvora)."""
    po_url, po_naslovu, out = set(), set(), []
    for lista in liste:
        for k in lista:
            u, n = _norm_url(k["url"]), _norm_naslov(k["naslov"])
            if u in po_url or (n and n in po_naslovu):
                continue
            po_url.add(u)
            if n:
                po_naslovu.add(n)
            out.append(k)
    return out


# ---------- CLAUDE KAO UREDNIK ----------

def _client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _model():
    return os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"


def claude_poziv(prompt, max_tokens=6000):
    model = _model()
    resp = _client().messages.create(model=model, max_tokens=max_tokens,
                                     messages=[{"role": "user", "content": prompt}])
    _zabiljezi(model, resp.usage)
    return "\n".join(b.text for b in resp.content if b.type == "text")


def urednik(naziv, kontekst, kandidati, start, today, trazi_upite=True):
    """Claude bira i ocjenjuje. Vraca (odabrani, dodatni_upiti)."""
    if not kandidati:
        return [], []
    popis = "\n".join(
        f"{i}. [{k['izvor']} | {k['datum'] or 'datum ?'}] {k['naslov']}" + (f" — {k['opis']}" if k["opis"] else "")
        for i, k in enumerate(kandidati)
    )
    upiti_dio = (
        f'\n"dodatni_upiti": do {DODATNIH_UPITA} kratka upita na hrvatskom ili engleskom za drugi krug pretrage: '
        "konkretni zakoni, institucije, osobe, projekti ili nabave iz odabranih stavki o kojima vrijedi potražiti "
        "nastavak, reakcije ili službene dokumente. Ako nema smisla, vrati [].\n"
        if trazi_upite else ""
    )
    prompt = f"""Danas je {today:%d.%m.%Y.} Ti si urednik praćenja vijesti za PA i GR agenciju ZBT Consulting.

KLIJENT: {naziv}
KONTEKST: {kontekst}
RAZDOBLJE: od {start:%d.%m.%Y.} do {today:%d.%m.%Y.}

Ispod su prikupljene stavke (broj. [izvor | datum] naslov — isječak). Odaberi one koje su relevantne za klijenta.
- Izostavi stavke koje su očito starije od razdoblja, sport, crnu kroniku, oglase i sadržaj bez veze s klijentom.
- Izostavi trajne stranice (početne stranice, popise, tekstove zakona, profile tvrtki) osim ako je riječ o novom savjetovanju ili nabavi.
- Ako je isti događaj više puta, odaberi jednu, najinformativniju stavku.
- Ne koristi kineske državne medije.

STAVKE:
{popis}

Odgovori ISKLJUČIVO JSON objektom:
{{"stavke": [{{"i": broj, "relevantnost": 1-5 (može decimala), "zemlja": "HR|BA|ME|EU|OSTALO",
  "oznaka": "Nabava|Javno savjetovanje|Sjednica Vlade|Sabor|Propis|", "rok": "YYYY-MM-DD ili prazno",
  "sazetak": "2 rečenice na hrvatskom: što se dogodilo i zašto je važno za klijenta"}}],
 "dodatni_upiti": []}}
Uključi samo stavke s relevantnošću 2.5 ili više. 5 ključno, 4 izravno relevantno, 3 relevantno, 2 površno, 1 nema veze.{upiti_dio}"""
    data = _json_iz_teksta(claude_poziv(prompt), "objekt")
    odabrani = []
    for d in data.get("stavke", []):
        try:
            k = kandidati[int(d.get("i"))]
            score = max(1.0, min(5.0, float(d.get("relevantnost", 0))))
        except (TypeError, ValueError, IndexError):
            continue
        zemlja = str(d.get("zemlja", "OSTALO")).upper()
        odabrani.append({
            **k,
            "relevantnost": score,
            "zemlja": zemlja_iz_url(k["url"]) or (zemlja if zemlja in ZASTAVE else "OSTALO"),
            "oznaka": str(d.get("oznaka") or "").strip(),
            "rok": str(d.get("rok") or "").strip(),
            "sazetak": str(d.get("sazetak") or "").strip(),
        })
    upiti = [str(u).strip() for u in data.get("dodatni_upiti", []) if str(u).strip()][:DODATNIH_UPITA]
    return odabrani, upiti


# ---------- PROVJERA ----------

def _provjeri(s, start, today):
    """Vraca (stavka, None) ili (None, razlog)."""
    s = {**s, "url": _izvorni_url(s["url"])}
    if s.get("pouzdan") and parse_date(s["datum"]):
        d = parse_date(s["datum"])  # RSS i Google News daju pouzdan datum objave
    else:
        postoji, d_stranica = _datum_sa_stranice(s["url"])
        if not postoji:
            return None, "stranica nedostupna"
        d = d_stranica or datum_iz_url(s["url"])
        if not d:
            rok = parse_date(s.get("rok"))
            if "savjetovanj" in s.get("oznaka", "").lower() and rok and today <= rok <= today + timedelta(days=90):
                return {**s, "datum": today.isoformat()}, None  # otvoreno savjetovanje: vazan je rok
            return None, "bez datuma"
    if d < start or d > today:
        return None, f"datum {d:%d.%m.%Y.}"
    if not s.get("izvor"):
        s["izvor"] = _domena(s["url"])
    return {**s, "datum": d.isoformat()}, None


def provjeri_sve(stavke, start, today, odbaceno=None):
    with ThreadPoolExecutor(max_workers=8) as ex:
        rez = list(ex.map(lambda s: _provjeri(s, start, today), stavke))
    if odbaceno is not None:
        for s, (_, razlog) in zip(stavke, rez):
            if razlog:
                odbaceno.append(f"{razlog}: {s['url']}")
    return [r for r, _ in rez if r]


def spoji(*liste):
    out = {}
    for lista in liste:
        for s in lista:
            k = _norm_url(s["url"])
            if k not in out or s["relevantnost"] > out[k]["relevantnost"]:
                out[k] = s
    return list(out.values())


# ---------- OBRADA ----------

def zajednicki_izvori(start, today):
    """Jednom po pokretanju: RSS i Exa pretraga institucija. Vraca (kandidati, napomene)."""
    rss, napomene = rss_stavke(start, today)
    inst, greske = exa_pretraga(INSTITUCIJE_UPITI, start, institucije=True)
    napomene.append(f"Exa institucije: {len(inst)} stavki")
    return rss + inst, napomene + greske


def obradi_klijenta(key, start, today, zajednicki):
    cfg = CLIENTS[key]
    greske = []

    exa1, g = exa_pretraga(cfg["exa_upiti"], start)
    greske += g
    gn1, g = google_news(cfg["gn_upiti"], start, today)
    greske += g
    rss = [k for k in zajednicki if k["porijeklo"] == "RSS"]
    vlada = [k for k in rss if k["izvor"] == "vlada.gov.hr"]  # Vladine objave uvijek idu uredniku
    zaj = vlada + filtriraj([k for k in rss if k["izvor"] != "vlada.gov.hr"], cfg["kljucne_rijeci"])
    inst = [k for k in zajednicki if k["porijeklo"] == "Exa institucije"]
    # Izravni izvori prvi: kod duplikata po naslovu zadrzava se izravna poveznica, ne Googleova.
    kandidati = spoji_kandidate(zaj, inst, exa1, gn1)[:MAX_KANDIDATA]

    odabrani1, dodatni = urednik(cfg["naziv"], cfg["kontekst"], kandidati, start, today)

    # Drugi krug: upiti koje je predložio urednik
    odabrani2, n2 = [], 0
    if dodatni:
        try:
            exa2, g = exa_pretraga(dodatni, start)
            greske += g
            gn2, g = google_news(dodatni, start, today)
            greske += g
            # duplikati po adresi i po naslovu u odnosu na prvi krug
            novi = spoji_kandidate(kandidati, exa2, gn2)[len(kandidati):][:60]
            n2 = len(novi)
            odabrani2, _ = urednik(cfg["naziv"], cfg["kontekst"], novi, start, today, trazi_upite=False)
        except Exception as e:
            greske.append(f"drugi krug: {e}")

    odabrani = spoji(odabrani1, odabrani2)
    odbaceno = []
    prosle = provjeri_sve(odabrani, start, today, odbaceno)
    provjerene = [s for s in prosle if s["relevantnost"] >= MIN_RELEVANTNOST]
    stats = {
        "pronadeno": len(kandidati) + n2, "spremljeno": len(provjerene), "pretrage": 0,
        "koraci": (f"kandidati: Exa {len(exa1)}, Google News {len(gn1)}, RSS {len(zaj)}, institucije {len(inst)} "
                   f"→ urednik odabrao {len(odabrani1)} | drugi krug: upiti {dodatni}, novih kandidata {n2}, "
                   f"odabrano {len(odabrani2)} | odbačeno provjerom {len(odbaceno)}"),
        "odbaceno": odbaceno, "napomene": [],
    }
    return provjerene, stats, greske


def trazi_aktere(akteri, start, today):
    exa, _ = exa_pretraga(list(akteri), start)
    gn, _ = google_news(list(akteri), start, today)
    kandidati = spoji_kandidate(exa, gn)[:MAX_KANDIDATA]
    kontekst = ZBT_KONTEKST + f" AKTERI: {', '.join(akteri)}."
    odabrani, _ = urednik("ZBT (akteri)", kontekst, kandidati, start, today, trazi_upite=False)
    provjerene = [s for s in provjeri_sve(odabrani, start, today) if s["relevantnost"] >= MIN_RELEVANTNOST]
    provjerene.sort(key=lambda s: (s["relevantnost"], s["datum"]), reverse=True)
    return provjerene, len(kandidati)


# ---------- SUPABASE ----------

def _sb(path):
    return f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/{path}"


def _sb_h(extra=None):
    key = os.environ["SUPABASE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def sb_spremi_vijesti(key, stavke):
    if not stavke:
        return
    redovi = [{
        "klijent": key, "url": s["url"], "naslov": s["naslov"], "izvor": s["izvor"],
        "datum": s["datum"], "zemlja": s["zemlja"], "relevantnost": s["relevantnost"],
        "oznaka": s["oznaka"], "rok": s["rok"], "sazetak": s["sazetak"], "krug": s.get("porijeklo", ""),
        "azurirano_at": datetime.now(timezone.utc).isoformat(),
    } for s in stavke]
    r = requests.post(_sb("vijesti?on_conflict=klijent,url"), json=redovi, timeout=20,
                      headers=_sb_h({"Prefer": "resolution=merge-duplicates"}))
    r.raise_for_status()


def sb_log(key, stats, greske):
    body = {"klijent": key, "pretrage": stats.get("pretrage", 0), "pronadeno": stats.get("pronadeno", 0),
            "spremljeno": stats.get("spremljeno", 0), "greske": "\n".join(greske)[:4000]}
    requests.post(_sb("osvjezavanja"), json=body, headers=_sb_h(), timeout=15).raise_for_status()


def sb_ocisti(dana=14):
    granica = (date.today() - timedelta(days=dana)).isoformat()
    requests.delete(_sb(f"vijesti?datum=lt.{granica}"), headers=_sb_h(), timeout=15).raise_for_status()


def sb_vijesti(key, start):
    params = {"select": "*", "klijent": f"eq.{key}", "datum": f"gte.{start.isoformat()}",
              "relevantnost": f"gte.{MIN_RELEVANTNOST}", "order": "relevantnost.desc,datum.desc"}
    r = requests.get(_sb("vijesti"), headers=_sb_h(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def sb_zadnje_osvjezavanje(key):
    params = {"select": "*", "klijent": f"eq.{key}", "order": "pokrenuto_at.desc", "limit": "1"}
    r = requests.get(_sb("osvjezavanja"), headers=_sb_h(), params=params, timeout=15)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def sb_arhiviraj(s, klijent):
    d = parse_date(s.get("datum"))
    body = {
        "url": s["url"], "klijent": klijent, "naslov": s["naslov"], "izvor": s["izvor"],
        "datum": d.strftime("%d.%m.%Y.") if d else s.get("datum", ""),
        "relevantnost": s["relevantnost"], "zemlja": s["zemlja"], "oznaka": s.get("oznaka", ""),
        "sazetak": s.get("sazetak", ""), "biljeska": "",
    }
    requests.post(_sb("arhiva"), json=body, timeout=15,
                  headers=_sb_h({"Prefer": "resolution=merge-duplicates"})).raise_for_status()


def sb_arhiva_lista(klijent=None):
    params = {"select": "*", "order": "arhivirano_at.desc"}
    if klijent:
        params["klijent"] = f"eq.{klijent}"
    r = requests.get(_sb("arhiva"), headers=_sb_h(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def sb_arhiva_biljeska(url, tekst):
    requests.patch(_sb("arhiva"), headers=_sb_h(), params={"url": f"eq.{url}"},
                   json={"biljeska": tekst}, timeout=15).raise_for_status()


def sb_arhiva_obrisi(url):
    requests.delete(_sb("arhiva"), headers=_sb_h(), params={"url": f"eq.{url}"}, timeout=15).raise_for_status()
