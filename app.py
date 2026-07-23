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
    layout="wide",
    initial_sidebar_state="expanded"
)

# Diseño y Estilos Cyberpunk/Hacker Premium (CSS)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Fira+Code:wght@300;400;500;700&display=swap');
    
    /* Configuración global de tipografía estilo terminal */
    html, body, [class*="css"], .stMarkdown, p, div, span, label, input, select {
        font-family: 'Share Tech Mono', 'Fira Code', monospace !important;
        color: #e0e6ed !important;
    }
    
    /* Fondo principal negro profundo únicamente en contenedores principales */
    [data-testid="stAppViewContainer"], .stApp, body, html {
        background-color: #030303 !important;
        color: #e0e6ed !important;
    }

    
    /* Barra lateral estilo consola */
    [data-testid="stSidebar"] {
        background-color: #070707 !important;
        border-right: 1px solid #00FF66 !important;
        box-shadow: 2px 0 15px rgba(0, 255, 65, 0.1) !important;
    }
    
    /* Header transparente */
    [data-testid="stHeader"] {
        background-color: rgba(3, 3, 3, 0.8) !important;
        backdrop-filter: blur(5px);
    }
    
    /* Sidebar Título Cyberpunk */
    .sidebar-title {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 20px;
        font-weight: 700;
        color: #00FF66;
        text-shadow: 0 0 10px rgba(0, 255, 102, 0.5);
        display: flex;
        align-items: center;
        margin-bottom: 20px;
        letter-spacing: 1px;
    }
    
    /* Cabecera Principal Terminal */
    .cyber-title-container {
        margin-bottom: 25px;
        padding-top: 10px;
    }
    .cyber-title {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 3px !important;
        color: #00FF66 !important;
        text-shadow: 0 0 8px rgba(0, 255, 102, 0.5);
        margin: 0 !important;
        padding: 0 !important;
    }
    .cyber-bar {
        height: 2px;
        background: linear-gradient(90deg, #00FF66, #00E5FF, transparent);
        margin-top: 8px;
        border-radius: 2px;
    }
    
    /* Subtítulos de Secciones Terminal */
    .section-title {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        color: #00E5FF !important;
        text-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
        margin-top: 25px !important;
        margin-bottom: 15px !important;
        border-left: 3px solid #00E5FF;
        padding-left: 10px;
    }
    
    /* Tarjetas Terminal con borde neon */
    .terminal-card {
        background-color: #070707 !important;
        border: 1px solid #00FF66 !important;
        box-shadow: 0 0 10px rgba(0, 255, 102, 0.1) !important;
        padding: 15px;
        border-radius: 4px;
        font-family: 'Share Tech Mono', monospace !important;
        margin-bottom: 15px;
    }
    .terminal-card-cyan {
        background-color: #070707 !important;
        border: 1px solid #00E5FF !important;
        box-shadow: 0 0 10px rgba(0, 229, 255, 0.1) !important;
        padding: 15px;
        border-radius: 4px;
        font-family: 'Share Tech Mono', monospace !important;
        margin-bottom: 15px;
    }
    
    /* Personalización del Selector (Streamlit Radio styled as Terminal Toggle Switch) */
    div[data-testid="stRadio"] > label {
        display: none !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        flex-direction: row !important;
        gap: 10px !important;
        background-color: transparent !important;
        padding: 5px 0 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background-color: #070707 !important;
        border: 1px solid #333333 !important;
        padding: 8px 16px !important;
        border-radius: 4px !important;
        color: #888888 !important;
        font-family: 'Share Tech Mono', monospace !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
        border-color: #00FF66 !important;
        color: #00FF66 !important;
        box-shadow: 0 0 8px rgba(0, 255, 102, 0.2) !important;
        background-color: rgba(0, 255, 102, 0.05) !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
        border-color: #00E5FF !important;
        color: #00E5FF !important;
    }
    
    /* Botones Neón */
    div.stButton > button {
        background-color: #050505 !important;
        color: #00FF66 !important;
        border: 1px solid #00FF66 !important;
        box-shadow: 0 0 8px rgba(0, 255, 102, 0.15) !important;
        border-radius: 4px !important;
        font-family: 'Share Tech Mono', monospace !important;
        text-transform: uppercase !important;
        font-weight: bold !important;
        letter-spacing: 1px !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
    }
    div.stButton > button:hover:not(:disabled) {
        background-color: rgba(0, 255, 102, 0.1) !important;
        box-shadow: 0 0 15px rgba(0, 255, 102, 0.5) !important;
        color: #ffffff !important;
    }
    div.stButton > button:disabled {
        color: #444444 !important;
        border-color: #222222 !important;
        box-shadow: none !important;
        cursor: not-allowed !important;
        background-color: #070707 !important;
    }
    
    /* DataFrame Tabla terminal */
    div[data-testid="stDataFrame"] {
        border: 1px solid #333333 !important;
        border-radius: 4px !important;
        background-color: #050505 !important;
    }
    
    /* Estilos responsivos optimizados para teléfonos */
    @media (max-width: 768px) {
        .cyber-title {
            font-size: 1.5rem !important;
            letter-spacing: 1px !important;
        }
        .terminal-card, .terminal-card-cyan {
            padding: 10px;
        }
    }
    </style>
""", unsafe_allow_html=True)

# 2. Gestión de estado
if "agente_corriendo" not in st.session_state:
    st.session_state.agente_corriendo = False

if "entorno_iniciado" not in st.session_state:
    st.session_state.entorno_iniciado = False

# Verificación de credenciales Supabase
supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
db_disponible = bool(supabase_url and supabase_key)

# 3. Barra lateral (Sidebar Terminal)
st.sidebar.markdown("""
    <div class="sidebar-title">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00FF66" stroke-width="2" style="vertical-align: middle; margin-right: 8px;">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        <span>[TERM_COMMAND]</span>
    </div>
""", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Selector exclusivo de plataforma estilizado como Toggle
st.sidebar.markdown('<div style="font-size: 11px; color: #888888; font-weight: bold; margin-bottom: 5px;">[SELECT_PLATFORM]</div>', unsafe_allow_html=True)
plataforma = st.sidebar.radio(
    "Selecciona red a escanear:",
    options=["Instagram", "Facebook"],
    index=0,
    label_visibility="collapsed"
)

# Cargar último índice de Supabase
ultimo_indice = 0
if db_disponible:
    try:
        ultimo_indice = db_client.obtener_ultimo_indice(plataforma)
        st.sidebar.markdown(f"""
            <div class="terminal-card-cyan" style="margin-top: 15px; padding: 10px;">
                <div style="font-size: 10px; color: #888888;">[PAGINACION_ACTUAL]</div>
                <div style="font-size: 18px; color: #00E5FF; font-weight: bold;">[SYS_INDEX: {ultimo_indice}]</div>
            </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.sidebar.error(f"Error cargando puntero: {e}")
else:
    st.sidebar.markdown("""
        <div class="terminal-card" style="border-color: #ff3366; box-shadow: 0 0 10px rgba(255, 51, 102, 0.1);">
            <span style="color: #ff3366;">[SYS_DB: OFFLINE]</span>
        </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")

# Botones de ejecución
col_iniciar, col_detener = st.sidebar.columns(2)

with col_iniciar:
    boton_deshabilitado = st.session_state.agente_corriendo or not db_disponible
    if st.button("RUN INDEX", use_container_width=True, disabled=boton_deshabilitado):
        st.sidebar.info("⚡ INICIALIZANDO...")
        st.session_state.agente_corriendo = True
        try:
            with st.spinner(f"Escaneando {plataforma} desde {ultimo_indice}..."):
                # Ejecutamos agente_scraper.py pasándole la plataforma y el índice de inicio
                proceso = subprocess.run(
                    [sys.executable, "agente_scraper.py", plataforma.lower(), str(ultimo_indice)],
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
st.sidebar.markdown('<div style="font-size: 11px; color: #888888; font-weight: bold; margin-top: 15px; margin-bottom: 5px;">[SYSTEM_HEALTH]</div>', unsafe_allow_html=True)
if st.session_state.agente_corriendo:
    st.sidebar.markdown("""
        <div class="terminal-card" style="padding: 10px; border-color: #00FF66; color: #00FF66; display: flex; align-items: center; gap: 8px;">
            <span style="display:inline-block; width:8px; height:8px; background-color:#00FF66; border-radius:50%; box-shadow: 0 0 8px #00FF66;"></span>
            <span>ONLINE_SCANNING</span>
        </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
        <div class="terminal-card" style="padding: 10px; border-color: #ff3366; color: #ff3366; display: flex; align-items: center; gap: 8px;">
            <span style="display:inline-block; width:8px; height:8px; background-color:#ff3366; border-radius:50%; box-shadow: 0 0 8px #ff3366;"></span>
            <span>SYSTEM_SLEEP</span>
        </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
limite_registros = st.sidebar.slider("[LIMIT_QUERY]", min_value=10, max_value=100, value=50, step=10)
st.sidebar.markdown("---")
st.sidebar.markdown("""
    <div style="font-size: 11px; color: #666; line-height: 1.4;">
        [INFO]: Scraper modular autónomo cloud-ready para búsqueda directa con propietarios de inmuebles.
    </div>
""", unsafe_allow_html=True)

# 4. Área Principal (Terminal de Visualización)
st.markdown("""
    <div class="cyber-title-container">
        <h1 class="cyber-title">> CONSOLE.LOG(CAPTACIONES)</h1>
        <div class="cyber-bar"></div>
    </div>
""", unsafe_allow_html=True)

# Grilla de Captaciones en Supabase
st.markdown('<div class="section-title">> TELEMETRY_DATA_GRID</div>', unsafe_allow_html=True)

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
st.markdown('<div class="section-title">> SYS_SYSTEM_LOGS</div>', unsafe_allow_html=True)
log_container = st.empty()

if st.session_state.agente_corriendo:
    if not st.session_state.entorno_iniciado:
        with log_container.container():
            st.markdown("""
                <div class="terminal-card" style="border-color:#00E5FF; color:#00E5FF;">
                    [SYS]: Paginando base de datos cloud...<br>
                    [SYS]: Inicializando motor HTTP y disparando dorks para la plataforma activa...
                </div>
            """, unsafe_allow_html=True)
            time.sleep(1)
            st.session_state.entorno_iniciado = True
            st.rerun()
    else:
        with log_container.container():
            st.markdown(f"""
                <div class="terminal-card" style="border-color:#00FF66; color:#00FF66;">
                    [SYS_ACTIVE]: Agente ejecutando búsqueda acotada de {plataforma.upper()}. Leyendo y escribiendo en la nube.
                </div>
            """, unsafe_allow_html=True)
else:
    log_container.markdown("""
        <div class="terminal-card" style="border-color:#333333; color:#666666;">
            [SYS_CONSOLE]: Esperando señal. Inicia la secuencia RUN INDEX desde el panel de control.
        </div>
    """, unsafe_allow_html=True)
