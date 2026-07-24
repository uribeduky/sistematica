import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Configuration
st.set_page_config(
    page_title="Sistemática Comercial IEP - Asset Management",
    page_icon="📊",
    layout="wide"
)

# Styling
st.markdown("""
<style>
    .main-header {
        font-size: 24px;
        font-weight: bold;
        color: #1F497D;
        margin-bottom: 20px;
    }
    .stMetric {
        background-color: #F8FAFC;
        padding: 12px;
        border-radius: 6px;
        border-left: 4px solid #1F497D;
    }
</style>
""", unsafe_allow_html=True)

# Directores
LISTA_DIRECTORES = [
    "Claudia Céspedez",
    "Claudia Lizarralde",
    "Gloria Lamus",
    "Karen Cortés",
    "Laura Gómez",
    "María Camila León",
    "Nicolás Quintero"
]

# Inicializar Base de Datos vacía (Comenzar de cero)
if "records" not in st.session_state:
    st.session_state.records = pd.DataFrame(columns=[
        "Fecha", "Mes_Año", "Director", "Tipo Cliente", "Canal", "Cierre"
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

# Capturar parámetros de la URL para separar accesos (Links)
query_params = st.query_params
mode = query_params.get("modo", "comercial") # 'comercial' o 'lider'

# Función de cálculo de métricas por mes
def compute_metrics(df, config):
    if df.empty:
        return pd.DataFrame()
    
    df_calc = df.copy()
    df_calc["Puntos_Canal"] = df_calc["Canal"].map({"Presencial": config["p_presencial"], "Virtual": config["p_virtual"]})
    df_calc["Puntos_Tipo"] = df_calc["Tipo Cliente"].map({"Nuevo (Captación)": config["p_captacion"], "Existente (Mantenimiento)": config["p_mantenimiento"]})
    df_calc["Puntos_Esfuerzo"] = df_calc["Puntos_Canal"] * df_calc["Puntos_Tipo"]
    df_calc["Es_Cierre"] = df_calc["Cierre"].apply(lambda x: 1 if x == "Sí" else 0)

    summary = df_calc.groupby("Director").agg(
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

# =============================================================
# MODO 1: PORTAL COMERCIAL (Para Directores)
# URL: ?modo=comercial (o sin parámetros)
# =============================================================
if mode == "comercial":
    st.title("👤 Portal Comercial - Registro de Visitas")
    st.caption("Herramienta de autocontrol comercial para Directores de Asset Management.")

    col_dir, col_mes_filter = st.columns([2, 1])
    with col_dir:
        selected_director = st.selectbox("Selecciona tu Nombre:", LISTA_DIRECTORES)

    st.subheader("📝 Registrar Nueva Visita Comercial")
    
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
        mes_str = fecha_visita.strftime("%Y-%m") # Guardar periodo Año-Mes
        new_row = pd.DataFrame([{
            "Fecha": str(fecha_visita),
            "Mes_Año": mes_str,
            "Director": selected_director,
            "Tipo Cliente": tipo_cliente,
            "Canal": canal,
            "Cierre": cierre
        }])
        st.session_state.records = pd.concat([st.session_state.records, new_row], ignore_index=True)
        st.success("¡Visita registrada exitosamente!")

    st.divider()
    
    # Filtro Mensual para el Director
    st.subheader(f"📌 Resumen Individual - {selected_director}")
    
    user_records_all = st.session_state.records[st.session_state.records["Director"] == selected_director]
    
    if not user_records_all.empty:
        meses_disponibles = sorted(user_records_all["Mes_Año"].unique(), reverse=True)
        selected_mes = st.selectbox("📅 Selecciona el Mes a consultar:", meses_disponibles, key="mes_user")
        
        user_records_month = user_records_all[user_records_all["Mes_Año"] == selected_mes]
        user_summary = compute_metrics(user_records_month, st.session_state.config)
        
        if not user_summary.empty:
            row = user_summary.iloc[0]
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Visitas Realizadas", int(row["Visitas_Totales"]))
            m2.metric("Puntos de Esfuerzo", f"{row['Puntos_Esfuerzo']:.1f} / {st.session_state.config['umbral_puntos']}")
            m3.metric("Factor Actividad", f"{row['Factor_Actividad']*100:.0f}%")
            m4.metric("Tasa Conversión", f"{row['Tasa_Conversion']*100:.1f}%")
            m5.metric("IEP Comercial", f"{row['IEP']*100:.1f}%", delta=row["Estatus"])
        
        st.caption(f"Detalle de visitas registradas en {selected_mes}:")
        st.dataframe(user_records_month[["Fecha", "Tipo Cliente", "Canal", "Cierre"]], use_container_width=True)
    else:
        st.info("Aún no tienes visitas registradas. Comienza guardando tu primera visita arriba.")

# =============================================================
# MODO 2: CONSOLA LÍDER COMERCIAL
# URL: ?modo=lider
# =============================================================
elif mode == "lider":
    st.title("👑 Consola de Liderazgo Comercial - Asset Management")
    st.caption("Consolidador de rendimiento global y calibración del modelo IEP.")

    tab1, tab2 = st.tabs(["📊 Dashboard de Rendimiento Global", "⚙️ Configuración de Parámetros"])

    with tab1:
        if not st.session_state.records.empty:
            meses_globales = sorted(st.session_state.records["Mes_Año"].unique(), reverse=True)
            col_mes, col_spacer = st.columns([1, 2])
            with col_mes:
                mes_global = st.selectbox("📅 Selecciona el Mes a Evaluar:", meses_globales)
            
            records_month = st.session_state.records[st.session_state.records["Mes_Año"] == mes_global]
            global_summary = compute_metrics(records_month, st.session_state.config)

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Total Visitas Equipo", int(global_summary["Visitas_Totales"].sum()))
            col_b.metric("Puntos Promedio Esfuerzo", f"{global_summary['Puntos_Esfuerzo'].mean():.1f}")
            col_c.metric("IEP Promedio Equipo", f"{global_summary['IEP'].mean()*100:.1f}%")
            col_d.metric("Cierres Totales Mes", int(global_summary["Cierres"].sum()))

            st.divider()
            st.subheader(f"📋 Rendimiento del Equipo - Período {mes_global}")

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
            st.info("No hay registros en la base de datos para mostrar acumulados.")

    with tab2:
        st.subheader("⚙️ Parámetros del Modelo")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.config["p_presencial"] = st.number_input("Puntos Visita Presencial", value=st.session_state.config["p_presencial"])
            st.session_state.config["p_virtual"] = st.number_input("Puntos Visita Virtual", value=st.session_state.config["p_virtual"])
            st.session_state.config["umbral_puntos"] = st.number_input("Umbral Mínimo Puntos (Esfuerzo)", value=st.session_state.config["umbral_puntos"])
        with c2:
            st.session_state.config["p_captacion"] = st.number_input("Multiplicador Cliente Nuevo", value=st.session_state.config["p_captacion"])
            st.session_state.config["p_mantenimiento"] = st.number_input("Multiplicador Cliente Existente", value=st.session_state.config["p_mantenimiento"])
            st.session_state.config["iep_objetivo"] = st.number_input("IEP Objetivo Mínimo (%)", value=st.session_state.config["iep_objetivo"] * 100) / 100.0
        st.success("Configuración actualizada.")
