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
st.markdown("Praćenje stakeholdera, zakona i statistike. **Strogi filter: Samo zadnja 3 dana.**")
st.divider()

# --- FUNKCIJA ZA DOHVAĆANJE ---
@st.cache_data(ttl=timedelta(hours=6))
def fetch_news_comprehensive():
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
    # Definiramo granicu od 3 dana (72 sata)
    tri_dana_unazad = datetime.now() - timedelta(days=3)
    danas_str = datetime.now().strftime("%d.%m.%Y.")
    
    for q in queries:
        search_result = tavily.search(
            query=q, 
            search_depth="advanced", 
            max_results=6, # Smanjeno s 8 kako bi pretraga bila brža i preciznija
            include_raw_content=False,
            include_images=False
        )
        all_results.extend(search_result['results'])
    
    unique_results = {res['url']: res for res in all_results}.values()
    final_output = []
    
    for item in unique_results:
        # --- 1. STROGI PYTHON FILTER DATUMA ---
        raw_date = item.get('published_date', None)
        clean_date = "Datum nije naveden"
        
        if raw_date:
            try:
                # Tavily vraća ISO format (npr. 2026-05-11T15:00:00Z)
                dt_published = datetime.fromisoformat(raw_date.replace('Z', '').split('.')[0])
                
                # Ako je vijest starija od 3 dana, odmah preskačemo!
                if dt_published < tri_dana_unazad:
                    continue 
                
                clean_date = dt_published.strftime('%d.%m.%Y.')
            except:
                pass # Ako pukne pretvaranje datuma, ostavljamo da AI odluči

        source_name = item['url'].split('/')[2].replace('www.', '')

        # --- 2. AI KALENDAR FILTER ---
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"Ti si analitičar vijesti za Airbnb. Danas je {danas_str}."},
                    {"role": "user", "content": f"""Analiziraj ovu vijest. 
                    ODBIJ (odgovori samo 'NE') u ova DVA slučaja:
                    1. Riječ je o oglasu za prodaju ili iznajmljivanje stana.
                    2. Iz teksta je očito da se radi o staroj vijesti koja NIJE iz zadnja 3 dana.
                    
                    PRIHVATI sve ostalo (DA | [Kratki sažetak od 1-2 rečenice]) ako se tiče stakeholdera, zakona, statistike ili Airbnb-a u zadnja 3 dana.
                    
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
with st.spinner("Skidamo samo najsvježije objave (zadnja 3 dana)..."):
    vijesti = fetch_news_comprehensive()

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} svježih vijesti (zadnja 72 sata).")
    for v in vijesti:
        with st.container():
            col_meta, col_main = st.columns([1, 4])
            with col_meta:
                st.write(f"📅 **{v['date']}**")
                st.caption(f"📰 {v['source']}")
            with col_main:
                st.markdown(f"#### [{v['title']}]({v['url']})")
                st.write(v['summary'])
            st.divider()
else:
    st.info("U zadnja 3 dana nema relevantnih vijesti vezanih za zadane stakeholdere i ključne riječi.")

if st.button("Osvježi bazu vijesti (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()
