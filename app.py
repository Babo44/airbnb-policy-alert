import streamlit as st
import feedparser
import urllib.parse
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from datetime import datetime, timedelta
import time

# --- KONFIGURACIJA ---
st.set_page_config(page_title="Airbnb Real-Time GR", page_icon="⚡", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.title("🔒 Airbnb Real-Time Radar")
        password = st.text_input("Lozinka:", type="password")
        if password:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Netočna lozinka.")
        return False
    return True

if not check_password():
    st.stop()

openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("⚡ Airbnb Real-Time Radar")
st.markdown("Hibridni sustav: **Google News (Trenutna detekcija) + AI Web Scraper (Analiza teksta)**. Prikazuje zadnja 3 dana.")
st.divider()

# --- POMOĆNA FUNKCIJA ZA ČITANJE PORTALA ---
def scrape_article_text(url):
    """Ova funkcija glumi čovjeka, otvara link i čita prve odlomke teksta."""
    try:
        # Šaljemo 'User-Agent' da portali misle da smo običan preglednik (Chrome), a ne bot
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Skupljamo sve odlomke teksta (<p> tagove)
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        
        # Vraćamo prvih 1500 znakova (sasvim dovoljno za AI da shvati poantu i ne troši tokene)
        return text[:1500] if text else "Nema teksta."
    except:
        return "Nije moguće pročitati tekst stranice."

# --- GLAVNI MOTOR ---
@st.cache_data(ttl=timedelta(hours=2)) # Osvježava se svaka 2 sata
def fetch_hybrid_news():
    # Jednostavni upiti koje Google News voli i odmah hvata
    queries = [
        "Airbnb Hrvatska",
        "kratkoročni najam",
        "Zakon upravljanje zgradama",
        "Ministarstvo turizma iznajmljivači",
        "HTZ turizam statistika",
        "porez na nekretnine"
        "Vlada turizam"
        "iznajmljivači"
            ]
    
    tri_dana_unazad = datetime.now() - timedelta(days=3)
    seen_links = set()
    final_output = []
    
    # Privremeni kontejner za prikaz napretka u Streamlitu
    progress_text = "Skeniram portale u realnom vremenu..."
    my_bar = st.progress(0, text=progress_text)
    
    total_queries = len(queries)

    for i, query in enumerate(queries):
        my_bar.progress((i + 1) / total_queries, text=f"Tražim: {query}")
        
        encoded_query = urllib.parse.quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries[:10]: # Uzimamo top 10 NAJSVJEŽIJIH po svakom upitu
            link = entry.link
            if link in seen_links:
                continue
            seen_links.add(link)

            # Provjera datuma (Google daje točan timestamp)
            pub_date_parsed = entry.get('published_parsed')
            if pub_date_parsed:
                dt_published = datetime.fromtimestamp(time.mktime(pub_date_parsed))
                if dt_published < tri_dana_unazad:
                    continue
                date_str = dt_published.strftime("%d.%m.%Y. u %H:%M")
            else:
                continue # Odbaci ako nema datuma

            # Čitamo pravi sadržaj članka s portala
            article_text = scrape_article_text(link)
            
            # Ako skripta nije uspjela pročitati tekst, oslanja se na Googleov naslov i sažetak
            if len(article_text) < 50:
                article_text = entry.get('description', entry.title)

            source = entry.title.rsplit(" - ", 1)[1] if " - " in entry.title else "Nepoznat izvor"
            clean_title = entry.title.rsplit(" - ", 1)[0] if " - " in entry.title else entry.title

            # --- AI ANALIZA ---
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si GR analitičar za Airbnb."},
                        {"role": "user", "content": f"""Analiziraj ovaj tekst. ODBIJ (samo 'NE') ako je oglas za apartman/stan, crna kronika ili čisti sport.
                        PRIHVATI sve o turizmu, zakonima, brojkama i politici (DA | [Kategorija: npr. Zakon/Statistika/Politika] | [GR Sažetak u 2 rečenice]).
                        
                        Naslov: {clean_title}
                        Sadržaj: {article_text}"""}
                    ],
                    max_tokens=150,
                    temperature=0
                )
                
                answer = response.choices[0].message.content.strip()
                
                if answer.upper().startswith("DA"):
                    parts = answer.split("|")
                    category = parts[1].strip() if len(parts) > 1 else "Turizam"
                    summary = parts[2].strip() if len(parts) > 2 else "Relevantna vijest."
                    
                    final_output.append({
                        "title": clean_title, "link": link, "source": source, 
                        "date": date_str, "category": category, "summary": summary, "dt": dt_published
                    })
            except:
                pass
                
        time.sleep(0.5) # Mala pauza da ne preopteretimo servere
        
    my_bar.empty() # Makni loading bar kad završi
    
    # Sortiraj od najnovijeg prema najstarijem
    final_output.sort(key=lambda x: x['dt'], reverse=True)
    return final_output

# --- PRIKAZ REZULTATA ---
vijesti = fetch_hybrid_news()

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} najnovijih objava!")
    for v in vijesti:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.write(f"🏷️ **{v['category']}**")
                st.caption(f"📰 Izvor: **{v['source']}**")
                st.caption(f"🕒 {v['date']}")
            with col2:
                st.markdown(f"#### [{v['title']}]({v['link']})")
                st.write(f"🔎 **Analiza:** {v['summary']}")
            st.divider()
else:
    st.info("Trenutno nema novih vijesti (zadnja 3 dana).")

if st.button("Skeniraj internet odmah (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()
