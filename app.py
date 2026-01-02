import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="COPOLT SmartFarm",
    page_icon="🐷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PERSONALIZADOS (LOOK & FEEL CORPORATIVO) ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIMULACIÓN DE DATOS ---
def get_sensor_data():
    return pd.DataFrame({
        'Hora': pd.date_range(start='08:00', periods=10, freq='H').strftime('%H:%M'),
        'Temperatura': np.random.uniform(20, 28, 10),
        'Humedad': np.random.uniform(50, 70, 10),
        'Amoniaco': np.random.uniform(5, 15, 10)
    })

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image("https://via.placeholder.com/300x100.png?text=COPOLT+Technology", use_container_width=True)
    st.markdown("---")
    menu = st.radio("Navegación", ["📊 Dashboard General", "🐷 Porcicultura", "🐔 Avicultura", "⚙️ Configuración"])
    
    st.markdown("---")
    st.info("Estado del Sistema: **ONLINE** 🟢")
    st.caption("v1.2.0 | Conectado a Servidor Chile")

# --- PÁGINA PRINCIPAL ---
st.title("🚜 COPOLT SmartFarm Platform")
st.markdown("Sistema integral de gestión y monitoreo IoT.")

if menu == "📊 Dashboard General":
    # KPIs Superiores
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Granjas Activas", "3", "Estable")
    col2.metric("Total Animales", "12,450", "+520 esta semana")
    col3.metric("Alertas Activas", "1", "-2 vs ayer", delta_color="inverse")
    col4.metric("Eficiencia Energética", "94%", "+2%")

    # Gráficos
    st.subheader("📡 Telemetría en Tiempo Real (Últimas 24h)")
    data = get_sensor_data()
    
    tab1, tab2 = st.tabs(["🌡️ Temperatura & Humedad", "⚠️ Niveles de Gases"])
    
    with tab1:
        fig = px.line(data, x='Hora', y=['Temperatura', 'Humedad'], markers=True, 
                     title="Condiciones Ambientales Promedio")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.warning("⚠️ Alerta: El nivel de Amoniaco subió ligeramente en el Galpón 3 a las 14:00 hrs.")
        fig2 = px.bar(data, x='Hora', y='Amoniaco', color='Amoniaco', 
                     title="Concentración de NH3 (ppm)", color_continuous_scale='Reds')
        st.plotly_chart(fig2, use_container_width=True)

elif menu == "🐷 Porcicultura":
    st.subheader("Gestión de Planteles Porcinos")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.success("✅ Ciclo de Engorde: Lote P-2024")
        st.write("**Días de vida:** 45 días")
        st.write("**Peso Promedio:** 22.5 kg")
        st.write("**Conversión Alimenticia:** 1.4")
        st.button("Ver Detalle del Lote", type="primary")
    
    with col2:
        st.dataframe(pd.DataFrame({
            "Galpón": ["G1 - Maternidad", "G2 - Recría", "G3 - Engorde"],
            "Temperatura": ["24°C", "22°C", "20°C"],
            "Estado": ["Normal", "Normal", "Alerta Térmica"],
            "Acción": ["Ninguna", "Ninguna", "Revisar Ventilación"]
        }), use_container_width=True)

elif menu == "🐔 Avicultura":
    st.subheader("Control Avícola (Broilers)")
    st.info("Módulo conectado a COPOLT Climate Controller v2")
    st.metric("Índice de Mortalidad Actual", "1.2%", "Bajo el estándar (Obj: <3%)")

elif menu == "⚙️ Configuración":
    st.header("Ajustes del Sistema")
    st.text_input("Token de API COPOLT", value="sk_live_51M...")
    st.slider("Umbral de Alerta Temperatura (°C)", 15, 35, 28)
    st.checkbox("Activar notificaciones por WhatsApp", value=True)
    st.button("Guardar Cambios")

# --- FOOTER ---
st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>© 2026 COPOLT Tecnología. Desarrollado en Chile.</div>", unsafe_allow_html=True)
