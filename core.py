"""Zajednicka logika: pretraga preko Claude API-ja, provjera stavki i Supabase.

Koriste je osvjezi.py (GitHub Actions, dvaput dnevno) i Streamlit aplikacija.
Kljucevi se citaju iz varijabli okruzenja:
ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY, CLAUDE_MODEL (neobavezno).
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import anthropic
import requests

# ---------- POSTAVKE ----------

DANA_UNAZAD = 3
MIN_RELEVANTNOST = 2.5

# Limiti pretraga po jednom pokretanju. Svaka pretraga stoji oko 0,01 $ plus tokeni.
PRETRAGE_KRUG1 = 5          # po klijentu
PRETRAGE_KRUG2 = 3          # po klijentu
PRETRAGE_INSTITUCIJE = 6    # jednom za sve klijente
DOHVACANJA_INSTITUCIJE = 8  # otvaranje stranica, bez naknade po pozivu (samo tokeni)
PRETRAGE_AKTERI = 4         # po upitu na stranici Akteri

WEB_SEARCH = "web_search_20250305"
WEB_FETCH = "web_fetch_20250910"
FETCH_BETA = "web-fetch-2025-09-10"

UA = {"User-Agent": "Mozilla/5.0 (compatible; ZBT-pracenje/1.0)"}
USER_LOCATION = {"type": "approximate", "city": "Zagreb", "country": "HR", "timezone": "Europe/Zagreb"}

BLOKIRANO = [
    "xinhuanet.com", "news.cn", "globaltimes.cn", "chinadaily.com.cn",
    "cgtn.com", "chinamil.com.cn", "people.com.cn", "ecns.cn",
]

ZASTAVE = {"HR": "🇭🇷", "BA": "🇧🇦", "ME": "🇲🇪", "EU": "🇪🇺", "OSTALO": "🌍"}
TLD_ZEMLJA = {".hr": "HR", ".ba": "BA", ".me": "ME"}

INSTITUCIJE_DOMENE = [
    "esavjetovanja.gov.hr", "savjetovanja.gov.hr", "vlada.gov.hr", "sabor.hr",
    "narodne-novine.nn.hr", "eojn.nn.hr", "mint.gov.hr", "mfin.gov.hr", "mingo.gov.hr",
    "mup.gov.hr", "morh.gov.hr", "porezna-uprava.gov.hr", "hakom.hr", "hanfa.hr",
    "hera.hr", "halmed.hr", "aztn.hr", "cert.hr", "htz.hr",
    "zagreb.hr", "split.hr", "rijeka.hr", "dubrovnik.hr", "zadar.hr", "pula.hr",
    "porec.hr", "rovinj-rovigno.hr", "makarska.hr", "osijek.hr",
]
INSTITUCIJE_POCETNE = [
    "https://esavjetovanja.gov.hr",
    "https://vlada.gov.hr",
    "https://www.sabor.hr",
    "https://narodne-novine.nn.hr",
]

RSS_FEEDOVI = [
    "https://www.index.hr/rss/vijesti-hrvatska",
    "https://www.index.hr/rss/vijesti-novac",
    "https://www.index.hr/rss/vijesti-eu",
    "https://www.index.hr/rss/vijesti-regija",
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
        "smjernice": [
            "javna savjetovanja o planovima upravljanja destinacijom u gradovima i županijama",
            "odluke gradova o ograničenju kratkoročnog najma",
            "izmjene Zakona o ugostiteljskoj djelatnosti i paušalnog poreza",
            "Zakon o upravljanju i održavanju zgrada i suglasnost suvlasnika za najam",
            "udruge iznajmljivača i HTZ statistika",
        ],
        "kljucne_rijeci": ["najam", "iznajmljiva", "apartman", "airbnb", "smještaj", "paušal", "noćenj", "turizam", "turist"],
    },
    "huawei": {
        "naziv": "Huawei",
        "kontekst": (
            "Huawei i kineska oprema u Hrvatskoj, BiH i Crnoj Gori te odnosi SAD–Kina, EU–Kina, EU–Huawei i Kina–Hrvatska. "
            "Visoko: pregovori o CSA2 (revizija Akta o kibernetičkoj sigurnosti) i NIS2, visokorizični dobavljači, "
            "5G i telekomi, javne nabave s kineskom opremom, kineska ulaganja i diplomacija, stavovi Vlade, Sabora i HAKOM-a. "
            "Nisko: tehnološke vijesti bez veze s regijom ili politikom."
        ),
        "smjernice": [
            "CSA2 revizija Akta o kibernetičkoj sigurnosti visokorizični dobavljači",
            "NIS2 provedba u Hrvatskoj",
            "Huawei Hrvatska",
            "EU Kina trgovinski i tehnološki odnosi",
            "kineska ulaganja i diplomacija u Hrvatskoj",
        ],
        "kljucne_rijeci": ["huawei", "kines", "kinesk", "peking", "5g", "kibernet", "nis2", "telekom", "hakom"],
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
        "smjernice": [
            "javna nabava kontrolni centar centar upravljanja Hrvatska",
            "nabava video zid kontrolna soba",
            "investicije HEP HOPS HAC HŽ Infrastruktura Croatia Control",
            "nabave u BiH i Crnoj Gori za kontrolne centre i kritičnu infrastrukturu",
            "obrana i kritična infrastruktura nabava opreme",
        ],
        "kljucne_rijeci": ["nabav", "tender", "kontroln", "centar upravljanja", "hep", "hops", "autocest", "zračn", "morh", "infrastruktur"],
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
        "smjernice": [
            "spyware mobiteli državni dužnosnici",
            "Pegasus Hrvatska",
            "CERT.hr upozorenja mobilni uređaji",
            "NIS2 mobilni uređaji javni sektor",
            "nabava zaštite mobilnih uređaja ministarstvo",
        ],
        "kljucne_rijeci": ["spyware", "pegasus", "špijun", "mobitel", "mobiln", "kibernet", "hak", "cert", "nis2"],
    },
}

ZBT_KONTEKST = (
    "ZBT Consulting je PA i GR agencija u Hrvatskoj, BiH i Crnoj Gori. Prate se akteri (institucije, regulatori, "
    "državna poduzeća, lokalna uprava, udruge) radi javnih politika, nabava i poslovnog razvoja. "
    "Visoko: izjave, odluke, nacrti propisa, javna savjetovanja, nabave i ugovori koje izravno pokreće navedeni akter. "
    "Nisko: samo spominjanje imena bez veze s odlukom, politikom ili nabavom."
)

JSON_FORMAT = """Odgovori ISKLJUČIVO JSON poljem, bez ikakvog drugog teksta:
[{"url": "točan URL iz rezultata", "naslov": "...", "izvor": "domena", "datum": "YYYY-MM-DD",
  "zemlja": "HR|BA|ME|EU|OSTALO", "relevantnost": 1-5 (može decimala),
  "oznaka": "Nabava|Javno savjetovanje|Sjednica Vlade|Sabor|Propis|" ,
  "rok": "YYYY-MM-DD ako postoji rok za komentare ili ponude, inače prazno",
  "sazetak": "2 rečenice na hrvatskom: što se dogodilo i zašto je važno za klijenta"}]
Relevantnost: 5 ključno, 4 izravno relevantno, 3 relevantno, 2 površno, 1 nema veze.
Ako nema ničega, vrati []."""


# ---------- POMOĆNE ----------

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


def _domena(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def _norm_url(url):
    return url.strip().rstrip("/")


def zemlja_iz_url(url):
    host = urlparse(url).netloc.lower()
    for tld, z in TLD_ZEMLJA.items():
        if host.endswith(tld):
            return z
    return None


META_RE = re.compile(
    r'<meta[^>]+(?:property|name|itemprop)=["\']'
    r'(?:article:published_time|og:published_time|datePublished|pubdate|date|DC.date.issued)["\']'
    r'[^>]*content=["\']([^"\']+)["\']',
    re.I,
)
JSONLD_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')


def _datum_sa_stranice(url):
    """Vraca (postoji, datum). postoji=False ako stranica nije dostupna."""
    try:
        r = requests.get(url, timeout=12, headers=UA)
        if r.status_code >= 400:
            return False, None
        html = r.text[:400_000]
        m = META_RE.search(html) or JSONLD_RE.search(html)
        return True, parse_date(m.group(1)) if m else None
    except Exception:
        return False, None


def _json_iz_teksta(tekst):
    blokovi = re.findall(r"```(?:json)?\s*(.*?)```", tekst or "", re.S)
    for k in list(reversed(blokovi)) + [tekst or ""]:
        a, b = k.find("["), k.rfind("]")
        if a != -1 and b > a:
            try:
                data = json.loads(k[a:b + 1])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                continue
    return []


def _normaliziraj(d, krug):
    if not isinstance(d, dict):
        return None
    url = str(d.get("url", "")).strip()
    if not url.startswith("http"):
        return None
    try:
        score = float(d.get("relevantnost", 0))
    except (TypeError, ValueError):
        score = 0.0
    zemlja = str(d.get("zemlja", "OSTALO")).upper()
    if zemlja not in ZASTAVE:
        zemlja = "OSTALO"
    return {
        "url": url,
        "naslov": str(d.get("naslov") or url)[:400],
        "izvor": str(d.get("izvor") or _domena(url)),
        "datum": str(d.get("datum", "")),
        "zemlja": zemlja_iz_url(url) or zemlja,
        "relevantnost": max(1.0, min(5.0, score)),
        "oznaka": str(d.get("oznaka") or "").strip(),
        "rok": str(d.get("rok") or "").strip(),
        "sazetak": str(d.get("sazetak") or "").strip(),
        "krug": krug,
    }


# ---------- CLAUDE ----------

def _client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _model():
    return os.environ.get("CLAUDE_MODEL") or "claude-haiku-5-5"


def alat_pretraga(max_uses, allowed=None):
    t = {"type": WEB_SEARCH, "name": "web_search", "max_uses": max_uses, "user_location": USER_LOCATION}
    if allowed:
        t["allowed_domains"] = allowed
    else:
        t["blocked_domains"] = BLOKIRANO
    return t


def alat_dohvat(max_uses, allowed):
    return {"type": WEB_FETCH, "name": "web_fetch", "max_uses": max_uses, "allowed_domains": allowed}


def claude_poziv(prompt, tools=None, max_tokens=8000):
    """Vraca (tekst, viđeni_url-ovi, broj_pretraga)."""
    client = _client()
    messages = [{"role": "user", "content": prompt}]
    tekst, urls, pretrage = [], set(), 0
    kwargs = {"model": _model(), "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
        if any(t["type"] == WEB_FETCH for t in tools):
            kwargs["extra_headers"] = {"anthropic-beta": FETCH_BETA}

    asistent = []
    for _ in range(4):  # nastavak ako API vrati pause_turn
        resp = client.messages.create(messages=messages, **kwargs)
        u = getattr(resp.usage, "server_tool_use", None)
        if u is not None:
            pretrage += getattr(u, "web_search_requests", 0) or 0
        for b in resp.content:
            if b.type == "text":
                tekst.append(b.text)
            elif b.type == "web_search_tool_result" and isinstance(b.content, list):
                for r in b.content:
                    if getattr(r, "url", None):
                        urls.add(_norm_url(r.url))
            elif b.type == "web_fetch_tool_result":
                if getattr(b.content, "url", None):
                    urls.add(_norm_url(b.content.url))
        if resp.stop_reason == "pause_turn":
            asistent += list(resp.content)
            messages = [messages[0], {"role": "assistant", "content": asistent}]
            continue
        break
    return "\n".join(tekst), urls, pretrage


# ---------- KRUGOVI PRETRAGE ----------

def _uvod(start, today):
    return (
        f"Danas je {today:%d.%m.%Y.} Radiš za PA i GR agenciju ZBT Consulting.\n"
        f"RAZDOBLJE: samo sadržaj objavljen od {start:%d.%m.%Y.} do {today:%d.%m.%Y.} Starije ne uključuj.\n"
    )


def krug1(cfg, start, today):
    prompt = _uvod(start, today) + f"""
KLIJENT: {cfg['naziv']}
KONTEKST: {cfg['kontekst']}

KAKO TRAŽITI:
- Pretražuj na hrvatskom i engleskom.
- Pokrij hrvatske medije (Jutarnji, Večernji, Index, N1, HRT, Poslovni dnevnik, Lider, Novi list, tportal,
  Telegram, Nacional, Netokracija, regionalne portale), institucije (Vlada, Sabor, ministarstva, regulatori,
  e-Savjetovanja, Narodne novine, gradovi) te EU izvore (Komisija, Parlament, Euractiv, Politico Europe)
  kad se tiču Hrvatske, BiH ili Crne Gore.
- Polazne teme: {'; '.join(cfg['smjernice'])}.
- Prilagodi upite prema onome što pronađeš.
Uključi samo stavke koje si pronašao pretragom, s točnim URL-om iz rezultata. Ne izmišljaj URL-ove ni datume.

{JSON_FORMAT}"""
    tekst, urls, n = claude_poziv(prompt, [alat_pretraga(PRETRAGE_KRUG1)])
    stavke = [s for s in (_normaliziraj(d, "krug 1") for d in _json_iz_teksta(tekst)) if s]
    return stavke, urls, n


def krug2(cfg, start, today, prve):
    if not prve or PRETRAGE_KRUG2 <= 0:
        return [], set(), 0
    popis = "\n".join(f"- {s['naslov']} ({s['izvor']})" for s in prve[:15])
    poznati = "\n".join(s["url"] for s in prve)
    prompt = _uvod(start, today) + f"""
KLIJENT: {cfg['naziv']}
KONTEKST: {cfg['kontekst']}

U prvom krugu pronađene su ove stavke:
{popis}

DRUGI KRUG: iz tih stavki izdvoji konkretne zakone, institucije, osobe, projekte i nabave te napravi
2 do 3 ciljane pretrage koje će pronaći NOVE povezane objave iz istog razdoblja (reakcije, službene
dokumente, rokove, nastavak priče). Ne vraćaj ove već poznate URL-ove:
{poznati}

{JSON_FORMAT}"""
    tekst, urls, n = claude_poziv(prompt, [alat_pretraga(PRETRAGE_KRUG2)])
    stavke = [s for s in (_normaliziraj(d, "krug 2") for d in _json_iz_teksta(tekst)) if s]
    return stavke, urls, n


def krug_institucije(start, today):
    """Jedan poziv za sve klijente. Svaka stavka dobiva ocjenu po klijentu."""
    klijenti = "\n".join(f"- {k}: {c['kontekst']}" for k, c in CLIENTS.items())
    prompt = _uvod(start, today) + f"""
ZADATAK: pregledaj službene izvore i pronađi objave iz razdoblja:
- nova javna savjetovanja (e-Savjetovanja i savjetovanja gradova, uključujući planove upravljanja destinacijom) i njihove rokove
- dnevni red i odluke sjednica Vlade
- rad Sabora i saborskih odbora
- nove brojeve Narodnih novina i važne propise u njima
- objave ministarstava, regulatora (HAKOM, HANFA, HERA, HALMED, AZTN, Porezna uprava, CERT.hr) i velike javne nabave

Možeš otvoriti ove početne stranice i pratiti poveznice na njima:
{chr(10).join(INSTITUCIJE_POCETNE)}

KLIJENTI:
{klijenti}

Za svaku stavku ocijeni relevantnost (1-5) za svakog klijenta za kojeg je bitna.
Uključi stavku samo ako je barem za jednog klijenta ocjena 2.5 ili viša.
Ne izmišljaj URL-ove ni datume.

Odgovori ISKLJUČIVO JSON poljem:
[{{"url": "...", "naslov": "...", "izvor": "domena", "datum": "YYYY-MM-DD", "zemlja": "HR|EU",
   "oznaka": "Javno savjetovanje|Sjednica Vlade|Sabor|Propis|Nabava|", "rok": "YYYY-MM-DD ili prazno",
   "sazetak": "2 rečenice na hrvatskom", "klijenti": {{"airbnb": 4, "huawei": 2}}}}]"""
    tools = [
        alat_pretraga(PRETRAGE_INSTITUCIJE, allowed=INSTITUCIJE_DOMENE),
        alat_dohvat(DOHVACANJA_INSTITUCIJE, INSTITUCIJE_DOMENE),
    ]
    tekst, urls, n = claude_poziv(prompt, tools, max_tokens=12000)
    return _json_iz_teksta(tekst), urls, n


def institucije_za_klijenta(sirove, key):
    out = []
    for d in sirove:
        if not isinstance(d, dict):
            continue
        ocjene = d.get("klijenti") or {}
        if key not in ocjene:
            continue
        s = _normaliziraj({**d, "relevantnost": ocjene.get(key)}, "institucije")
        if s:
            out.append(s)
    return out


# ---------- RSS ----------

def rss_stavke(start, today):
    out, greske = {}, []
    for feed in RSS_FEEDOVI:
        try:
            r = requests.get(feed, timeout=15, headers=UA)
            root = ET.fromstring(r.content)
            for it in root.iter("item"):
                link = (it.findtext("link") or "").strip()
                pub = it.findtext("pubDate")
                try:
                    d = parsedate_to_datetime(pub).date() if pub else None
                except (TypeError, ValueError):
                    d = None
                if not link or not d or not (start <= d <= today):
                    continue
                opis = re.sub(r"<[^>]+>", "", it.findtext("description") or "")
                out[link] = {"url": link, "naslov": (it.findtext("title") or "").strip(),
                             "opis": opis.strip()[:400], "datum": d.isoformat()}
        except Exception as e:
            greske.append(f"RSS {feed}: {e}")
    return list(out.values()), greske


def ocijeni_rss(cfg, svi_rss, start, today):
    kw = [k.lower() for k in cfg["kljucne_rijeci"]]
    kandidati = [s for s in svi_rss if any(k in f"{s['naslov']} {s['opis']}".lower() for k in kw)][:40]
    if not kandidati:
        return []
    popis = "\n".join(f"{i}. {s['naslov']} | {s['opis']}" for i, s in enumerate(kandidati))
    prompt = _uvod(start, today) + f"""
KLIJENT: {cfg['naziv']}
KONTEKST: {cfg['kontekst']}

Ocijeni ove naslove s Index.hr (broj. naslov | opis):
{popis}

Odgovori ISKLJUČIVO JSON poljem, samo za stavke s relevantnošću 2 ili više:
[{{"i": broj, "relevantnost": 1-5, "zemlja": "HR|BA|ME|EU|OSTALO", "oznaka": "Nabava|Javno savjetovanje|", "sazetak": "2 rečenice na hrvatskom"}}]"""
    tekst, _, _ = claude_poziv(prompt, max_tokens=4000)
    out = []
    for d in _json_iz_teksta(tekst):
        try:
            k = kandidati[int(d.get("i"))]
        except (TypeError, ValueError, IndexError):
            continue
        s = _normaliziraj({**d, "url": k["url"], "naslov": k["naslov"], "izvor": "index.hr", "datum": k["datum"]}, "RSS")
        if s:
            out.append(s)
    return out


# ---------- PROVJERA ----------

def _provjeri(s, vidjeni, start, today):
    postoji, d_stranica = _datum_sa_stranice(s["url"])
    if not postoji and _norm_url(s["url"]) not in vidjeni:
        return None  # nedostupno i nije iz rezultata pretrage: moguće izmišljen URL
    d = d_stranica or parse_date(s["datum"])
    if not d or d < start or d > today:
        return None
    return {**s, "datum": d.isoformat()}


def provjeri_sve(stavke, vidjeni, start, today):
    with ThreadPoolExecutor(max_workers=8) as ex:
        rez = list(ex.map(lambda s: _provjeri(s, vidjeni, start, today), stavke))
    return [r for r in rez if r]


def spoji(*liste):
    out = {}
    for lista in liste:
        for s in lista:
            k = _norm_url(s["url"])
            if k not in out or s["relevantnost"] > out[k]["relevantnost"]:
                out[k] = s
    return list(out.values())


def obradi_klijenta(key, start, today, inst_sirove, inst_urls, svi_rss):
    cfg = CLIENTS[key]
    greske, pretrage = [], 0
    k1, u1, k2, u2 = [], set(), [], set()
    try:
        k1, u1, n = krug1(cfg, start, today)
        pretrage += n
    except Exception as e:
        greske.append(f"krug 1: {e}")
    try:
        k2, u2, n = krug2(cfg, start, today, k1)
        pretrage += n
    except Exception as e:
        greske.append(f"krug 2: {e}")
    try:
        k_rss = ocijeni_rss(cfg, svi_rss, start, today)
    except Exception as e:
        k_rss = []
        greske.append(f"RSS ocjena: {e}")
    k_inst = institucije_za_klijenta(inst_sirove, key)

    sve = spoji(k1, k2, k_rss, k_inst)
    vidjeni = u1 | u2 | inst_urls | {_norm_url(s["url"]) for s in k_rss}
    provjerene = [s for s in provjeri_sve(sve, vidjeni, start, today) if s["relevantnost"] >= MIN_RELEVANTNOST]
    stats = {"pronadeno": len(sve), "spremljeno": len(provjerene), "pretrage": pretrage}
    return provjerene, stats, greske


def trazi_aktere(akteri, start, today):
    prompt = _uvod(start, today) + f"""
KONTEKST: {ZBT_KONTEKST}
AKTERI: {', '.join(akteri)}

Pronađi objave iz razdoblja u kojima navedeni akteri nešto odlučuju, izjavljuju, objavljuju, nabavljaju
ili otvaraju savjetovanje. Pretražuj na hrvatskom, a za akteri iz BiH i Crne Gore i na lokalnom jeziku.
Uključi samo stavke koje si pronašao pretragom, s točnim URL-om. Ne izmišljaj URL-ove ni datume.

{JSON_FORMAT}"""
    tekst, urls, n = claude_poziv(prompt, [alat_pretraga(PRETRAGE_AKTERI)])
    stavke = [s for s in (_normaliziraj(d, "akteri") for d in _json_iz_teksta(tekst)) if s]
    provjerene = [s for s in provjeri_sve(spoji(stavke), urls, start, today) if s["relevantnost"] >= MIN_RELEVANTNOST]
    provjerene.sort(key=lambda s: (s["relevantnost"], s["datum"]), reverse=True)
    return provjerene, n


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
        "oznaka": s["oznaka"], "rok": s["rok"], "sazetak": s["sazetak"], "krug": s["krug"],
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
