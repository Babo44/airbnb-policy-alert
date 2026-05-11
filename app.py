import streamlit as st
import feedparser
import urllib.parse
from openai import OpenAI
from datetime import datetime, timedelta
import time

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb Public Affairs Alert", page_icon="🏛️", layout="wide")

# --- SUSTAV PRIJAVE (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 Prijava za pristup")
        password = st.text_input("Unesite lozinku:", type="password")
        
        if password:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Netočna lozinka. Pokušajte ponovno.")
        return False
    return True

if not check_password():
    st.stop()


# --- GLAVNI DIO APLIKACIJE ---
st.title("🏛️ Airbnb Public Affairs & GR Tracker")
st.markdown("Alat dizajniran za **Government Relations menadžere**. Prati poteze Vlade, Nacionalnog vijeća, zakone, izjave ministara i makroekonomske podatke o turističkoj sezoni (zadnjih 14 dana).")
st.divider()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- DOHVAĆANJE I AI ANALIZA ---
@st.cache_data(ttl=timedelta(hours=12))
def fetch_and_analyze_news():
    # Mreža pretrage prilagođena za Public Affairs
    queries = [
        "Nacionalno vijeće za razvoj turizma",
        "Ministarstvo turizma sezona",
        "HTZ podaci turizam",
        "Vlada RH turizam",
        "Zakon o upravljanju zgradama apartmani",
        "kratkoročni najam zakon",
        "porez na nekretnine iznajmljivači",
        "Tonči Glavina cijene",
        "Airbnb Hrvatska"
    ]
    
    relevant_news = []
    seen_links = set()
    # Povećano na 14 dana da uhvatimo sjednice od prošlog tjedna
    days_ago = datetime.now() - timedelta(days=14)
    
    total_raw_articles = 0 

    for query in queries:
        encoded_query = urllib.parse.quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        
        feed = feedparser.parse(rss_url)
        total_raw_articles += len(feed.entries)
        
        for entry in feed.entries[:25]:
            link = entry.link
            if link in seen_links:
                continue
            seen_links.add(link)

            pub_date_parsed = entry.get('published_parsed')
            if pub_date_parsed:
                dt_published = datetime.fromtimestamp(time.mktime(pub_date_parsed))
                if dt_published < days_ago:
                    continue 
                date_str = dt_published.strftime("%d.%m.%Y.")
            else:
                date_str = "Nepoznat datum"

            raw_title = entry.title
            source = raw_title.rsplit(" - ", 1)[1] if " - " in raw_title else "Nepoznat izvor"
            clean_title = raw_title.rsplit(" - ", 1)[0] if " - " in raw_title else raw_title
            summary = entry.get('description', '')

            # --- AI PROMPT ZA PUBLIC AFFAIRS MANAGERA ---
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si Senior Public Affairs i Government Relations analitičar za Airbnb u Hrvatskoj."},
                        {"role": "user", "content": f"Procijeni važnost ove vijesti. Tražimo sve o: regulativama, sjednicama vlade/vijeća, podacima HTZ-a o sezoni, cijenama, potezima ministarstava i udruga.\n\nVAŽNO: Hrvatski portali često skrivaju sažetak (npr. piše samo 'Pročitajte više'). U tom slučaju, OSLONI SE ISKLJUČIVO NA NASLOV!\n\nODBIJ (samo 'NE') JEDINO ako je ovo klasičan oglas za prodaju nekretnine, sport ili čista crna kronika.\nPRIHVATI ('DA | [Tvoj kratki GR komentar zašto je ovo politički/poslovno bitno]') sve vezano za turističku politiku i brojke.\n\nNaslov: {clean_title}\nSažetak: {summary}"}
                    ],
                    max_tokens=150,
                    temperature=0.1
                )
                
                answer = response.choices[0].message.content.strip()
                
                if answer.upper().startswith("DA"):
                    reason = answer.split("|", 1)[1].strip() if "|" in answer else "Relevantno za GR i javne politike."
                    relevant_news.append({
                        "title": clean_title, "link": link, "date": date_str, "source": source, "reason": reason
                    })
            except Exception as e:
                pass 
        
        time.sleep(1)
                
    return relevant_news, total_raw_articles

# --- PRIKAZ REZULTATA ---
with st.spinner("Skeniram portale unazad 14 dana i radim Public Affairs analizu (cca 15 sekundi)..."):
    news_items, raw_count = fetch_and_analyze_news()

st.caption(f"*(Tehnički info: Od {raw_count} prikupljenih članaka, AI je izvukao {len(news_items)} GR sažetaka)*")

if news_items:
    st.success(f"Pronađeno je {len(news_items)} važnih tema u zadnjih 14 dana!")
    for item in news_items:
        st.markdown(f"#### [{item['title']}]({item['link']})")
        st.caption(f"📅 **Datum:** {item['date']} | 📰 **Izvor:** {item['source']}")
        st.info(f"🏛️ **GR Analiza:** {item['reason']}")
        st.divider()
else:
    st.info("Nema novih političkih ni statističkih kretanja u zadnjih 14 dana.")
