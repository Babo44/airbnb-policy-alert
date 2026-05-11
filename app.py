import streamlit as st
import feedparser
import urllib.parse
from openai import OpenAI
from datetime import timedelta

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb Policy Alert", page_icon="🏠")

# --- SUSTAV PRIJAVE (LOGIN) ---
def check_password():
    """Vraća True ako je korisnik unio ispravnu lozinku."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 Prijava za pristup")
        # Tražimo unos lozinke, text_input s type="password" skriva znakove
        password = st.text_input("Unesite lozinku:", type="password")
        
        if password:
            # Provjeravamo podudara li se unos s lozinkom u Streamlit Secrets
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun() # Osvježava stranicu kako bi se prikazao glavni sadržaj
            else:
                st.error("😕 Netočna lozinka. Pokušajte ponovno.")
        return False
    return True

# Ako provjera lozinke ne prođe, zaustavljamo crtanje ostatka stranice
if not check_password():
    st.stop()


# --- GLAVNI DIO APLIKACIJE (Nakon uspješne prijave) ---
st.title("🏠 Airbnb Policy Alert")
st.markdown("Ovaj alat dnevno prati vijesti o regulativama, porezima i zakonima vezanim uz kratkoročni najam i filtrira ih pomoću umjetne inteligencije.")
st.divider()

# Inicijalizacija OpenAI klijenta (ključ se vuče iz Streamlit Secrets)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- DOHVAĆANJE I AI ANALIZA (S Cachingom od 12 sati) ---
@st.cache_data(ttl=timedelta(hours=12))
def fetch_and_analyze_news():
    # Pametno posloženi upiti za Google News
    queries = [
        "Airbnb Hrvatska zakon OR vlada OR udruga OR ministarstvo",
        "kratkoročni najam regulativa OR zakon",
        "porez na nekretnine iznajmljivači",
        "obiteljski iznajmljivači"
    ]
    
    relevant_news = []
    seen_links = set() # Set za sprječavanje istih vijesti

    for query in queries:
        # Prebacujemo tekst u format pogodan za URL linkove
        encoded_query = urllib.parse.quote(query)
        # Google News RSS URL za Hrvatsku
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        
        feed = feedparser.parse(rss_url)
        
        # Gledamo samo prvih 7 najnovijih vijesti po svakom upitu da ne trošimo puno AI API-ja
        for entry in feed.entries[:7]:
            title = entry.title
            link = entry.link
            summary = entry.get('description', '')
            
            # Ako smo već obradili ovu vijest (ista vijest može iskočiti na dva upita), preskoči
            if link in seen_links:
                continue
            seen_links.add(link)

            # OpenAI Analiza
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si precizan asistent koji analizira vijesti."},
                        {"role": "user", "content": f"Je li ovo vijest o državnim zakonima, porezima ili javnim politikama vezanim za Airbnb, kratkoročni najam ili iznajmljivače (uključujući rad ministarstava, vlade ili udruga po tom pitanju)? Odgovori samo s DA ili NE.\n\nNaslov: {title}\nSažetak: {summary}"}
                    ],
                    max_tokens=5, # Treba nam samo kratak odgovor
                    temperature=0.1 # Niska temperatura znači manje haluciniranja, precizniji odgovor
                )
                
                answer = response.choices[0].message.content.strip().upper()
                
                # Ako je AI rekao DA, spremamo vijest
                if "DA" in answer:
                    relevant_news.append({"title": title, "link": link})
            except Exception as e:
                pass # U slučaju greške preskačemo tu vijest kako aplikacija ne bi pukla
                
    return relevant_news

# --- PRIKAZ REZULTATA ---
# Dok se funkcija izvodi (ili vuče iz cachea), vrtimo spinner
with st.spinner("Pretražujem web i analiziram sadržaj... Ovo može potrajati 10-15 sekundi."):
    news_items = fetch_and_analyze_news()

if news_items:
    st.success(f"Pronađeno je {len(news_items)} relevantnih policy vijesti!")
    for item in news_items:
        # Prikazujemo vijest kao markdown link (klikabilni naslov)
        st.markdown(f"📌 **[{item['title']}]({item['link']})**")
else:
    st.info("Danas nema novih policy vijesti. Provjerite ponovno kasnije.")
