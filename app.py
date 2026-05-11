import streamlit as st
from tavily import TavilyClient
from openai import OpenAI
from datetime import datetime, timedelta

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb vijesti", page_icon="🏠", layout="wide")

# --- SUSTAV PRIJAVE (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.title("🔒 Airbnb vijesti - Prijava")
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

# --- INICIJALIZACIJA ---
tavily = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🏠 Airbnb vijesti")
st.markdown("Praćenje stakeholdera, zakona, statistike i kretanja na tržištu nekretnina i turizma.")
st.divider()

# --- FUNKCIJA ZA DOHVAĆANJE ---
@st.cache_data(ttl=timedelta(hours=6))
def fetch_news_comprehensive():
    # Široka lista upita za sve stakeholdere
    queries = [
        "Airbnb Hrvatska vijesti",
        "kratkoročni najam zakoni prijedlozi",
        "Ministarstvo turizma i sporta Tonči Glavina objave",
        "HTZ statistika istraživanja turizam",
        "Hrvatska udruga obiteljskog smještaja vijesti",
        "Zajednica obiteljskog turizma HGK",
        "Porez na nekretnine Hrvatska novosti",
        "Zakon o ugostiteljskoj djelatnosti izmjene",
        "Udruga Glas poduzetnika iznajmljivači"
    ]
    
    all_results = []
    for q in queries:
        search_result = tavily.search(
            query=q, 
            search_depth="advanced", 
            max_results=8, # Povećan broj rezultata
            include_raw_content=False,
            include_images=False
        )
        all_results.extend(search_result['results'])
    
    # Uklanjanje duplikata po URL-u
    unique_results = {res['url']: res for res in all_results}.values()
    
    final_output = []
    for item in unique_results:
        # Ekstrakcija datuma iz Tavily rezultata
        raw_date = item.get('published_date', None)
        if raw_date:
            try:
                # Pretvaramo ISO format u čitljiv datum
                clean_date = datetime.fromisoformat(raw_date.replace('Z', '')).strftime('%d.%m.%Y.')
            except:
                clean_date = "Nedavno"
        else:
            clean_date = "Datum nije naveden"

        source_name = item['url'].split('/')[2].replace('www.', '')

        try:
            # AI Analiza - sada vrlo popustljiva
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ti si analitičar vijesti za Airbnb. Tvoj zadatak je filtrirati samo OGLASE. Sve ostale vijesti o turizmu, zakonima, statistici i stakeholderima prihvati."},
                    {"role": "user", "content": f"""Analiziraj vijest. 
                    ODBIJ (odgovori samo 'NE') samo ako je riječ o direktnom oglasu za prodaju ili iznajmljivanje konkretnog stana/apartmana.
                    PRIHVATI sve ostalo (DA | [Kratki sažetak]) ako se radi o: Ministarstvu, HTZ-u, udrugama, zakonima, porezima ili trendovima.
                    
                    Naslov: {item['title']}
                    Sadržaj: {item['content']}"""}
                ],
                max_tokens=150,
                temperature=0
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer.upper().startswith("DA"):
                summary = answer.split("|")[1].strip() if "|" in answer else "Pregledajte članak za detalje."
                final_output.append({
                    "title": item['title'],
                    "url": item['url'],
                    "source": source_name,
                    "date": clean_date,
                    "summary": summary
                })
        except:
            continue
            
    return final_output

# --- PRIKAZ ---
with st.spinner("Prikupljam najnovije vijesti sa svih strana..."):
    vijesti = fetch_news_comprehensive()

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} vijesti u zadnjem periodu.")
    for v in vijesti:
        with st.container():
            col_meta, col_main = st.columns([1, 4])
            with col_meta:
                st.write(f"📅 {v['date']}")
                st.caption(f"📰 {v['source']}")
            with col_main:
                st.markdown(f"#### [{v['title']}]({v['url']})")
                st.write(v['summary'])
            st.divider()
else:
    st.info("Trenutno nema novih vijesti.")

if st.button("Osvježi bazu vijesti"):
    st.cache_data.clear()
    st.rerun()
