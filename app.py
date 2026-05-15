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

st.title("⚡ Airbnb Real-Time Radar (Najnovije vijesti)")
st.markdown("Sustav forsira kronološki prikaz i filtrira isključivo **zadnja 3 dana**.")
st.divider()

def scrape_article_text(url):
    """Funkcija za čitanje teksta s portala uz zaobilaženje osnovnih prepreka."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        return text[:1500] if text else "Nema teksta."
    except:
        return "Nije moguće pročitati tekst."

@st.cache_data(ttl=timedelta(hours=2))
def fetch_hybrid_news():
    # Ažurirana lista ključnih riječi s novim upitima
    queries = [
        "Airbnb Hrvatska",
        "kratkoročni najam apartmani",
        "Zakon o upravljanju zgradama",
        "Ministarstvo turizma iznajmljivači",
        "HTZ turizam",
        "porez na nekretnine Hrvatska",
        "vijesti turizam Hrvatska danas",
        "Vlada turizam",
        "iznajmljivači"
    ]
    
    tri_dana_unazad = datetime.now() - timedelta(days=3)
    seen_links = set()
    final_output = []
    
    stats = {"raw": 0, "passed_date": 0, "passed_ai": 0}
    
    progress_text = "Skeniram najnovije objave s portala..."
    my_bar = st.progress(0, text=progress_text)
    total_queries = len(queries)

    for i, query in enumerate(queries):
        my_bar.progress((i + 1) / total_queries, text=f"Tražim: {query}")
        
        encoded_query = urllib.parse.quote_plus(query)
        # TAJNI PARAMETAR: &tbs=sbd:1 sortira rezultate striktno po vremenu objave (od najnovijeg)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr&tbs=sbd:1"
        feed = feedparser.parse(rss_url)
        
        # Vučemo maksimalnih 100 rezultata po upitu umjesto 60!
        entries = feed.entries[:100]
        stats["raw"] += len(entries)
        
        for entry in entries: 
            link = entry.link
            if link in seen_links:
                continue
            seen_links.add(link)

            pub_date_parsed = entry.get('published_parsed')
            if pub_date_parsed:
                dt_published = datetime.from
