import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ---------------- CONFIGURACIÓN GENERAL ----------------
st.set_page_config(
    page_title="COPOLT SmartFarm",
    page_icon="🐷",
    layout="wide"
)

# ---------------- HEADER ----------------
st.title("🐷🐔 COPOLT SmartFarm")
st.subheader("Plataforma digital de gestión porcina y avícola")
st.caption("Demo funcional – MVP SaaS | Chile 🇨🇱")

st.divider()

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Panel de Control")
granja = st.sidebar.selectbox(
    "Selecciona Granja",
    ["Granja Porcina Norte", "Granja Avícola Sur"]
)

lote = st.sidebar.selectbox(
    "Selecciona Lote",
    ["Lote A-2025", "Lote B-2025"]
)

fecha = st.sidebar.date_input("Fecha", datetime.today())

st.sidebar.success("🟢 Sistema Operativo")

# ---------------- KPIs ----------------
st.subheader("📊 Indicadores Clave (KPIs)")

col1, col2, col3, col4 = st.columns(4)

col1.metric("🌡 Temperatura", "22.5 °C", "+0.5")
col2.metric("💧 Humedad", "63 %", "-2")
col3.metric("🐖 Animales", "1.240", "+12")
col4.metric("⚠️ Alertas Activas", "1", "-1")

st.divider()

# ---------------- DATOS SIMULADOS IOT ----------------
st.subheader("📡 Monitoreo Ambiental (IoT – Simulado)")

data = {
    "Hora": ["08:00", "10:00", "12:00", "14:00", "16:00"],
    "Temperatura (°C)": [21.5, 22.1, 23.0, 22.7, 22.4],
    "Humedad (%)": [65, 63, 60, 62, 64]
}

df = pd.DataFrame(data)

col5, col6 = st.columns(2)

with col5:
    fig_temp = px.line(
        df,
        x="Hora",
        y="Temperatura (°C)",
        title="Temperatura Ambiente"
    )
    st.plotly_chart(fig_temp, use_container_width=True)

with col6:
    fig_hum = px.line(
        df,
        x="Hora",
        y="Humedad (%)",
        title="Humedad Relativa"
    )
    st.plotly_chart(fig_hum, use_container_width=True)

# ---------------- TABLA ----------------
st.subheader("📋 Registro Operacional")
st.dataframe(df, use_container_width=True)

# ---------------- ALERTAS ----------------
st.subheader("🚨 Alertas Inteligentes")

st.warning("⚠️ Humedad fuera de rango en Galpón 2 (63%)")

# ---------------- SOPORTE ----------------
st.divider()
st.subheader("🆘 Soporte y Asistencia")

if st.button("Solicitar Soporte Técnico"):
    st.info("📩 Solicitud enviada al equipo COPOLT")

# ---------------- FOOTER ----------------
st.divider()
st.caption(
    "© 2026 COPOLT SmartFarm | Demo desarrollada por vibecodingchile"
)
