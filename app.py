import streamlit as st
import feedparser
import urllib.parse
from openai import OpenAI
from datetime import datetime, timedelta
import time

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb Policy Alert", page_icon="🏠")

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
st.title("🏠 Airbnb Policy Alert")
st.markdown("Ovaj alat prati vijesti o kratkoročnom najmu i turizmu **unazad 7 dana**. Prikazuje apsolutno sve relevantno i uklanja samo spam i oglase.")
st.divider()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- DOHVAĆANJE I AI ANALIZA (Vraćen Cache na 12 sati za štednju novca) ---
@st.cache_data(ttl=timedelta(hours=12))
def fetch_and_analyze_news():
    queries = [
        "Airbnb Hrvatska",
        "kratkoročni najam",
        "porez na nekretnine",
        "Tonči Glavina",
        "Zakon o upravljanju zgradama",
        "turizam apartmani"
    ]
    
    relevant_news = []
    seen_links = set()
    seven_days_ago = datetime.now() - timedelta(days=7)
    
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
                if dt_published < seven_days_ago:
                    continue 
                date_str = dt_published.strftime("%d.%m.%Y.")
            else:
                date_str = "Nepoznat datum"

            raw_title = entry.title
            source = raw_title.rsplit(" - ", 1)[1] if " - " in raw_title else "Nepoznat izvor"
            clean_title = raw_title.rsplit(" - ", 1)[0] if " - " in raw_title else raw_title
            summary = entry.get('description', '')

            # --- NOVI, SVEOPUHVATNI AI PROMPT (GLUMI SAMO "REDARA" ZA OGLASE) ---
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si brzi filter za vijesti o turizmu i iznajmljivanju."},
                        {"role": "user", "content": f"Zanima nas doslovno SVE o Airbnb-u, kratkoročnom najmu, turizmu, zakonima i statistikama u Hrvatskoj.\n\nTVOJ JEDINI ZADATAK JE IZBACITI OGLASE I POTPUNI SPAM.\n\nODBIJ (odgovori samo 'NE') isključivo ako je ovo oglas za prodaju nekretnine, oglas za rezervaciju apartmana, ili potpuni spam koji nema veze s turizmom.\n\nPRIHVATI (odgovori 'DA | [Kratki sažetak članka u jednoj rečenici]') sve ostale vijesti: zakone, statistike, rasprave, nesreće, žalbe građana, izjave političara i trendove.\n\nNaslov: {clean_title}\nSažetak: {summary}"}
                    ],
                    max_tokens=150,
                    temperature=0.1
                )
                
                answer = response.choices[0].message.content.strip()
                
                if answer.upper().startswith("DA"):
                    reason = answer.split("|", 1)[1].strip() if "|" in answer else "Općenita vijest o turizmu/najmu."
                    relevant_news.append({
                        "title": clean_title, "link": link, "date": date_str, "source": source, "reason": reason
                    })
            except Exception as e:
                pass # U cache modu gasimo ispisivanje grešaka da stranica ostane čista
        
        time.sleep(1)
                
    return relevant_news, total_raw_articles

# --- PRIKAZ REZULTATA ---
with st.spinner("Pretražujem web za zadnjih 7 dana i AI izbacuje oglase (traje oko 10-15 sekundi)..."):
    news_items, raw_count = fetch_and_analyze_news()

st.caption(f"*(Detektivski info: Od {raw_count} sirovih rezultata, AI je izbacio oglase i ostavio {len(news_items)} vijesti)*")

if news_items:
    st.success(f"Pronađeno je {len(news_items)} vijesti u zadnjih 7 dana!")
    for item in news_items:
        st.markdown(f"### [{item['title']}]({item['link']})")
        st.caption(f"📅 **Datum:** {item['date']} | 📰 **Izvor:** {item['source']}")
        st.info(f"💡 **Sažetak:** {item['reason']}")
        st.divider()
else:
    st.info("U zadnjih 7 dana nije bilo nikakvih novosti.")
