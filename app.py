import streamlit as st
import pandas as pd
import time
import os
import subprocess
import sys

# Intentar cargar variables de entorno locales desde archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import db_client

# 1. Configuración de la página
st.set_page_config(
    page_title="IA INMOBILIARIA - TERMINAL DE OPERACIONES",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# La interfaz utiliza el diseño nativo estable de Streamlit.

# 2. Gestión de estado
if "agente_corriendo" not in st.session_state:
    st.session_state.agente_corriendo = False

if "entorno_iniciado" not in st.session_state:
    st.session_state.entorno_iniciado = False

# Verificación de credenciales Supabase
supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
db_disponible = bool(supabase_url and supabase_key)

# 3. Barra lateral
st.sidebar.title("🤖 IA Inmobiliaria")
st.sidebar.caption("Terminal de control")
st.sidebar.divider()

# Selector de plataforma nativo
plataforma = st.sidebar.radio(
    "Plataforma a escanear:",
    options=["Instagram", "Facebook"],
    index=0
)

# Cargar último índice de Supabase
ultimo_indice = 0
if db_disponible:
    try:
        ultimo_indice = db_client.obtener_ultimo_indice(plataforma)
        st.sidebar.metric(label="Último Índice Escaneado", value=ultimo_indice)
    except Exception as e:
        st.sidebar.error(f"Error cargando puntero: {e}")
else:
    st.sidebar.error("Base de datos de Supabase offline. Configura las credenciales en .env")

st.sidebar.divider()

# Botones de ejecución
col_iniciar, col_detener = st.sidebar.columns(2)

with col_iniciar:
    boton_deshabilitado = st.session_state.agente_corriendo or not db_disponible
    if st.button("RUN INDEX", use_container_width=True, disabled=boton_deshabilitado):
        st.sidebar.info("⚡ INICIALIZANDO...")
        st.session_state.agente_corriendo = True
        try:
            with st.spinner(f"Escaneando {plataforma} desde {ultimo_indice}..."):
                # Calcular ruta absoluta de forma robusta para evitar errores de CWD en la nube
                dir_actual = os.path.dirname(os.path.abspath(__file__))
                ruta_scraper = os.path.join(dir_actual, "agente_scraper.py")
                # Ejecutamos agente_scraper.py pasándole la plataforma y el índice de inicio
                proceso = subprocess.run(
                    [sys.executable, ruta_scraper, plataforma.lower(), str(ultimo_indice)],
                    capture_output=True,
                    text=True
                )
            
            st.session_state.agente_corriendo = False
            if proceso.returncode == 0:
                st.sidebar.success("✅ COMAND FINISHED")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("❌ PROCESS CRASHED")
                with st.expander("Ver log de diagnóstico"):
                    st.code(proceso.stderr or proceso.stdout)
                st.session_state.estado = "ESPERANDO"
                
        except Exception as e:
            st.session_state.agente_corriendo = False
            st.sidebar.error(f"Error: {e}")
            st.session_state.estado = "ESPERANDO"

with col_detener:
    if st.button("STOP", use_container_width=True, disabled=True):
        pass

# Indicador visual del estado del sistema
if st.session_state.agente_corriendo:
    st.sidebar.success("Escáner activo en la nube.")
else:
    st.sidebar.info("Escáner inactivo.")

st.sidebar.divider()
limite_registros = st.sidebar.slider("Límite de registros a consultar:", min_value=10, max_value=100, value=50, step=10)
st.sidebar.divider()
st.sidebar.info("Scraper modular autónomo cloud-ready para búsqueda directa con propietarios de inmuebles.")

# 4. Área Principal (Terminal de Visualización)
st.title("🖥️ Terminal de Captaciones Inmobiliarias")

# Grilla de Captaciones en Supabase
st.subheader("Datos de Telemetría Recientes")

if db_disponible:
    try:
        datos = db_client.obtener_captaciones_recientes(limit=limite_registros)
        if datos:
            df = pd.DataFrame(datos)
            
            # Formatear la columna de fecha para estilo consola
            if "creado_en" in df.columns:
                df["creado_en"] = pd.to_datetime(df["creado_en"]).dt.strftime("%Y-%m-%d %H:%M")
            
            # Asegurar y renombrar columnas deseadas para la consola
            df_display = df.rename(columns={
                "creado_en": "FECHA",
                "plataforma": "RED",
                "titulo": "PROPIEDAD_TITULO",
                "link": "URL",
                "telefono": "TELEFONO",
                "analisis_ia": "ANALISIS_IA"
            })
            
            columnas_show = ["FECHA", "RED", "PROPIEDAD_TITULO", "URL", "TELEFONO", "ANALISIS_IA"]
            df_display = df_display[[c for c in columnas_show if c in df_display.columns]]
            
            st.dataframe(
                df_display,
                column_config={
                    "URL": st.column_config.LinkColumn(
                        "URL",
                        help="Abrir la publicación orginal en una pestaña nueva",
                        display_text="LINK_OPEN 🔗"
                    )
                },
                use_container_width=True
            )
        else:
            st.info("[SYS_INFO]: No se encontraron registros en Supabase. Corre el agente para poblar la base de datos cloud.")
    except Exception as e:
        st.error(f"[SYS_ERROR]: Falló la sincronización con la base de datos cloud: {e}")
else:
    st.warning("[SYS_WARN]: Supabase no está configurado. Revisa tu archivo .env.")

# 5. Consola de Registro de Operaciones (Logs)
st.subheader("Logs de Operación del Sistema")
log_container = st.empty()

if st.session_state.agente_corriendo:
    if not st.session_state.entorno_iniciado:
        with log_container.container():
            st.info("[SYS]: Paginando base de datos cloud...\n[SYS]: Inicializando motor HTTP y disparando dorks para la plataforma activa...")
            time.sleep(1)
            st.session_state.entorno_iniciado = True
            st.rerun()
    else:
        with log_container.container():
            st.success(f"[SYS_ACTIVE]: Agente ejecutando búsqueda acotada de {plataforma.upper()}. Leyendo y escribiendo en la nube.")
else:
    log_container.info("[SYS_CONSOLE]: Esperando señal. Inicia la secuencia RUN INDEX desde el panel de control.")
