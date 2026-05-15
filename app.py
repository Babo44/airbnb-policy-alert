import streamlit as st
from exa_py import Exa
from openai import OpenAI
from datetime import datetime, timedelta

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Airbnb GR Radar", page_icon="🏛️", layout="wide")

# --- SUSTAV PRIJAVE (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.title("🔒 Airbnb GR Radar - Prijava")
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

# --- INICIJALIZACIJA KLIJENATA ---
exa = Exa(api_key=st.secrets["EXA_API_KEY"])
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🏛️ Airbnb GR Radar (Exa Engine)")
st.markdown("Pametna semantička pretraga weba. **Exa API osigurava striktne datume (zadnja 3 dana).**")
st.divider()

# --- FUNKCIJA ZA DOHVAĆANJE (EXA MOTOR) ---
@st.cache_data(ttl=timedelta(hours=4))
def fetch_news_exa():
    # Poboljšani i prošireni upiti za Exa semantičku tražilicu
    queries = [
        "Airbnb Hrvatska kratkoročni najam",
        "Zakon o upravljanju i održavanju zgrada suglasnost",
        "Ministarstvo turizma i sporta ministar Tonči Glavina",
        "HTZ statistika turizam sezona",
        "Hrvatska udruga obiteljskog smještaja iznajmljivači",
        "porez na nekretnine Hrvatska najave",
        "Vlada RH turizam odluke",
        "vijesti turizam Hrvatska danas"
    ]
    
    # Računamo točan datum od prije 3 dana u formatu koji Exa razumije (YYYY-MM-DD)
    tri_dana_unazad = datetime.now() - timedelta(days=3)
    start_date_str = tri_dana_unazad.strftime('%Y-%m-%d')
    
    all_results = []
    
    progress_text = "Exa pretražuje web bazu..."
    my_bar = st.progress(0, text=progress_text)
    total_queries = len(queries)
    
    for i, q in enumerate(queries):
        my_bar.progress((i + 1) / total_queries, text=f"Exa analizira: {q}")
        try:
            search_response = exa.search_and_contents(
                q,
                type="neural",
                num_results=10, # Povećano na 10 rezultata po upitu za bolji ulov
                start_published_date=start_date_str
            )
            all_results.extend(search_response.results)
        except Exception as e:
            continue

    my_bar.empty()

    # Uklanjanje duplikata po URL-u
    unique_results = {res.url: res for res in all_results}.values()
    final_output = []
    
    for item in unique_results:
        # Exa šalje uredan datum objave
        raw_date = item.published_date
        dt_obj = None
        if raw_date:
            try:
                dt_obj = datetime.fromisoformat(raw_date.replace('Z', '').split('T')[0])
                clean_date = dt_obj.strftime('%d.%m.%Y.')
            except:
                clean_date = "Unutar zadnja 3 dana"
        else:
            clean_date = "Unutar zadnja 3 dana"

        source_name = item.url.split('/')[2].replace('www.', '')

        # --- AI FILTER ---
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ti si GR analitičar za Airbnb."},
                    {"role": "user", "content": f"""Analiziraj ovu vijest. 
                    ODBIJ (odgovori samo 'NE') ISKLJUČIVO ako se radi o direktnom oglasu za prodaju ili iznajmljivanje stana (Booking, Njuškalo, agencije), crnoj kronici ili sportu.
                    PRIHVATI sve ostale vijesti koje se tiču turizma, zakona, vlade, poreza ili stakeholdera u formatu: DA | [Kategorija] | [Kratki, informativni sažetak od 1-2 rečenice].
                    
                    Naslov: {item.title}
                    Sadržaj: {item.text}"""} 
                ],
                max_tokens=150,
                temperature=0
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer.upper().startswith("DA"):
                parts = answer.split("|")
                category = parts[1].strip() if len(parts) > 1 else "Turizam"
                summary = parts[2].strip() if len(parts) > 2 else "Pregledajte članak za detalje."
                
                final_output.append({
                    "title": item.title,
                    "url": item.url,
                    "source": source_name,
                    "date": clean_date,
                    "summary": summary,
                    "dt_obj": dt_obj or datetime.now()
                })
        except:
            continue
            
    # Sortiranje po datumu (najnovije na vrhu)
    final_output.sort(key=lambda x: x['dt_obj'], reverse=True)
    return final_output

# --- PRIKAZ ---
with st.spinner("Exa inteligencija obrađuje podatke..."):
    vijesti = fetch_news_exa()

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} relevantnih vijesti (strogo zadnja 72 sata).")
    for v in vijesti:
        with st.container():
            col_meta, col_main = st.columns([1, 4])
            with col_meta:
                st.write(f"🏷️ **{v['category']}**")
                st.write(f"📅 **{v['date']}**")
                st.caption(f"📰 {v['source']}")
            with col_main:
                st.markdown(f"#### [{v['title']}]({v['url']})")
                st.write(f"🔎 **Analiza:** {v['summary']}")
            st.divider()
else:
    st.info("U zadnja 3 dana Exa nije pronašla relevantne objave vezane uz vaše upite.")

if st.button("Osvježi bazu vijesti (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()
