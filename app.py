import streamlit as st
from utils import page_setup, check_password, CLIENTS, DANA_UNAZAD, MIN_RELEVANTNOST

page_setup()
if not check_password():
    st.stop()

st.title("Praćenje vijesti")
st.write(
    f"Zadnjih {DANA_UNAZAD} dana · prag relevantnosti {MIN_RELEVANTNOST} · "
    "rezultati se osvježavaju svakih 6 sati."
)
st.divider()

for path, naziv in [
    ("pages/1_Airbnb.py", "Airbnb"),
    ("pages/2_Huawei.py", "Huawei"),
    ("pages/3_WEYTEC.py", "WEYTEC"),
    ("pages/4_Envoid.py", "Envoid"),
]:
    st.page_link(path, label=naziv)
