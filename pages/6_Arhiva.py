import streamlit as st
from utils import start, CLIENTS, ZASTAVE, arhiva_lista, arhiva_biljeska, arhiva_obrisi

start()
st.title("Arhiva")

nazivi = ["Sve"] + [c["naziv"] for c in CLIENTS.values()]
filtar = st.selectbox("Klijent", nazivi)

stavke = arhiva_lista(None if filtar == "Sve" else filtar)
st.caption(f"{len(stavke)} spremljenih vijesti")
st.divider()

if not stavke:
    st.info("Arhiva je prazna. Vijesti spremate gumbom Arhiviraj.")

for a in stavke:
    zastava = ZASTAVE.get(a.get("zemlja"), "🌍")
    with st.container(border=True):
        st.markdown(f"##### [{a['naslov']}]({a['url']})")
        st.caption(
            f"{zastava} {a.get('zemlja', '')}  ·  {a.get('datum', '')}  ·  "
            f"{a.get('izvor', '')}  ·  {a.get('klijent', '')}  ·  relevantnost {a.get('relevantnost', '')}"
        )
        st.write(a.get("sazetak", ""))

        bil = st.text_area("Bilješka", value=a.get("biljeska") or "", key=f"bil_{a['url']}", height=80)
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Spremi bilješku", key=f"spremi_{a['url']}"):
                arhiva_biljeska(a["url"], bil)
                st.toast("Bilješka spremljena")
        with c2:
            if st.button("Ukloni iz arhive", key=f"obrisi_{a['url']}"):
                arhiva_obrisi(a["url"])
                st.rerun()
