import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Page configuration
st.set_page_config(
    page_title="Gestión Comercial IEP - Asset Management",
    page_icon="📊",
    layout="wide"
)

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 24px;
        font-weight: bold;
        color: #1F497D;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-left: 5px solid #1F497D;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State Data
if "records" not in st.session_state:
    st.session_state.records = pd.DataFrame([
        {"Fecha": "2026-07-01", "Director": "Carlos Mendoza", "Tipo Cliente": "Nuevo (Captación)", "Canal": "Presencial", "Cierre": "Sí"},
        {"Fecha": "2026-07-03", "Director": "Carlos Mendoza", "Tipo Cliente": "Nuevo (Captación)", "Canal": "Presencial", "Cierre": "No"},
        {"Fecha": "2026-07-05", "Director": "Carlos Mendoza", "Tipo Cliente": "Existente (Mantenimiento)", "Canal": "Virtual", "Cierre": "No"},
        {"Fecha": "2026-07-10", "Director": "Carlos Mendoza", "Tipo Cliente": "Nuevo (Captación)", "Canal": "Virtual", "Cierre": "Sí"},
        {"Fecha": "2026-07-02", "Director": "Ana María Rojas", "Tipo Cliente": "Existente (Mantenimiento)", "Canal": "Presencial", "Cierre": "Sí"},
        {"Fecha": "2026-07-04", "Director": "Ana María Rojas", "Tipo Cliente": "Existente (Mantenimiento)", "Canal": "Presencial", "Cierre": "No"},
        {"Fecha": "2026-07-08", "Director": "Ana María Rojas", "Tipo Cliente": "Nuevo (Captación)", "Canal": "Presencial", "Cierre": "Sí"},
        {"Fecha": "2026-07-12", "Director": "Ana María Rojas", "Tipo Cliente": "Existente (Mantenimiento)", "Canal": "Virtual", "Cierre": "No"},
        {"Fecha": "2026-07-15", "Director": "Ana María Rojas", "Tipo Cliente": "Nuevo (Captación)", "Canal": "Presencial", "Cierre": "Sí"},
    ])

if "config" not in st.session_state:
    st.session_state.config = {
        "p_presencial": 1.0,
        "p_virtual": 0.6,
        "p_captacion": 1.5,
        "p_mantenimiento": 0.8,
        "umbral_puntos": 15.0,
        "iep_objetivo": 0.15
    }

# App Title & Navigation
st.title("📊 Portal de Control Comercial IEP - Asset Management")
st.caption("Plataforma en línea para registro individual de gestores y consola de control del Líder Comercial.")

role = st.sidebar.radio("📌 Selecciona tu Vista:", ["👤 Registro Comercial (Director)", "📈 Dashboard Global (Líder / Director General)", "⚙️ Configuración del Modelo"])

# Helper function to compute metrics
def compute_metrics(df, config):
    if df.empty:
        return pd.DataFrame()
    
    # Calculate points per row
    df["Puntos_Canal"] = df["Canal"].map({"Presencial": config["p_presencial"], "Virtual": config["p_virtual"]})
    df["Puntos_Tipo"] = df["Tipo Cliente"].map({"Nuevo (Captación)": config["p_captacion"], "Existente (Mantenimiento)": config["p_mantenimiento"]})
    df["Puntos_Esfuerzo"] = df["Puntos_Canal"] * df["Puntos_Tipo"]
    df["Es_Cierre"] = df["Cierre"].apply(lambda x: 1 if x == "Sí" else 0)

    # Group by Director
    summary = df.groupby("Director").agg(
        Visitas_Totales=("Fecha", "count"),
        Visitas_Presenciales=("Canal", lambda x: (x == "Presencial").sum()),
        Visitas_Virtuales=("Canal", lambda x: (x == "Virtual").sum()),
        Visitas_Nuevos=("Tipo Cliente", lambda x: (x == "Nuevo (Captación)").sum()),
        Visitas_Existentes=("Tipo Cliente", lambda x: (x == "Existente (Mantenimiento)").sum()),
        Puntos_Esfuerzo=("Puntos_Esfuerzo", "sum"),
        Cierres=("Es_Cierre", "sum")
    ).reset_index()

    summary["Factor_Actividad"] = summary["Puntos_Esfuerzo"].apply(lambda pts: min(1.0, pts / config["umbral_puntos"]))
    summary["Tasa_Conversion"] = summary["Cierres"] / summary["Visitas_Totales"].replace(0, 1)
    summary["IEP"] = summary["Tasa_Conversion"] * summary["Factor_Actividad"]
    summary["Estatus"] = summary["IEP"].apply(lambda x: "🟢 CUMPLE IEP" if x >= config["iep_objetivo"] else "🔴 BAJO OBJETIVO")

    return summary

# -------------------------------------------------------------
# VISTA 1: REGISTRO COMERCIAL (DIRECTOR)
# -------------------------------------------------------------
if role == "👤 Registro Comercial (Director)":
    st.subheader("📝 Registrar Nueva Visita Comercial")
    
    directores = ["Carlos Mendoza", "Ana María Rojas", "Roberto Gómez", "Laura Silva"]
    selected_director = st.selectbox("Selecciona tu Nombre:", directores)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        fecha_visita = st.date_input("Fecha de Visita", datetime.date.today())
    with col2:
        tipo_cliente = st.selectbox("Tipo de Cliente", ["Nuevo (Captación)", "Existente (Mantenimiento)"])
    with col3:
        canal = st.selectbox("Canal de Reunión", ["Presencial", "Virtual"])
    with col4:
        cierre = st.selectbox("¿Ocurrió Cierre / Venta?", ["No", "Sí"])

    if st.button("💾 Guardar Visita"):
        new_row = pd.DataFrame([{
            "Fecha": str(fecha_visita),
            "Director": selected_director,
            "Tipo Cliente": tipo_cliente,
            "Canal": canal,
            "Cierre": cierre
        }])
        st.session_state.records = pd.concat([st.session_state.records, new_row], ignore_index=True)
        st.success("¡Visita registrada exitosamente!")

    st.divider()
    st.subheader(f"📌 Resumen Mensual Individual - {selected_director}")
    
    # Filter data for selected director
    user_records = st.session_state.records[st.session_state.records["Director"] == selected_director]
    user_summary = compute_metrics(user_records, st.session_state.config)
    
    if not user_summary.empty:
        row = user_summary.iloc[0]
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Visitas Realizadas", int(row["Visitas_Totales"]))
        m2.metric("Puntos de Esfuerzo", f"{row['Puntos_Esfuerzo']:.1f} / {st.session_state.config['umbral_puntos']}")
        m3.metric("Factor Actividad", f"{row['Factor_Actividad']*100:.0f}%")
        m4.metric("Tasa Conversión", f"{row['Tasa_Conversion']*100:.1f}%")
        m5.metric("IEP Comercial", f"{row['IEP']*100:.1f}%", delta=row["Estatus"])
    else:
        st.info("Aún no tienes visitas registradas este mes.")

    st.caption("Detalle de tus visitas registradas:")
    st.dataframe(user_records, use_container_width=True)

# -------------------------------------------------------------
# VISTA 2: DASHBOARD GLOBAL (LÍDER)
# -------------------------------------------------------------
elif role == "📈 Dashboard Global (Líder / Director General)":
    st.subheader("👑 Consolidador y Seguimiento del Equipo Comercial")
    
    global_summary = compute_metrics(st.session_state.records, st.session_state.config)
    
    if not global_summary.empty:
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Total Visitas Equipo", int(global_summary["Visitas_Totales"].sum()))
        col_b.metric("Puntos Promedio Esfuerzo", f"{global_summary['Puntos_Esfuerzo'].mean():.1f}")
        col_c.metric("IEP Promedio Equipo", f"{global_summary['IEP'].mean()*100:.1f}%")
        col_d.metric("Cierres Totales Mes", int(global_summary["Cierres"].sum()))
        
        st.divider()
        st.subheader("📋 Tabla de Posiciones y Rendimiento Comercial (IEP)")
        
        display_df = global_summary[[
            "Director", "Visitas_Totales", "Visitas_Presenciales", "Visitas_Virtuales",
            "Visitas_Nuevos", "Visitas_Existentes", "Puntos_Esfuerzo", "Factor_Actividad",
            "Cierres", "Tasa_Conversion", "IEP", "Estatus"
        ]].copy()
        
        display_df["Factor_Actividad"] = (display_df["Factor_Actividad"] * 100).round(1).astype(str) + "%"
        display_df["Tasa_Conversion"] = (display_df["Tasa_Conversion"] * 100).round(1).astype(str) + "%"
        display_df["IEP"] = (display_df["IEP"] * 100).round(1).astype(str) + "%"
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("No hay registros en la base de datos.")

# -------------------------------------------------------------
# VISTA 3: CONFIGURACIÓN
# -------------------------------------------------------------
elif role == "⚙️ Configuración del Modelo":
    st.subheader("⚙️ Parámetros y Reglas del Modelo Comercial")
    
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.config["p_presencial"] = st.number_input("Puntos Visita Presencial", value=st.session_state.config["p_presencial"])
        st.session_state.config["p_virtual"] = st.number_input("Puntos Visita Virtual", value=st.session_state.config["p_virtual"])
        st.session_state.config["umbral_puntos"] = st.number_input("Umbral Mínimo Puntos (Esfuerzo)", value=st.session_state.config["umbral_puntos"])
    with c2:
        st.session_state.config["p_captacion"] = st.number_input("Multiplicador Cliente Nuevo", value=st.session_state.config["p_captacion"])
        st.session_state.config["p_mantenimiento"] = st.number_input("Multiplicador Cliente Existente", value=st.session_state.config["p_mantenimiento"])
        st.session_state.config["iep_objetivo"] = st.number_input("IEP Objetivo Mínimo (%)", value=st.session_state.config["iep_objetivo"] * 100) / 100.0

    st.success("Configuración actualizada correctamente.")
