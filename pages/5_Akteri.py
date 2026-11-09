import streamlit as st
from utils import start, CLIENTS, fetch_akteri, prikazi_vijesti

start()
st.title("Akteri")
st.caption("Vijesti o ljudima i institucijama koje pratite, zadnja tri dana")

klijent = st.selectbox("Klijent", list(CLIENTS), format_func=lambda k: CLIENTS[k]["naziv"])
cfg = CLIENTS[klijent]

izbor = st.multiselect("Akteri", cfg["akteri"], default=cfg["akteri"][:3])
dodatni = st.text_input("Dodatni akteri (odvojeni zarezom)")
svi = izbor + [x.strip() for x in dodatni.split(",") if x.strip()]
svi = tuple(svi[:8])

if not svi:
    st.info("Odaberite barem jednog aktera.")
    st.stop()

with st.spinner("Pretražujem…"):
    r = fetch_akteri(klijent, svi)

st.caption(f"Dohvaćeno {r['dohvaceno']}  ·  prikazano {len(r['vijesti'])}")
st.divider()

if not r["vijesti"]:
    st.info("Nema relevantnih objava za odabrane aktere.")
else:
    prikazi_vijesti(r["vijesti"], cfg["naziv"], prefix=f"akt_{klijent}")
