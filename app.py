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
st.markdown("Ovaj alat prati vijesti o regulativama i zakonima vezanim uz kratkoročni najam **unazad 7 dana**.")
st.divider()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- DOHVAĆANJE I AI ANALIZA ---
def fetch_and_analyze_news():
    # 6 jakih i jasnih pojmova
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
        # KLJUČNA PROMJENA 1: quote_plus stavlja pluseve (+) umjesto razmaka, što Google voli
        encoded_query = urllib.parse.quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        
        feed = feedparser.parse(rss_url)
        total_raw_articles += len(feed.entries)
        
        for entry in feed.entries[:20]:
            link = entry.link
            
            if link in seen_links:
                continue
            seen_links.add(link)

            # --- OBRADA DATUMA ---
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

            # --- AI ANALIZA ---
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si stručnjak za analizu turističkih regulativa u Hrvatskoj."},
                        {"role": "user", "content": f"Je li ova vijest vezana za mijenjanje zakona, poreza, ili javnih politika o kratkoročnom najmu? Ako NIJE, odgovori s 'NE'. Ako JEST, odgovori točno u formatu: 'DA | [Kratki razlog]'.\n\nNaslov: {clean_title}\nSažetak: {summary}"}
                    ],
                    max_tokens=150,
                    temperature=0.1
                )
                
                answer = response.choices[0].message.content.strip()
                
                if answer.upper().startswith("DA"):
                    reason = answer.split("|", 1)[1].strip() if "|" in answer else "Relevantna policy vijest."
                    relevant_news.append({
                        "title": clean_title, "link": link, "date": date_str, "source": source, "reason": reason
                    })
            except Exception as e:
                st.error(f"🚨 Greška s OpenAI API-jem: {e}")
        
        # KLJUČNA PROMJENA 2: Pauza od 1 sekunde da nas Google ne blokira zbog spama
        time.sleep(1)
                
    return relevant_news, total_raw_articles

# --- PRIKAZ REZULTATA ---
with st.spinner("Pretražujem web za zadnjih 7 dana i AI analizira sadržaj (prikupljam sirove podatke, traje oko 10-15 sekundi)..."):
    news_items, raw_count = fetch_and_analyze_news()

st.caption(f"*(Detektivski info: Google je ukupno pronašao {raw_count} sirovih vijesti prije vremenskog i AI filtriranja)*")

if news_items:
    st.success(f"Pronađeno je {len(news_items)} bitnih vijesti u zadnjih 7 dana!")
    for item in news_items:
        st.markdown(f"### [{item['title']}]({item['link']})")
        st.caption(f"📅 **Datum:** {item['date']} | 📰 **Izvor:** {item['source']}")
        st.info(f"💡 **Zašto je bitno:** {item['reason']}")
        st.divider()
else:
    st.info("U zadnjih 7 dana nije bilo novih relevantnih policy vijesti vezanih uz Airbnb.")
