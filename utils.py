import json
from datetime import datetime, timedelta

import streamlit as st
from exa_py import Exa
from openai import OpenAI

DANA_UNAZAD = 3
MIN_RELEVANTNOST = 2.5

# Kineski državni i kineski mediji na engleskom – isključeni iz pretrage
ISKLJUCENI_IZVORI = [
    "xinhuanet.com", "news.cn", "english.news.cn", "globaltimes.cn",
    "chinadaily.com.cn", "cgtn.com", "chinamil.com.cn", "people.com.cn", "ecns.cn",
]

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
    },
    "huawei": {
        "naziv": "Huawei",
        "kontekst": (
            "Tim prati Huawei i kinesku opremu u Hrvatskoj, BiH i Crnoj Gori, te geopolitiku između "
            "SAD-a, EU-a i Kine. Visoka relevantnost: pregovori o CSA2 (Akt o kibernetičkoj sigurnosti) "
            "i NIS2, zahtjevi za visokorizične dobavljače, javne nabave u kojima se spominje Huawei ili "
            "kineska oprema (telekomi, 5G, državna infrastruktura), odnos SAD–Kina, EU–Kina, EU–Huawei "
            "i Kina–Hrvatska (ulaganja, diplomacija, posjeti), stavovi Sabora, Vlade i ministarstava o toj temi. "
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
    },
    "weytec": {
        "naziv": "WEYTEC",
        "kontekst": (
            "Tim prati tržište za WEYTEC, švicarskog proizvođača opreme za kontrolne sobe i trgovinske "
            "podove (smartTOUCH, smartVISUAL, WDP MX, KVM). Visoka relevantnost: javne nabave u Hrvatskoj, "
            "BiH i Crnoj Gori za kontrolne sobe, centre upravljanja, prometne centre, energetiku, zračni promet, "
            "sigurnosne službe i banke; tehnički natječaji za video zidove, KVM, radna mjesta; projekti u regiji "
            "(NEK, DARS, ELES, EMS, DEM, Gastrans). Oznaka 'Nabava' za sve tendere i natječaje. "
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
    },
    "envoid": {
        "naziv": "Envoid",
        "kontekst": (
            "Tim prati tržište za Envoid, zaštitu mobilnih uređaja za visokorizične organizacije. "
            "Visoka relevantnost: mobilni spyware i napadi (Pegasus, DarkSword, Coruna) u Hrvatskoj, BiH, "
            "Crnoj Gori i EU, posebno ako se tiču državnih službenika, vojske, diplomacije; regulativa "
            "(NIS2, CSA2, zaštita klasificiranih podataka); upozorenja CERT.hr, ENISA, ZSIS; javne nabave "
            "i tenderi za zaštitu mobitela, MDM i MTD rješenja u javnom sektoru (MUP, MORH, ministarstva, "
            "sudovi, državna poduzeća). Oznaka 'Nabava' za tendere. "
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
    },
}


def check_password():
    if st.session_state.get("password_correct"):
        return True
    st.title("🔒 Prijava")
    pw = st.text_input("Lozinka:", type="password")
    if pw:
        if pw == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Netočna lozinka.")
    return False


def page_setup():
    st.set_page_config(page_title="Praćenje vijesti", page_icon="▪", layout="centered")
    st.markdown(
        """
        <style>
        #MainMenu, footer {visibility: hidden;}
        .block-container {max-width: 820px; padding-top: 2rem;}
        h1 {font-weight: 600; letter-spacing: -0.02em;}
        a {color: #1F4E79;}
        hr {margin: 0.8rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def ai_ocjena(oai, kontekst, title, text):
    prompt = f"""Ocijeni vijest za praćenje klijenta.

KONTEKST KLIJENTA:
{kontekst}

PRAVILA:
- Relevantnost je broj od 1 do 5, može s decimalom (npr. 2.5).
  5 = ključno, mora se pročitati. 4 = izravno relevantno. 3 = relevantno.
  2 = površno povezano. 1 = nema veze.
- Ocijeni s 1 oglase za nekretnine, sadržaj agencija, sport i crnu kroniku.
- Ocijeni s 1 vijesti iz izvora izvan Hrvatske, BiH i Crne Gore, osim ako se izravno tiču tih zemalja.
- Javna nabava dobiva oznaku "Nabava". Javno savjetovanje dobiva oznaku "Javno savjetovanje". Inače je oznaka prazna.

Odgovori isključivo JSON objektom:
{{"relevantnost": <broj 1-5>, "oznaka": "<Nabava | Javno savjetovanje | prazno>", "sazetak": "<2 rečenice na hrvatskom>"}}

Naslov: {title}
Sadržaj: {text[:3000]}"""

    response = oai.chat.completions.create(
        model=st.secrets.get("OPENAI_MODEL", "gpt-4o-mini"),
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
    return score, data.get("oznaka", "").strip(), data.get("sazetak", "").strip()


@st.cache_data(ttl=timedelta(hours=6), show_spinner=False)
def fetch_news(client_key):
    exa, oai = get_clients()
    cfg = CLIENTS[client_key]
    start = (datetime.now() - timedelta(days=DANA_UNAZAD)).date()

    greske = []
    rezultati = {}  # dedup po URL-u

    for q in cfg["upiti"]:
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

    vijesti = []
    izbaceno_datum = 0
    izbaceno_relevantnost = 0

    for url, item in rezultati.items():
        pub = parse_date(item.published_date)
        if not pub or pub < start or not item.text:
            izbaceno_datum += 1
            continue
        try:
            score, oznaka, sazetak = ai_ocjena(oai, cfg["kontekst"], item.title, item.text)
        except Exception as e:
            greske.append(f"OpenAI, {url}: {e}")
            continue

        if score < MIN_RELEVANTNOST:
            izbaceno_relevantnost += 1
            continue

        vijesti.append({
            "title": item.title or url,
            "url": url,
            "source": url.split("/")[2].replace("www.", ""),
            "date": pub.strftime("%d.%m.%Y."),
            "sort_date": pub.isoformat(),
            "relevantnost": score,
            "oznaka": oznaka,
            "summary": sazetak or "Pregledajte članak za detalje.",
        })

    vijesti.sort(key=lambda v: (v["sort_date"], v["relevantnost"]), reverse=True)

    return {
        "vijesti": vijesti,
        "greske": greske,
        "dohvaceno": len(rezultati),
        "izbaceno_datum": izbaceno_datum,
        "izbaceno_relevantnost": izbaceno_relevantnost,
    }


def render_client_page(client_key):
    cfg = CLIENTS[client_key]
    st.title(cfg["naziv"])
    st.caption(f"Zadnja {DANA_UNAZAD} dana · prag relevantnosti {MIN_RELEVANTNOST}")

    with st.spinner("Pretražujem izvore..."):
        r = fetch_news(client_key)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dohvaćeno", r["dohvaceno"])
    c2.metric("Izbačeno (datum)", r["izbaceno_datum"])
    c3.metric("Izbačeno (relevantnost)", r["izbaceno_relevantnost"])
    c4.metric("Prikazano", len(r["vijesti"]))

    if st.button("Osvježi"):
        fetch_news.clear()
        st.rerun()

    if r["greske"]:
        with st.expander(f"⚠️ {len(r['greske'])} grešaka pri dohvaćanju"):
            for g in r["greske"][:30]:
                st.code(g)

    st.divider()

    if not r["vijesti"]:
        st.info("Nema relevantnih objava u zadnja tri dana.")
        return

    for v in r["vijesti"]:
        oznaka = f" · **{v['oznaka']}**" if v["oznaka"] else ""
        st.markdown(f"**[{v['title']}]({v['url']})**")
        st.caption(f"{v['date']} · {v['source']} · relevantnost {v['relevantnost']}{oznaka}")
        st.write(v["summary"])
        st.divider()
