import streamlit as st
from exa_py import Exa
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

# --- INICIJALIZACIJA KLIJENATA ---
exa = Exa(api_key=st.secrets["EXA_API_KEY"])
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🏠 Airbnb vijesti")
st.markdown("Praćenje stakeholdera, zakona i statistike. **Exa API osigurava striktne datume (zadnja 3 dana).**")
st.divider()

# --- FUNKCIJA ZA DOHVAĆANJE (EXA MOTOR) ---
@st.cache_data(ttl=timedelta(hours=6))
def fetch_news_exa():
    queries = [
        "najnovije vijesti Airbnb i kratkoročni najam u Hrvatskoj",
        "Zakon o upravljanju i održavanju zgrada suglasnost susjeda",
        "Ministarstvo turizma i sporta ministar Tonči Glavina objave",
        "Hrvatska turistička zajednica HTZ statistika turizam",
        "Hrvatska udruga obiteljskog smještaja ili Glas poduzetnika iznajmljivači",
        "porez na nekretnine Hrvatska novosti"
        "Vlada turizam"
        "iznajmljivači"
    ]
    
    # Računamo točan datum od prije 3 dana u formatu koji Exa razumije (YYYY-MM-DD)
    tri_dana_unazad = datetime.now() - timedelta(days=3)
    start_date_str = tri_dana_unazad.strftime('%Y-%m-%d')
    
    all_results = []
    
    for q in queries:
        try:
            # OBRISAN 'use_autoprompt' parametar
            search_response = exa.search_and_contents(
                q,
                type="neural",
                num_results=5,
                start_published_date=start_date_str
            )
            all_results.extend(search_response.results)
        except Exception as e:
            st.error(f"Greška pri dohvaćanju Exa rezultata: {e}")
            continue

    # Uklanjanje duplikata po URL-u
    unique_results = {res.url: res for res in all_results}.values()
    final_output = []
    
    for item in unique_results:
        raw_date = item.published_date
        if raw_date:
            try:
                clean_date = datetime.fromisoformat(raw_date.replace('Z', '').split('T')[0]).strftime('%d.%m.%Y.')
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
                    {"role": "system", "content": "Ti si analitičar vijesti za Airbnb."},
                    {"role": "user", "content": f"""Analiziraj ovu vijest. ODBIJ (odgovori samo 'NE') ISKLJUČIVO ako se radi o direktnom oglasu za prodaju ili iznajmljivanje stana/apartmana (Booking, Njuškalo, agencije).
                    PRIHVATI sve ostale vijesti koje se tiču turizma, zakona, poreza ili stakeholdera u formatu: DA | [Kratki, informativni sažetak od 2 rečenice].
                    
                    Naslov: {item.title}
                    Sadržaj: {item.text}"""}
                ],
                max_tokens=150,
                temperature=0
            )
            
            answer = response.choices[0].message.content.strip()
            
            if answer.upper().startswith("DA"):
                summary = answer.split("|")[1].strip() if "|" in answer else "Pregledajte članak za detalje."
                final_output.append({
                    "title": item.title,
                    "url": item.url,
                    "source": source_name,
                    "date": clean_date,
                    "summary": summary
                })
        except:
            continue
            
    return final_output

# --- PRIKAZ ---
with st.spinner("Exa pretražuje bazu (garantirano zadnja 3 dana)..."):
    vijesti = fetch_news_exa()

if vijesti:
    st.success(f"Pronađeno je {len(vijesti)} relevantnih vijesti (strogo zadnja 72 sata).")
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
    st.info("U zadnja 3 dana nema relevantnih objava vezanih uz vaše upite.")

if st.button("Osvježi bazu vijesti (Clear Cache)"):
    st.cache_data.clear()
    st.rerun()
