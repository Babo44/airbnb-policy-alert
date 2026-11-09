import streamlit as st
from utils import page_setup, check_password, render_client_page

page_setup()
if not check_password():
    st.stop()
render_client_page("huawei")
