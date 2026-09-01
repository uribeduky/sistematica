import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
import altair as alt
import plotly.express as px

# Configuration
st.set_page_config(
    page_title="Sistemática Comercial IEP - Asset Management",
    page_icon="📊",
    layout="wide"
)

# Styling adaptativo para garantizar visibilidad en modo oscuro y claro
st.markdown("""
<style>
    .main-header {
        font-size: 24px;
        font-weight: bold;
        color: #1F497D;
        margin-bottom: 20px;
    }
    div[data-testid="stMetric"] {
        background-color: #F8FAFC !important;
        padding: 12px !important;
        border-radius: 8px !important;
        border-left: 5px solid #1F497D !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    div[data-testid="stMetric"] label, 
    div[data-testid="stMetric"] div[data-testid="stMetricValue"],
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
        color: #1E293B !important;
    }
</style>
""", unsafe_allow_html=True)

# Directores ordenados alfabéticamente
LISTA_DIRECTORES = sorted([
    "Claudia Céspedes",
    "Claudia Lizarralde",
    "Gloria Lamus",
    "Karen Cortés",
    "Laura Gómez",
    "María Camila León",
    "Nicolás Quintero"
])

# Productos actualizados
LISTA_PRODUCTOS = [
    "FIC Efectivo",
    "FIC Monetario",
    "FIC Multiplazo",
    "Impulso",
    "Impacto",
    "Urbano",
    "Skandia Cash",
    "OFC",
    "Crowd",
    "CATs",
    "Nota Estructurada",
    "Fideicomiso de Inversión"
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
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxe5DtYRWvWtFCNvnJTXdtU45Un2GYcqkcUVwszoEr_vsisalLRZBhLwobTwu6zkkiDpg/exec"

if "local_records" not in st.session_state:
    st.session_state.local_records = pd.DataFrame(columns=[
        "ID", "Fecha", "Mes_Año", "Director", "Nombre Cliente", "Tipo Cliente", "Canal", "Cierre", "Principal Producto", "Monto COP$MM"
    ])

if "deleted_ids" not in st.session_state:
    st.session_state.deleted_ids = set()

def send_to_google_sheet(payload):
    try:
        response = requests.post(WEBAPP_URL, json=payload, timeout=10)
        if response.status_code in [200, 302]:
            return True
        else:
            st.warning(f"⚠️ Alerta de sincronización (Código: {response.status_code})")
            return False
    except Exception as e:
        st.error(f"⚠️ Error al conectar con la base de datos: {e}")
        return False

def format_cop_int(val):
    try:
        val_int = int(round(float(val)))
        return f"${val_int:,}".replace(",", ".")
    except Exception:
        return "$0"

def load_data():
    df_sheet = pd.DataFrame(columns=["ID", "Fecha", "Mes_Año", "Director", "Nombre Cliente", "Tipo Cliente", "Canal", "Cierre", "Principal Producto", "Monto COP$MM"])
    try:
        timestamp_url = f"{SHEET_CSV_URL}&t={int(datetime.datetime.now().timestamp())}"
        df_sheet = pd.read_csv(timestamp_url)
        if not df_sheet.empty and "ID" in df_sheet.columns:
            df_sheet["ID"] = df_sheet["ID"].astype(str)
            
            # Mapeo universal de nombres de columnas
            col_map = {
                "Nombre_Cliente": "Nombre Cliente",
                "Tipo_Cliente": "Tipo Cliente",
                "Principal_Producto": "Principal Producto",
                "Monto_COP_MM": "Monto COP$MM",
                "Monto": "Monto COP$MM",
                "Monto ($MM)": "Monto COP$MM"
            }
            df_sheet.rename(columns=col_map, inplace=True)

            if "Principal Producto" not in df_sheet.columns:
                df_sheet["Principal Producto"] = ""
            if "Monto COP$MM" not in df_sheet.columns:
                df_sheet["Monto COP$MM"] = 0
            else:
                df_sheet["Monto COP$MM"] = pd.to_numeric(df_sheet["Monto COP$MM"], errors='coerce').fillna(0).astype(int)
    except Exception:
        pass

    if not st.session_state.local_records.empty:
        df_sheet = pd.concat([df_sheet, st.session_state.local_records], ignore_index=True)
    
    if not df_sheet.empty and "ID" in df_sheet.columns:
        df_sheet = df_sheet.drop_duplicates(subset=["ID"], keep="last")
        if st.session_state.deleted_ids:
            df_sheet = df_sheet[~df_sheet["ID"].isin(st.session_state.deleted_ids)]

    return df_sheet

def compute_metrics(df, config):
    if df.empty:
        return pd.DataFrame()
    
    df_calc = df.copy()
    df_calc["Es_Presencial"] = df_calc["Canal"].apply(lambda x: 1 if str(x).strip() == "Presencial" else 0)
    df_calc["Es_Virtual"] = df_calc["Canal"].apply(lambda x: 1 if str(x).strip() == "Virtual" else 0)
    df_calc["Es_Nuevo"] = df_calc["Tipo Cliente"].apply(lambda x: 1 if "Nuevo" in str(x) or "Captación" in str(x) else 0)
    df_calc["Es_Existente"] = df_calc["Tipo Cliente"].apply(lambda x: 1 if "Existente" in str(x) or "Mantenimiento" in str(x) else 0)
    df_calc["Es_Cierre"] = df_calc["Cierre"].apply(lambda x: 1 if str(x).strip().lower() in ["sí", "si"] else 0)
    df_calc["Monto COP$MM"] = pd.to_numeric(df_calc["Monto COP$MM"], errors='coerce').fillna(0).astype(int)

    summary = df_calc.groupby("Director").agg(
        Visitas_Totales=("Fecha", "count"),
        Visitas_Presenciales=("Es_Presencial", "sum"),
        Visitas_Virtuales=("Es_Virtual", "sum"),
        Visitas_Nuevos=("Es_Nuevo", "sum"),
        Visitas_Existentes=("Es_Existente", "sum"),
        Cierres=("Es_Cierre", "sum"),
        Total_Monto_COP_MM=("Monto COP$MM", "sum")
    ).reset_index()

    puntos_canal = (summary["Visitas_Presenciales"] * config["p_presencial"]) + (summary["Visitas_Virtuales"] * config["p_virtual"])
    puntos_tipo = (summary["Visitas_Nuevos"] * config["p_captacion"]) + (summary["Visitas_Existentes"] * config["p_mantenimiento"])
    mezcla_cliente = puntos_tipo / summary["Visitas_Totales"].replace(0, 1)

    summary["Puntos_Esfuerzo"] = (puntos_canal * mezcla_cliente).round(1)
    summary["Factor_Actividad"] = summary["Puntos_Esfuerzo"].apply(lambda pts: min(1.0, pts / config["umbral_puntos"]))
    summary["Tasa_Conversion"] = summary["Cierres"] / summary["Visitas_Totales"].replace(0, 1)
    summary["IEP"] = summary["Tasa_Conversion"] * summary["Factor_Actividad"]
    
    return summary

def create_bar_chart_with_mean(data, x_col, color_hex, title_text):
    mean_val = data[x_col].mean()
    
    bars = alt.Chart(data).mark_bar(color=color_hex, cornerRadiusEnd=4).encode(
        y=alt.Y('Director:N', title=None, sort='ascending'),
        x=alt.X(f'{x_col}:Q', title=None),
        tooltip=['Director', alt.Tooltip(f'{x_col}:Q', title=title_text)]
    )
    
    rule = alt.Chart(pd.DataFrame({'media': [mean_val]})).mark_rule(
        color='#DC2626',
        strokeDash=[4, 4],
        size=2
    ).encode(
        x='media:Q'
    )
    
    text_rule = alt.Chart(pd.DataFrame({'media': [mean_val], 'label': [f'Media: {mean_val:.1f}']})).mark_text(
        align='left',
        baseline='bottom',
        dx=5,
        dy=-5,
        color='#DC2626',
        fontSize=11,
        fontWeight='bold'
    ).encode(
        x='media:Q',
        text='label:N'
    )
    
    chart = (bars + rule + text_rule).properties(height=260)
    return chart

def create_pie_chart_plotly(data, col_name):
    if data.empty or col_name not in data.columns:
        return px.pie(title="Sin datos")
    
    df_pie = data[col_name].value_counts().reset_index()
    df_pie.columns = [col_name, 'Count']
    df_pie = df_pie[df_pie[col_name].astype(str).str.strip() != ""]
    
    if df_pie.empty:
        return px.pie(title="Sin datos")
    
    total_count = df_pie['Count'].sum()
    df_pie['Percentage'] = (df_pie['Count'] / total_count * 100).round(1)
    
    # Ordenar para identificar el Top 3
    df_pie = df_pie.sort_values(by='Count', ascending=False).reset_index(drop=True)
    
    # Etiqueta interna solo para los 3 primeros productos de mayor participación
    df_pie['Label_Inside'] = df_pie.apply(
        lambda r: f"<b>{r['Percentage']:.1f}%</b>" if r.name < 3 and r['Percentage'] > 0 else "", axis=1
    )

    fig = px.pie(
        df_pie,
        values='Count',
        names=col_name,
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig.update_traces(
        text=df_pie['Label_Inside'],
        textinfo='text',
        textposition='inside',
        insidetextfont=dict(size=14, color='white'),
        hovertemplate="<b>%{label}</b><br>Visitas: %{value}<br>Participación: %{percent}"
    )
    
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
    )
    
    return fig

def create_line_chart(df_all, dir_filter, prod_filter):
    df_t = df_all.copy()
    if dir_filter != "Todos":
        df_t = df_t[df_t["Director"] == dir_filter]
    if prod_filter != "Todos":
        df_t = df_t[df_t["Principal Producto"] == prod_filter]
        
    if df_t.empty:
        return alt.Chart(pd.DataFrame({'msg': ['Sin datos']})).mark_text().encode(text='msg')
        
    df_t["Es_Nuevo"] = df_t["Tipo Cliente"].apply(lambda x: 1 if "Nuevo" in str(x) or "Captación" in str(x) else 0)
    df_t["Es_Cierre"] = df_t["Cierre"].apply(lambda x: 1 if str(x).strip().lower() in ["sí", "si"] else 0)
    
    trend = df_t.groupby("Mes_Año").agg(
        Visitas_Totales=("Fecha", "count"),
        Clientes_Nuevos=("Es_Nuevo", "sum"),
        Cierres=("Es_Cierre", "sum")
    ).reset_index().sort_values("Mes_Año")
    
    if trend.empty:
        return alt.Chart(pd.DataFrame({'msg': ['Sin datos']})).mark_text().encode(text='msg')
        
    trend_melted = trend.melt('Mes_Año', var_name='Métrica', value_name='Valor')
    
    metric_names = {
        'Visitas_Totales': 'Visitas Totales',
        'Clientes_Nuevos': 'Clientes Nuevos',
        'Cierres': 'Cierres'
    }
    trend_melted['Métrica'] = trend_melted['Métrica'].map(metric_names)
    
    chart = alt.Chart(trend_melted).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X('Mes_Año:N', title='Mes'),
        y=alt.Y('Valor:Q', title='Cantidad'),
        color=alt.Color('Métrica:N', scale=alt.Scale(domain=['Visitas Totales', 'Clientes Nuevos', 'Cierres'], range=['#1F497D', '#2E7D32', '#D81B60']), legend=alt.Legend(title="Indicador", orient="bottom")),
        tooltip=['Mes_Año:N', 'Métrica:N', 'Valor:Q']
    ).properties(height=280)
    return chart

query_params = st.query_params
mode = query_params.get("modo", "comercial")

with st.spinner("Cargando datos comerciales..."):
    records_df = load_data()

# =============================================================
# MODO 1: PORTAL COMERCIAL (Para Directores)
# =============================================================
if mode == "comercial":
    st.title("👤 Portal Comercial - Registro de Visitas")
    st.caption("Herramienta comercial para Directores de Asset Management.")

    col_dir, col_mes_filter = st.columns([2, 1])
    with col_dir:
        selected_director = st.selectbox("Selecciona tu Nombre:", LISTA_DIRECTORES)

    st.subheader("📝 Registrar Nueva Visita Comercial")
    
    col1, col2, col3, col4, col5, col6 = st.columns([1.1, 1.8, 1.3, 1.0, 1.3, 1.0])
    with col1:
        fecha_visita = st.date_input("Fecha de Visita", datetime.date.today())
    with col2:
        nombre_cliente = st.text_input("Nombre Cliente / Cuenta", placeholder="Ej: Fondo Pensión ABC / Juan Pérez")
    with col3:
        tipo_cliente = st.selectbox("Tipo de Cliente", ["Nuevo (Captación)", "Existente (Mantenimiento)"])
    with col4:
        canal = st.selectbox("Canal de Reunión", ["Presencial", "Virtual"])
    with col5:
        principal_producto = st.selectbox("Principal Producto", LISTA_PRODUCTOS)
    with col6:
        cierre = st.selectbox("¿Ocurrió Cierre?", ["No", "Sí"])

    monto_cierre = 0
    if cierre == "Sí":
        monto_cierre = st.number_input("💵 Monto Cierre (COP $ MM):", min_value=0, value=0, step=1, help="Ingresa el monto captado o cerrado en millones de pesos colombianos (entero).")

    if st.button("💾 Guardar Visita"):
        if not nombre_cliente.strip():
            st.warning("⚠️ Por favor ingresa el Nombre del Cliente antes de guardar.")
        else:
            mes_str = fecha_visita.strftime("%Y-%m")
            record_id = str(int(datetime.datetime.now().timestamp() * 1000))
            
            final_monto = int(monto_cierre) if cierre == "Sí" else 0
            
            new_row = pd.DataFrame([{
                "ID": record_id,
                "Fecha": str(fecha_visita),
                "Mes_Año": mes_str,
                "Director": selected_director,
                "Nombre Cliente": nombre_cliente.strip(),
                "Tipo Cliente": tipo_cliente,
                "Canal": canal,
                "Cierre": cierre,
                "Principal Producto": principal_producto,
                "Monto COP$MM": final_monto
            }])
            st.session_state.local_records = pd.concat([st.session_state.local_records, new_row], ignore_index=True)

            payload = {
                "action": "add",
                "ID": record_id,
                "Fecha": str(fecha_visita),
                "Mes_Año": mes_str,
                "Director": selected_director,
                "Nombre_Cliente": nombre_cliente.strip(),
                "Nombre Cliente": nombre_cliente.strip(),
                "Tipo_Cliente": tipo_cliente,
                "Tipo Cliente": tipo_cliente,
                "Canal": canal,
                "Cierre": cierre,
                "Principal_Producto": principal_producto,
                "Principal Producto": principal_producto,
                "Monto_COP_MM": final_monto,
                "Monto COP$MM": final_monto,
                "Monto": final_monto
            }
            send_to_google_sheet(payload)

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
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Visitas Realizadas", int(row["Visitas_Totales"]))
            m2.metric("Puntos de Esfuerzo", f"{row['Puntos_Esfuerzo']:.1f} / {st.session_state.config['umbral_puntos']}")
            m3.metric("Factor Actividad", f"{row['Factor_Actividad']*100:.0f}%")
            m4.metric("Tasa Conversión", f"{row['Tasa_Conversion']*100:.1f}%")
            m5.metric("IEP Comercial", f"{row['IEP']*100:.1f}%")
            m6.metric("Total Cierres $MM", f"{format_cop_int(row['Total_Monto_COP_MM'])} MM")

            # SECCIÓN DATA ANALYTICS INDIVIDUAL + RECOMENDACIÓN COMERCIAL
            with st.expander("💡 Data Analytics", expanded=True):
                u_visitas = len(user_records_month)
                u_cierres = int(row["Cierres"])
                u_monto = row["Total_Monto_COP_MM"]

                u_ticket_prom = (u_monto / u_cierres) if u_cierres > 0 else 0
                
                u_pres = len(user_records_month[user_records_month["Canal"].astype(str).str.strip() == "Presencial"])
                u_pct_pres = (u_pres / u_visitas * 100) if u_visitas > 0 else 0

                u_nuevos = len(user_records_month[user_records_month["Tipo Cliente"].astype(str).str.contains("Nuevo|Captación", case=False, na=False)])
                u_pct_nuevos = (u_nuevos / u_visitas * 100) if u_visitas > 0 else 0

                c_i1, c_i2, c_i3 = st.columns(3)
                c_i1.metric("Ticket Promedio / Cierre", f"{format_cop_int(u_ticket_prom)} MM")
                c_i2.metric("Mix Presencialidad", f"{u_pct_pres:.0f}% Presencial")
                c_i3.metric("Foco Captación (Nuevos)", f"{u_pct_nuevos:.0f}% Nuevo")

                st.markdown("---")
                st.markdown("##### 📌 **Recomendación Comercial**")
                
                u_pts = row["Puntos_Esfuerzo"]
                if u_pts < st.session_state.config["umbral_puntos"]:
                    st.info(f"💡 **Recomendación Comercial:** Tu nivel de esfuerzo actual ({u_pts:.1f} pts) está por debajo del umbral objetivo ({st.session_state.config['umbral_puntos']} pts). Agendar reuniones presenciales adicionales o enfocar la semana en prospección de clientes nuevos te ayudará a alcanzar la meta rápidamente.")
                elif u_pct_nuevos < 40:
                    st.warning("💡 **Recomendación Comercial:** Tu agenda está inclinada principalmente hacia mantenimiento de clientes existentes. Para maximizar tus puntos de esfuerzo, intenta balancear tus llamadas integrando nuevas cuentas de captación.")
                else:
                    st.success("💡 **Recomendación Comercial:** Excelente balance de esfuerzo y prospección. Mantener el ritmo de conversión actual para consolidar el IEP del período.")

        st.divider()
        st.subheader("📋 Mis Visitas Registradas")

        df_display = user_records_month[["ID", "Fecha", "Nombre Cliente", "Tipo Cliente", "Canal", "Principal Producto", "Cierre", "Monto COP$MM"]].copy()
        df_display_show = df_display[["Fecha", "Nombre Cliente", "Tipo Cliente", "Canal", "Principal Producto", "Cierre", "Monto COP$MM"]].copy()
        df_display_show["Monto COP$MM"] = df_display_show["Monto COP$MM"].apply(format_cop_int)
        
        st.dataframe(df_display_show, use_container_width=True)

        col_edit_exp, col_del_exp = st.columns(2)

        with col_edit_exp:
            with st.expander("✏️ Actualizar una Visita Registrada"):
                dict_edit = {
                    f"{r['Fecha']} - {r['Nombre Cliente']} (Producto: {r['Principal Producto'] or 'Sin definir'})": r
                    for _, r in df_display.iterrows()
                }
                if dict_edit:
                    visita_edit_sel = st.selectbox("Selecciona la visita que deseas actualizar:", list(dict_edit.keys()), key="sel_edit_user")
                    record_to_edit = dict_edit[visita_edit_sel]
                    
                    curr_prod = str(record_to_edit.get('Principal Producto', ''))
                    idx_prod = LISTA_PRODUCTOS.index(curr_prod) if curr_prod in LISTA_PRODUCTOS else 0

                    nuevo_prod = st.selectbox("Nuevo Principal Producto:", LISTA_PRODUCTOS, index=idx_prod, key="edit_prod")
                    nuevo_cierre = st.selectbox("¿Ocurrió Cierre?", ["No", "Sí"], index=1 if str(record_to_edit['Cierre']).strip().lower() in ['sí', 'si'] else 0, key="edit_cierre")
                    nuevo_monto = st.number_input("Monto COP $MM:", min_value=0, value=int(record_to_edit.get('Monto COP$MM', 0)), step=1, key="edit_monto")
                    
                    if st.button("🔄 Guardar Cambios en la Visita", key="btn_save_edit"):
                        final_edit_monto = int(nuevo_monto) if nuevo_cierre == "Sí" else 0
                        
                        edit_payload = {
                            "action": "update",
                            "ID": str(record_to_edit['ID']),
                            "Principal_Producto": nuevo_prod,
                            "Principal Producto": nuevo_prod,
                            "Cierre": nuevo_cierre,
                            "Monto_COP_MM": final_edit_monto,
                            "Monto COP$MM": final_edit_monto,
                            "Monto": final_edit_monto
                        }
                        send_to_google_sheet(edit_payload)
                        
                        mask = st.session_state.local_records["ID"].astype(str) == str(record_to_edit['ID'])
                        if mask.any():
                            st.session_state.local_records.loc[mask, "Principal Producto"] = nuevo_prod
                            st.session_state.local_records.loc[mask, "Cierre"] = nuevo_cierre
                            st.session_state.local_records.loc[mask, "Monto COP$MM"] = final_edit_monto

                        st.success("¡Visita actualizada correctamente!")
                        st.rerun()

        with col_del_exp:
            with st.expander("🗑️ Eliminar una Visita Registrada"):
                dict_del = {
                    f"{r['Fecha']} - {r['Nombre Cliente']} (ID: {r['ID']})": str(r['ID'])
                    for _, r in df_display.iterrows()
                }
                if dict_del:
                    visita_del_sel = st.selectbox("Selecciona la visita que deseas eliminar:", list(dict_del.keys()), key="sel_del_user")
                    if st.button("🗑️ Eliminar Esta Visita", key="btn_del_user"):
                        id_del_user = dict_del[visita_del_sel]
                        send_to_google_sheet({"action": "delete", "ID": id_del_user})
                        st.session_state.deleted_ids.add(id_del_user)
                        
                        if not st.session_state.local_records.empty:
                            st.session_state.local_records = st.session_state.local_records[
                                st.session_state.local_records["ID"].astype(str) != id_del_user
                            ]
                        st.success("¡Visita eliminada correctamente!")
                        st.rerun()

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
            col_mes, col_dir_filter, col_prod_filter = st.columns([1, 1, 1])
            with col_mes:
                mes_global = st.selectbox("📅 Selecciona el Mes a Evaluar:", meses_globales)
            with col_dir_filter:
                dir_global_filter = st.selectbox("👤 Filtrar por Director:", ["Todos"] + LISTA_DIRECTORES)
            with col_prod_filter:
                prod_global_filter = st.selectbox("📦 Filtrar por Producto:", ["Todos"] + LISTA_PRODUCTOS)
            
            records_month = records_df[records_df["Mes_Año"] == mes_global]
            if dir_global_filter != "Todos":
                records_month = records_month[records_month["Director"] == dir_global_filter]
            if prod_global_filter != "Todos":
                records_month = records_month[records_month["Principal Producto"] == prod_global_filter]

            global_summary = compute_metrics(records_month, st.session_state.config)

            if not global_summary.empty:
                col_a, col_b, col_c, col_d, col_e = st.columns(5)
                col_a.metric("Total Visitas Equipo", int(global_summary["Visitas_Totales"].sum()))
                col_b.metric("Puntos Promedio Esfuerzo", f"{global_summary['Puntos_Esfuerzo'].mean():.1f}")
                col_c.metric("IEP Promedio Equipo", f"{global_summary['IEP'].mean()*100:.1f}%")
                col_d.metric("Cierres Totales Mes", int(global_summary["Cierres"].sum()))
                col_e.metric("Volumen Captado Total", f"{format_cop_int(global_summary['Total_Monto_COP_MM'].sum())} MM")

                st.divider()

                # SECCIÓN DE DATA ANALYTICS GLOBAL
                with st.expander("💡 Data Analytics", expanded=True):
                    tot_visitas = len(records_month)
                    tot_cierres = int(global_summary["Cierres"].sum())
                    tot_monto = global_summary["Total_Monto_COP_MM"].sum()

                    ticket_prom = (tot_monto / tot_cierres) if tot_cierres > 0 else 0
                    
                    num_pres = len(records_month[records_month["Canal"].str.strip() == "Presencial"]) if not records_month.empty else 0
                    pct_pres = (num_pres / tot_visitas * 100) if tot_visitas > 0 else 0

                    num_nuevos = len(records_month[records_month["Tipo Cliente"].str.contains("Nuevo|Captación", case=False, na=False)]) if not records_month.empty else 0
                    pct_nuevos = (num_nuevos / tot_visitas * 100) if tot_visitas > 0 else 0

                    ratio_cierres_global = (tot_cierres / tot_visitas * 100) if tot_visitas > 0 else 0

                    ins_col1, ins_col2, ins_col3, ins_col4 = st.columns(4)
                    ins_col1.metric("Ticket Promedio / Cierre", f"{format_cop_int(ticket_prom)} MM")
                    ins_col2.metric("Mix Presencialidad", f"{pct_pres:.0f}% Presencial")
                    ins_col3.metric("Foco Captación (Nuevos)", f"{pct_nuevos:.0f}% Nuevo")
                    ins_col4.metric("Ratio Cierres vs Visitas", f"{ratio_cierres_global:.1f}%")

                    st.markdown("---")
                    st.markdown("##### 📌 **Recomendación Comercial**")
                    
                    pts_prom = global_summary['Puntos_Esfuerzo'].mean()
                    if pts_prom < st.session_state.config["umbral_puntos"]:
                        st.info(f"💡 **Recomendación Comercial:** El volumen de esfuerzo del equipo ({pts_prom:.1f} pts) está por debajo del umbral objetivo ({st.session_state.config['umbral_puntos']} pts). Se sugiere incentivar una mayor intensidad de reuniones iniciales y visitas presenciales.")
                    elif pct_nuevos < 40:
                        st.warning("💡 **Recomendación Comercial:** La mayor parte de la agenda está concentrada en mantenimiento de clientes existentes. Se recomienda motivar la prospección activa de clientes nuevos para aprovechar el multiplicador de captación (1.5x).")
                    else:
                        st.success("💡 **Recomendación Comercial:** Excelente balance de esfuerzo y mezcla de prospectos. Mantener el ritmo de cierres en los productos foco.")

                st.divider()

                # SECCIÓN DE GRÁFICOS DE BARRAS HORIZONTALES
                st.subheader("📈 Comparativos por Comercial")
                
                chart_df = global_summary.sort_values("Director", ascending=True).copy()
                
                col_g1, col_g2, col_g3 = st.columns(3)
                
                with col_g1:
                    st.markdown("##### 📍 Visitas Totales por Comercial")
                    chart_v = create_bar_chart_with_mean(chart_df, "Visitas_Totales", "#1F497D", "Visitas Totales")
                    st.altair_chart(chart_v, use_container_width=True)

                with col_g2:
                    st.markdown("##### 🎯 Visitas a Clientes Nuevos")
                    chart_n = create_bar_chart_with_mean(chart_df, "Visitas_Nuevos", "#2E7D32", "Visitas Nuevos")
                    st.altair_chart(chart_n, use_container_width=True)

                with col_g3:
                    st.markdown("##### 🤝 Número de Cierres")
                    chart_c = create_bar_chart_with_mean(chart_df, "Cierres", "#D81B60", "Cierres")
                    st.altair_chart(chart_c, use_container_width=True)

                st.divider()

                # SECCIÓN DE GRÁFICOS: PIE (PLOTLY DENTRO DEL PIE) Y LÍNEA (EVOLUCIÓN HISTÓRICA)
                st.subheader("📊 Distribución por Producto y Evolución Histórica")
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.markdown("##### 📦 Distribución de Visitas por Producto")
                    pie_chart_fig = create_pie_chart_plotly(records_month, "Principal Producto")
                    st.plotly_chart(pie_chart_fig, use_container_width=True)
                    
                with col_p2:
                    st.markdown("##### 📈 Evolución Histórica por Mes")
                    line_chart_obj = create_line_chart(records_df, dir_global_filter, prod_global_filter)
                    st.altair_chart(line_chart_obj, use_container_width=True)

                st.divider()
                st.subheader(f"📋 Rendimiento del Equipo - Período {mes_global}")

                display_df = global_summary[[
                    "Director", "Visitas_Totales", "Visitas_Presenciales", "Visitas_Virtuales",
                    "Visitas_Nuevos", "Visitas_Existentes", "Puntos_Esfuerzo", "Factor_Actividad",
                    "Cierres", "Total_Monto_COP_MM", "Tasa_Conversion", "IEP"
                ]].sort_values("Director", ascending=True).copy()

                display_df["Total_Monto_COP_MM"] = display_df["Total_Monto_COP_MM"].apply(format_cop_int)
                display_df.rename(columns={"Total_Monto_COP_MM": "Monto Total ($MM)"}, inplace=True)
                display_df["Factor_Actividad"] = (display_df["Factor_Actividad"] * 100).round(1).astype(str) + "%"
                display_df["Tasa_Conversion"] = (display_df["Tasa_Conversion"] * 100).round(1).astype(str) + "%"
                display_df["IEP"] = (display_df["IEP"] * 100).round(1).astype(str) + "%"

                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("No hay registros que coincidan con los filtros seleccionados (Mes, Director o Producto).")
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

            cols_show = ["Fecha", "Director", "Nombre Cliente", "Tipo Cliente", "Canal", "Principal Producto", "Cierre", "Monto COP$MM"]
            df_bitacora_show = df_bitacora[[c for c in cols_show if c in df_bitacora.columns]].copy()
            if "Monto COP$MM" in df_bitacora_show.columns:
                df_bitacora_show["Monto COP$MM"] = df_bitacora_show["Monto COP$MM"].apply(format_cop_int)

            st.dataframe(df_bitacora_show, use_container_width=True)
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
