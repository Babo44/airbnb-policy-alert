import streamlit as st
from tavily import TavilyClient
from openai import OpenAI
from datetime import datetime, timedelta

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb PA & GR Tracker", page_icon="🏛️", layout="wide")

# --- SUSTAV PRIJAVE (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.title("🔒 Airbnb PA & GR Portal")
        password = st.text_input("Unesite lozinku za pristup:", type="password")
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

# --- INICIJALIZACIJA KLIJENATA ---
tavily = TavilyClient(api_key=st.secrets["TAVILY_API_KEY"])
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🏛️ Airbnb Public Affairs & GR Tracker")
st.markdown(f"**Status:** Skeniranje regulatornih kretanja i objava Vlade RH (Zadnja **3 dana**)")
st.divider()

# --- FUNKCIJA ZA PAMETNU PRETRAGU I ANALIZU ---
@st.cache_data(ttl=timedelta(hours=6)) # Osvježava se 4 puta dnevno
def run_gr_intelligence():
    # Fokusirani upiti za brzi pregled zadnja 3 dana
    queries = [
        "Sjednica Nacionalnog vijeća za razvoj turizma Hrvatska vijesti",
        "Zakon o upravljanju i održavanju zgrada apartmani novosti",
        "Ministarstvo turizma i sporta Tonči Glavina izjave danas",
        "HTZ najnoviji podaci turizam",
        "Hrvatska udruga obiteljskog smještaja vijesti",
        "Porez na nekretnine iznajmljivači najave"
    ]
    
    all_results = []
    
    for q in queries:
        # Pretražujemo samo najnovije (zadnja 3 dana se filtriraju kroz AI i Tavily 'advanced')
        search_result = tavily.search(
            query=q, 
            search_depth="advanced", 
            max_results=5,
            search_context=True
        )
        all_results.extend(search_result['results'])
    
    unique_results = {res['url']: res for res in all_results}.values()
    final_alerts = []
    
    for item in unique_results:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ti si Senior Public Affairs Manager za Airbnb. Tvoj zadatak je filtrirati vijesti i dati kratku GR analizu."},
                    {"role": "user", "content": f"""Analiziraj ovaj tekst. Ako se radi o oglasu, staroj vijesti ili nebitnoj temi, odgovori 'NE'. 
                    Ako je vijest bitna i objavljena/aktualna u zadnja 3 dana, odgovori u formatu:
                    DA | [Kategorija] | [Kratka GR analiza]
                    
                    Tekst: {item['title']} - {item['content']}"""}
                ],
                max_tokens=200,
                temperature=0
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer.upper().startswith("DA"):
                parts = answer.split("|")
                category = parts[1].strip() if len(parts) > 1 else "General"
                gr_insight = parts[2].strip() if len(parts) > 2 else "Relevantno za poslovanje."
                
                final_alerts.append({
                    "title": item['title'],
                    "url": item['url'],
                    "category": category,
                    "insight": gr_insight
                })
        except:
            continue
            
    return final_alerts

# --- PRIKAZ PODATAKA ---
with st.spinner("Skeniram najnovije objave (zadnja 3 dana)..."):
    alerts = run_gr_intelligence()

if alerts:
    st.success(f"Pronađeno {len(alerts)} relevantnih tema u zadnja 3 dana.")
    for alert in alerts:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.write(f"🏷️ **{alert['category']}**")
            with col2:
                st.markdown(f"#### [{alert['title']}]({alert['url']})")
                st.write(f"🏛️ **GR Analiza:** {alert['insight']}")
            st.divider()
else:
    st.info("Nema novih kritičnih kretanja u zadnja 3 dana. Sustav je čist.")

if st.button("Prisili osvježavanje podataka"):
    st.cache_data.clear()
    st.rerun()
