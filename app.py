import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests

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

DEFAULT_CONFIG = {
    "p_presencial": 1.0,
    "p_virtual": 0.6,
    "p_captacion": 1.5,
    "p_mantenimiento": 0.8,
    "umbral_puntos": 15.0,
    "iep_objetivo": 0.15
}

if "config" not in st.session_state:
    st.session_state.config = DEFAULT_CONFIG

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1c_3WF_RyzgtsHyr6MlPnVGYFvBfjveUIKCe6RRQdAws/export?format=csv"
WEBAPP_URL = "https://script.google.com/macros/s/AKfycby3KW1Fq_J0IDwCjcHd9RxY7w6ig6LHkPcxq9EIqpIfDjc56L6Zf_4cfexMqp7wlHJbmw/exec"

if "records" not in st.session_state:
    st.session_state.records = pd.DataFrame(columns=[
        "ID", "Fecha", "Mes_Año", "Director", "Nombre Cliente", "Tipo Cliente", "Canal", "Cierre"
    ])

def load_data():
    try:
        df_sheet = pd.read_csv(SHEET_CSV_URL)
        if not df_sheet.empty and "ID" in df_sheet.columns:
            df_sheet["ID"] = df_sheet["ID"].astype(str)
            combined = pd.concat([df_sheet, st.session_state.records], ignore_index=True).drop_duplicates(subset=["ID"], keep="last")
            return combined
    except Exception:
        pass
    return st.session_state.records

# -------------------------------------------------------------
# CÁLCULO DE MÉTRICAS IDÉNTICO AL MODELO EXCEL (.XLS)
# -------------------------------------------------------------
def compute_metrics(df, config):
    if df.empty:
        return pd.DataFrame()
    
    df_calc = df.copy()
    df_calc["Es_Presencial"] = df_calc["Canal"].apply(lambda x: 1 if str(x).strip() == "Presencial" else 0)
    df_calc["Es_Virtual"] = df_calc["Canal"].apply(lambda x: 1 if str(x).strip() == "Virtual" else 0)
    df_calc["Es_Nuevo"] = df_calc["Tipo Cliente"].apply(lambda x: 1 if "Nuevo" in str(x) or "Captación" in str(x) else 0)
    df_calc["Es_Existente"] = df_calc["Tipo Cliente"].apply(lambda x: 1 if "Existente" in str(x) or "Mantenimiento" in str(x) else 0)
    df_calc["Es_Cierre"] = df_calc["Cierre"].apply(lambda x: 1 if str(x).strip().lower() in ["sí", "si"] else 0)

    summary = df_calc.groupby("Director").agg(
        Visitas_Totales=("Fecha", "count"),
        Visitas_Presenciales=("Es_Presencial", "sum"),
        Visitas_Virtuales=("Es_Virtual", "sum"),
        Visitas_Nuevos=("Es_Nuevo", "sum"),
        Visitas_Existentes=("Es_Existente", "sum"),
        Cierres=("Es_Cierre", "sum")
    ).reset_index()

    # Puntos por Canal (Presencial + Virtual)
    puntos_canal = (summary["Visitas_Presenciales"] * config["p_presencial"]) + (summary["Visitas_Virtuales"] * config["p_virtual"])
    
    # Mezcla de Cliente (Ponderación Captación vs Mantenimiento)
    puntos_tipo = (summary["Visitas_Nuevos"] * config["p_captacion"]) + (summary["Visitas_Existentes"] * config["p_mantenimiento"])
    mezcla_cliente = puntos_tipo / summary["Visitas_Totales"].replace(0, 1)

    # Fórmula XLS: Puntos Esfuerzo = Puntos Canal * Mezcla Cliente
    summary["Puntos_Esfuerzo"] = (puntos_canal * mezcla_cliente).round(1)
    
    # Factor de Actividad (Top de 1.0 al alcanzar los 15 puntos)
    summary["Factor_Actividad"] = summary["Puntos_Esfuerzo"].apply(lambda pts: min(1.0, pts / config["umbral_puntos"]))
    
    # Tasa de Conversión Real
    summary["Tasa_Conversion"] = summary["Cierres"] / summary["Visitas_Totales"].replace(0, 1)
    
    # IEP = Tasa de Conversión * Factor de Actividad
    summary["IEP"] = summary["Tasa_Conversion"] * summary["Factor_Actividad"]
    
    # Estatus vs Objetivo (Exige alcanzar los 15 pts de esfuerzo y el 15% de IEP)
    def evaluar_cumplimiento(row):
        if row["Puntos_Esfuerzo"] < config["umbral_puntos"]:
            return "🔴 ESFUERZO INSUFICIENTE"
        elif row["IEP"] >= config["iep_objetivo"]:
            return "🟢 CUMPLE IEP"
        else:
            return "🔴 BAJO OBJETIVO"

    summary["Estatus"] = summary.apply(evaluar_cumplimiento, axis=1)
    return summary

query_params = st.query_params
mode = query_params.get("modo", "comercial")
records_df = load_data()

# =============================================================
# MODO 1: PORTAL COMERCIAL (Para Directores)
# =============================================================
if mode == "comercial":
    st.title("👤 Portal Comercial - Registro de Visitas")
    st.caption("Herramienta de autocontrol comercial para Directores de Asset Management.")

    col_dir, col_mes_filter = st.columns([2, 1])
    with col_dir:
        selected_director = st.selectbox("Selecciona tu Nombre:", LISTA_DIRECTORES)

    st.subheader("📝 Registrar Nueva Visita Comercial")
    
    col1, col2, col3, col4, col5 = st.columns([1.2, 2, 1.5, 1.2, 1.2])
    with col1:
        fecha_visita = st.date_input("Fecha de Visita", datetime.date.today())
    with col2:
        nombre_cliente = st.text_input("Nombre Cliente / Cuenta", placeholder="Ej: Fondo Pensión ABC / Juan Pérez")
    with col3:
        tipo_cliente = st.selectbox("Tipo de Cliente", ["Nuevo (Captación)", "Existente (Mantenimiento)"])
    with col4:
        canal = st.selectbox("Canal de Reunión", ["Presencial", "Virtual"])
    with col5:
        cierre = st.selectbox("¿Ocurrió Cierre / Venta?", ["No", "Sí"])

    if st.button("💾 Guardar Visita"):
        if not nombre_cliente.strip():
            st.warning("⚠️ Por favor ingresa el Nombre del Cliente antes de guardar.")
        else:
            mes_str = fecha_visita.strftime("%Y-%m")
            record_id = str(int(datetime.datetime.now().timestamp() * 1000))
            
            payload = {
                "ID": record_id,
                "Fecha": str(fecha_visita),
                "Mes_Año": mes_str,
                "Director": selected_director,
                "Nombre_Cliente": nombre_cliente.strip(),
                "Tipo_Cliente": tipo_cliente,
                "Canal": canal,
                "Cierre": cierre
            }
            
            if WEBAPP_URL and "http" in WEBAPP_URL:
                try:
                    requests.post(WEBAPP_URL, json=payload, timeout=5)
                except Exception:
                    pass

            new_row = pd.DataFrame([{
                "ID": record_id,
                "Fecha": str(fecha_visita),
                "Mes_Año": mes_str,
                "Director": selected_director,
                "Nombre Cliente": nombre_cliente.strip(),
                "Tipo Cliente": tipo_cliente,
                "Canal": canal,
                "Cierre": cierre
            }])
            st.session_state.records = pd.concat([st.session_state.records, new_row], ignore_index=True)
            st.success(f"¡Visita a '{nombre_cliente}' registrada exitosamente!")
            st.rerun()

    st.divider()
    
    st.subheader(f"📌 Resumen Individual - {selected_director}")
    
    user_records_all = records_df[records_df["Director"] == selected_director] if not records_df.empty else pd.DataFrame()
    
    if not user_records_all.empty:
        meses_disponibles = sorted(user_records_all["Mes_Año"].astype(str).unique(), reverse=True)
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
        
        st.subheader("📋 Mis Visitas Registradas")
        st.dataframe(user_records_month[["Fecha", "Nombre Cliente", "Tipo Cliente", "Canal", "Cierre"]], use_container_width=True)
    else:
        st.info("Aún no tienes visitas registradas. Comienza guardando tu primera visita arriba.")

# =============================================================
# MODO 2: CONSOLA LÍDER COMERCIAL
# =============================================================
elif mode == "lider":
    st.title("👑 Consola de Liderazgo Comercial - Asset Management")
    st.caption("Consolidador de rendimiento global y calibración del modelo IEP.")

    tab1, tab2, tab3 = st.tabs(["📊 Dashboard de Rendimiento Global", "📋 Detalle de Visitas por Cliente", "⚙️ Configuración de Parámetros"])

    with tab1:
        if not records_df.empty:
            meses_globales = sorted(records_df["Mes_Año"].astype(str).unique(), reverse=True)
            col_mes, col_spacer = st.columns([1, 2])
            with col_mes:
                mes_global = st.selectbox("📅 Selecciona el Mes a Evaluar:", meses_globales)
            
            records_month = records_df[records_df["Mes_Año"] == mes_global]
            global_summary = compute_metrics(records_month, st.session_state.config)

            if not global_summary.empty:
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
                st.info("No hay registros en el mes seleccionado.")
        else:
            st.info("No hay registros en la base de datos para mostrar acumulados.")

    with tab2:
        st.subheader("🔎 Bitácora Detallada de Visitas Comercial del Equipo")
        if not records_df.empty:
            meses_bitacora = sorted(records_df["Mes_Año"].astype(str).unique(), reverse=True)
            col_m1, col_m2 = st.columns([1, 1])
            with col_m1:
                m_selected = st.selectbox("Filtrar por Mes:", ["Todos"] + meses_bitacora)
            with col_m2:
                d_selected = st.selectbox("Filtrar por Director:", ["Todos"] + LISTA_DIRECTORES)

            df_bitacora = records_df.copy()
            if m_selected != "Todos":
                df_bitacora = df_bitacora[df_bitacora["Mes_Año"] == m_selected]
            if d_selected != "Todos":
                df_bitacora = df_bitacora[df_bitacora["Director"] == d_selected]

            st.dataframe(df_bitacora[["Fecha", "Director", "Nombre Cliente", "Tipo Cliente", "Canal", "Cierre"]], use_container_width=True)
        else:
            st.info("Aún no hay visitas registradas por el equipo.")

    with tab3:
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
