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

st.title("⚡ Airbnb Real-Time Radar (Fokus na svježinu)")
st.markdown("Pretraga prisiljena na najnovije vijesti. Prikazuje strogo **zadnja 3 dana**.")
st.divider()

def scrape_article_text(url):
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
    # Dodali smo šire pojmove (Vlada RH, Sabor, općenito turizam) da uhvatimo dnevnu politiku
    queries = [
        "Airbnb Hrvatska",
        "kratkoročni najam apartmani",
        "Zakon o upravljanju zgradama",
        "Ministarstvo turizma",
        "HTZ turizam",
        "porez na nekretnine Hrvatska",
        "Vlada RH turizam",
        "Sabor turizam",
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
        
        # Ovdje je ključ: Dodajemo " when:3d" direktno u upit da Google izbaci stare vijesti
        encoded_query = urllib.parse.quote_plus(f"{query} when:3d")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=hr&gl=HR&ceid=HR:hr"
        feed = feedparser.parse(rss_url)
        
        stats["raw"] += len(feed.entries)
        
        for entry in feed.entries[:15]: 
            link = entry.link
            if link in seen_links:
                continue
            seen_links.add(link)

            pub_date_parsed = entry.get('published_parsed')
            if pub_date_parsed:
                dt_published = datetime.fromtimestamp(time.mktime(pub_date_parsed))
                # Python osigurač da nešto ipak ne prođe ispod radara
                if dt_published < tri_dana_unazad:
                    continue
                date_str = dt_published.strftime("%d.%m.%Y. u %H:%M")
            else:
                continue
                
            stats["passed_date"] += 1

            article_text = scrape_article_text(link)
            if len(article_text) < 100 or "kolačić" in article_text.lower() or "cookie" in article_text.lower() or "pretplatite" in article_text.lower():
                article_text = entry.get('description', entry.title)

            source = entry.title.rsplit(" - ", 1)[1] if " - " in entry.title else "Nepoznat izvor"
            clean_title = entry.title.rsplit(" - ", 1)[0] if " - " in entry.title else entry.title

            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ti si GR analitičar za Airbnb."},
                        {"role": "user", "content": f"""Analiziraj ovu vijest. 
                        ODBIJ (odgovori samo 'NE') isključivo ako se radi o direktnom oglasu za rezervaciju stana, crnoj kronici ili sportu.
                        PRIHVATI apsolutno sve ostalo o turizmu, ministarstvu, iznajmljivačima, ekonomiji, Vladi RH ili zakonima.
                        
                        Odgovori točno u formatu: DA | [Kategorija] | [Sažetak od 1 rečenice].
                        
                        Naslov: {clean_title}
                        Sadržaj: {article_text}"""}
                    ],
                    max_tokens=150,
                    temperature=0
                )
                
                answer = response.choices[0].message.content.strip()
                
                if answer.upper().startswith("DA"):
                    stats["passed_ai"] += 1
                    parts = answer.split("|")
                    category = parts[1].strip() if len(parts) > 1 else "Turizam"
                    summary = parts[2].strip() if len(parts) > 2 else "Relevantna vijest o turizmu."
                    
                    final_output.append({
                        "title": clean_title, "link": link, "source": source, 
                        "date": date_str, "category": category, "summary": summary, "dt": dt_published
                    })
            except:
                pass
                
        time.sleep(0.5)
        
    my_bar.empty()
    final_output.sort(key=lambda x: x['dt'], reverse=True)
    return final_output, stats

# --- PRIKAZ REZULTATA ---
vijesti, statistika = fetch_hybrid_news()

st.info(f"🕵️ **Detektivski Info:** Google našao: **{statistika['raw']}** | Mlađe od 3 dana: **{statistika['passed_date']}** | AI odobrio: **{statistika['passed_ai']}**")

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} najnovijih objava (u zadnja 3 dana)!")
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
    st.warning("U zadnja 72 sata nitko u medijima nije objavio vijest koja sadrži zadane ključne riječi.")

if st.button("Skeniraj internet odmah (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()
