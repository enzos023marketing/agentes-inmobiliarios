import streamlit as st
import pandas as pd
import time
import os
import subprocess
import sys
import queue
import threading

# Intentar cargar variables de entorno locales desde archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import db_client

@st.cache_data(ttl=60)
def check_supabase():
    return db_client.validar_conexion_supabase()

@st.cache_data(ttl=60)
def check_telegram():
    from notificador_telegram import validar_conexion_telegram
    return validar_conexion_telegram()

@st.cache_data(ttl=60)
def check_gemini():
    gemini_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            gemini_key = str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    if not gemini_key:
        val = os.getenv("GEMINI_API_KEY")
        if val is not None:
            gemini_key = val.strip()
            
    if not gemini_key:
        return False
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        client.models.list()
        return True
    except Exception:
        return False


# 1. Configuración de la página
st.set_page_config(
    page_title="IA INMOBILIARIA - TERMINAL DE OPERACIONES",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# La interfaz utiliza el diseño nativo estable de Streamlit.

# Custom Hacker CSS injection
st.markdown("""
<style>
    /* Estilos globales */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stHeader"] {
        background-color: #05070a !important;
        color: #00ff66 !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    
    /* Forzar textos a Courier New y Verde Neón */
    h1, h2, h3, h4, h5, h6, span, label, p, div, small {
        font-family: 'Courier New', Courier, monospace !important;
        color: #00ff66 !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #070a0f !important;
        border-right: 1px solid #00ff6633 !important;
    }
    
    /* Inputs, select boxes y sliders */
    input, select, textarea, div[role="button"], div[data-baseweb="select"] {
        background-color: #0a0e14 !important;
        color: #00ff66 !important;
        border: 1px solid #00ff6655 !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    
    /* Ajuste de controles sliders */
    div[data-testid="stSlider"] {
        color: #00ff66 !important;
    }
    
    /* Botones estilo terminal */
    button[kind="primary"], button[kind="secondary"], .stButton > button {
        background-color: #05070a !important;
        color: #00ff66 !important;
        border: 1px solid #00ff66 !important;
        font-family: 'Courier New', Courier, monospace !important;
        border-radius: 4px !important;
        transition: all 0.3s ease-in-out !important;
        font-weight: bold !important;
        text-transform: uppercase !important;
    }
    
    button[kind="primary"]:hover, button[kind="secondary"]:hover, .stButton > button:hover {
        background-color: #00ff66 !important;
        color: #05070a !important;
        box-shadow: 0 0 15px #00ff66bb !important;
        border: 1px solid #00ff66 !important;
    }
    
    /* DataFrame y tablas estilo hacker */
    .stDataFrame, div[data-testid="stTable"] {
        background-color: #05070a !important;
        border: 1px solid #00ff6633 !important;
    }
    
    div[data-testid="stDataFrame"] div {
        font-family: 'Courier New', Courier, monospace !important;
    }

    /* Modificar colores del dataframe renderizado */
    .stDataFrame [role="grid"] {
        background-color: #05070a !important;
    }
    
    .stDataFrame [role="gridcell"], .stDataFrame [role="columnheader"] {
        background-color: #070a0f !important;
        color: #00ff66 !important;
        border: 1px solid #00ff6622 !important;
    }
    
    /* Mensajes de información y advertencia */
    div[data-testid="stAlert"] {
        background-color: #0a0e14 !important;
        color: #00ff66 !important;
        border: 1px solid #00ff6644 !important;
    }
    
    /* Estilo del área de logs (st.code) */
    code, pre {
        background-color: #020305 !important;
        color: #00ff99 !important;
        border: 1px solid #00ff6622 !important;
        font-family: 'Courier New', Courier, monospace !important;
    }
    
    /* Ocultar elementos nativos de Streamlit sobrantes */
    #MainMenu, footer, header {
        visibility: hidden;
    }
</style>
""", unsafe_allow_html=True)

# 2. Gestión de estado
if "agente_corriendo" not in st.session_state:
    st.session_state.agente_corriendo = False

if "proceso" not in st.session_state:
    st.session_state.proceso = None

if "logs" not in st.session_state:
    st.session_state.logs = []

if "progreso_pct" not in st.session_state:
    st.session_state.progreso_pct = 0

if "stdout_queue" not in st.session_state:
    st.session_state.stdout_queue = None

if "thread" not in st.session_state:
    st.session_state.thread = None

# Verificación de credenciales Supabase
db_disponible = check_supabase()

# 3. Barra lateral
st.sidebar.title("🤖 IA Inmobiliaria")
st.sidebar.caption("Terminal de control")
st.sidebar.divider()

# Panel de Conexiones
st.sidebar.subheader("🔌 Estado de Conexiones")
if db_disponible:
    st.sidebar.markdown("<span style='color:#00ff66;'>🟢 Supabase: CONECTADO</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span style='color:#ff3333;'>🔴 Supabase: DESCONECTADO</span>", unsafe_allow_html=True)

if check_telegram():
    st.sidebar.markdown("<span style='color:#00ff66;'>🟢 Telegram: BOT ACTIVO</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span style='color:#ff3333;'>🔴 Telegram: ERROR/401</span>", unsafe_allow_html=True)

if check_gemini():
    st.sidebar.markdown("<span style='color:#00ff66;'>🟢 Gemini API: CONECTADO</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span style='color:#ffcc00;'>🟡 Gemini API: SIN CREDENCIALES</span>", unsafe_allow_html=True)

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

# Nuevos controles para el control del escaneo
indice_personalizado = st.sidebar.number_input(
    "Índice de inicio:",
    min_value=0,
    value=int(ultimo_indice),
    step=10,
    help="Índice de inicio para la consulta a Google Search. Precargado con el último guardado."
)

paginas_escanear = st.sidebar.slider(
    "Páginas a escanear (1 pág = 10 resultados):",
    min_value=1,
    max_value=5,
    value=1,
    step=1,
    help="Cantidad de páginas de resultados de Google a escanear en esta ejecución."
)

st.sidebar.divider()

# Botones de ejecución
col_iniciar, col_detener = st.sidebar.columns(2)

with col_iniciar:
    boton_deshabilitado = st.session_state.agente_corriendo or not db_disponible
    if st.button("RUN INDEX", use_container_width=True, disabled=boton_deshabilitado):
        st.sidebar.info("⚡ INICIALIZANDO...")
        st.session_state.agente_corriendo = True
        st.session_state.logs = ["[SYS]: Iniciando Agente Central Orquestador (Fase 1)..."]
        st.session_state.progreso_pct = 0
        
        try:
            # Calcular ruta absoluta de forma robusta
            dir_actual = os.path.dirname(os.path.abspath(__file__))
            ruta_orquestador = os.path.join(dir_actual, "agente_orquestador.py")
            
            # Ejecutamos agente_orquestador.py pasándole la plataforma, el índice inicial y las páginas
            proceso = subprocess.Popen(
                [sys.executable, ruta_orquestador, plataforma.lower(), str(indice_personalizado), str(paginas_escanear)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            st.session_state.proceso = proceso
            
            # Cola para lectura asíncrona de stdout
            q = queue.Queue()
            st.session_state.stdout_queue = q
            
            def leer_salida(stream, col_q):
                try:
                    for linea in iter(stream.readline, ''):
                        col_q.put(linea)
                except Exception:
                    pass
                finally:
                    stream.close()
                    
            t = threading.Thread(target=leer_salida, args=(proceso.stdout, q))
            t.daemon = True
            t.start()
            st.session_state.thread = t
            
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
                
        except Exception as e:
            st.session_state.agente_corriendo = False
            st.sidebar.error(f"Error al iniciar: {e}")

with col_detener:
    boton_detener_deshabilitado = not st.session_state.agente_corriendo or st.session_state.proceso is None
    if st.button("STOP", use_container_width=True, disabled=boton_detener_deshabilitado):
        if st.session_state.proceso:
            try:
                st.session_state.proceso.terminate()
                st.session_state.proceso.wait(timeout=3)
            except Exception:
                try:
                    st.session_state.proceso.kill()
                except Exception:
                    pass
        st.session_state.agente_corriendo = False
        st.session_state.logs.append("[SYS_STOP]: Ejecución cancelada por el usuario.")
        st.session_state.proceso = None
        st.session_state.thread = None
        st.session_state.stdout_queue = None
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()

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
st.title("🖥️ IA INMOBILIARIA - TERMINAL DE OPERACIONES")

# 5. Consola de Registro de Operaciones (Logs)
st.subheader("📟 Consola de Diagnóstico de Terminal")

if st.session_state.agente_corriendo:
    # 1. Leer todas las líneas de la cola
    q = st.session_state.get("stdout_queue")
    proceso = st.session_state.get("proceso")
    
    if q and proceso:
        lineas_nuevas = []
        while True:
            try:
                linea = q.get_nowait()
                lineas_nuevas.append(linea)
            except queue.Empty:
                break
                
        # 2. Procesar líneas nuevas
        for linea in lineas_nuevas:
            linea_clean = linea.strip()
            if linea_clean:
                # Comprobar si reporta porcentaje de progreso
                if linea_clean.startswith("[PROGRESS_PCT]"):
                    try:
                        pct = int(linea_clean.replace("[PROGRESS_PCT]", "").replace("%", "").strip())
                        st.session_state.progreso_pct = pct
                    except ValueError:
                        pass
                else:
                    st.session_state.logs.append(linea_clean)
                    
        # 3. Mostrar UI de progreso con spinner de caracteres ASCII
        col_pct, col_spinner, col_desc = st.columns([1, 1.2, 3.8])
        with col_pct:
            st.metric("PROGRESO", f"{st.session_state.progreso_pct}%")
        with col_spinner:
            spinner_frames = ["[ ⠋ ]", "[ ⠙ ]", "[ ⠹ ]", "[ ⠸ ]", "[ ⠼ ]", "[ ⠴ ]", "[ ⠦ ]", "[ ⠧ ]", "[ ⠇ ]", "[ ⠏ ]"]
            frame_idx = int(time.time() * 2) % len(spinner_frames)
            spinner_char = spinner_frames[frame_idx]
            st.metric("ESTADO", f"RUNNING {spinner_char}")
        with col_desc:
            st.progress(st.session_state.progreso_pct / 100.0)
            
        st.success(f"[SYS_ACTIVE]: Agente ejecutando búsqueda acotada de {plataforma.upper()} desde índice {indice_personalizado} ({paginas_escanear} pág/s).")
        
        # 4. Verificar si terminó
        retorno = proceso.poll()
        if retorno is not None:
            # Leer cualquier línea restante de la cola
            while True:
                try:
                    linea = q.get_nowait()
                    linea_clean = linea.strip()
                    if linea_clean and not linea_clean.startswith("[PROGRESS_PCT]"):
                        st.session_state.logs.append(linea_clean)
                except queue.Empty:
                    break
            
            # Terminar y limpiar estado
            st.session_state.agente_corriendo = False
            st.session_state.proceso = None
            st.session_state.thread = None
            st.session_state.stdout_queue = None
            
            if retorno == 0:
                st.toast("✅ Ejecución finalizada con éxito", icon="✅")
                st.session_state.logs.append("[SYS_FINISHED]: Proceso completado exitosamente.")
            else:
                st.toast("❌ El proceso falló o fue cancelado", icon="❌")
                st.session_state.logs.append(f"[SYS_ERROR]: El proceso terminó con código de error {retorno}.")
            
            time.sleep(1)
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        else:
            # Si sigue corriendo, dormir 0.5 segundos y relanzar rerun para refrescar
            time.sleep(0.5)
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
    else:
        # Fallback en caso de que esté en estado inconsistente
        st.session_state.agente_corriendo = False
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()

# Renderizado persistente de los logs acumulados en pantalla
if st.session_state.logs:
    st.code("\n".join(st.session_state.logs[-40:]), language="text")
else:
    st.info("[SYS_CONSOLE]: Esperando señal. Inicia la secuencia RUN INDEX desde el panel de control.")

st.divider()

# 6. Resultados y Capturas Encontradas (Al pie de la página, persistente)
st.subheader("📋 Resultados y Capturas Encontradas")

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
                        help="Abrir la publicación original en una pestaña nueva",
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
