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
    """Vraća True ako je korisnik unio ispravnu lozinku."""
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
st.markdown("Ovaj alat prati vijesti o regulativama i zakonima vezanim uz kratkoročni najam **unazad 7 dana** te koristi AI za analizu utjecaja na iznajmljivače.")
st.divider()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- DOHVAĆANJE I AI ANALIZA ---
@st.cache_data(ttl=timedelta(hours=12))
def fetch_and_analyze_news():
    # Dodan parametar 'when:7d' kako bi Google News forsirao svježije rezultate
    queries = [
        "Airbnb Hrvatska zakon OR vlada OR udruga OR ministarstvo when:7d",
        "kratkoročni najam regulativa OR zakon when:7d",
        "porez na nekretnine iznajmljivači when:7d",
        "obiteljski iznajmljivači when:7d"
    ]
    
    relevant_news = []
    seen_links = set()
    
    # Granica od 7 dana za precizno filtriranje
    seven_days_ago = datetime.now() - timedelta(days=7)

    for query in queries:
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        
        feed = feedparser.parse(rss_url)
        
        # Gledamo do 15 vijesti po upitu jer tražimo samo unazad 7 dana
        for entry in feed.entries[:15]:
            link = entry.link
            
            if link in seen_links:
                continue
            seen_links.add(link)

            # --- OBRADA DATUMA I FILTRIRANJE ---
            pub_date_parsed = entry.get('published_parsed')
            if pub_date_parsed:
                dt_published = datetime.fromtimestamp(time.mktime(pub_date_parsed))
                # Preskoči ako je starije od 7 dana
                if dt_published < seven_days_ago:
                    continue
                date_str = dt_published.strftime("%d.%m.%Y.")
            else:
                date_str = "Nepoznat datum"

            # --- OBRADA NASLOVA I IZVORA ---
            raw_title = entry.title
            source = "Nepoznat izvor"
            clean_title = raw_title
            
            # Google News obično na kraj naslova stavlja ime portala iza ' - '
            if " - " in raw_title:
                clean_title = raw_title.rsplit(" - ", 1)[0]
                source = raw_title.rsplit(" - ", 1)[1]

            summary = entry.get('description', '')

            # --- AI ANALIZA ---
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si stručnjak za analizu javnih politika i turističkih regulativa u Hrvatskoj."},
                        {"role": "user", "content": f"Analiziraj sljedeću vijest. Je li vezana za mijenjanje zakona, poreza, ili javnih politika o Airbnb-u i kratkoročnom najmu? \nAko NIJE (npr. samo je crna kronika, uređenje stana ili obična turistička reportaža), odgovori samo s 'NE'.\nAko JEST, odgovori točno u ovom formatu: 'DA | [Kratka rečenica koja objašnjava zašto je ovo bitno za Airbnb iznajmljivače policy-wise]'.\n\nNaslov: {clean_title}\nSažetak: {summary}"}
                    ],
                    max_tokens=150, # Povećano da AI ima prostora za pisanje razloga
                    temperature=0.1
                )
                
                answer = response.choices[0].message.content.strip()
                
                # Ako je vijest procijenjena kao relevantna (počinje s DA)
                if answer.upper().startswith("DA"):
                    reason = "Relevantna policy vijest."
                    # Izdvajanje razloga iz AI odgovora
                    if "|" in answer:
                        reason = answer.split("|", 1)[1].strip()
                    
                    relevant_news.append({
                        "title": clean_title,
                        "link": link,
                        "date": date_str,
                        "source": source,
                        "reason": reason
                    })
            except Exception as e:
                pass # U slučaju greške pri komunikaciji s API-jem preskačemo vijest
                
    return relevant_news

# --- PRIKAZ REZULTATA ---
with st.spinner("Pretražujem web za zadnjih 7 dana i AI analizira sadržaj..."):
    news_items = fetch_and_analyze_news()

if news_items:
    st.success(f"Pronađeno je {len(news_items)} bitnih vijesti u zadnjih 7 dana!")
    
    for item in news_items:
        # Lijepo formatirani prikaz sa svim traženim detaljima
        st.markdown(f"### [{item['title']}]({item['link']})")
        st.caption(f"📅 **Datum:** {item['date']} | 📰 **Izvor:** {item['source']}")
        st.info(f"💡 **Zašto je bitno:** {item['reason']}")
        st.divider()
else:
    st.info("U zadnjih 7 dana nije bilo novih relevantnih policy vijesti vezanih uz Airbnb.")
