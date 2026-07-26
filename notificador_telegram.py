import pandas as pd
import requests
import time
import os

# --- CONFIGURACIÓN DE TELEGRAM ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
def obtener_secreto(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    val = os.getenv(key)
    if val is not None:
        return val.strip()
    return default

TOKEN = obtener_secreto("TELEGRAM_BOT_TOKEN")
CHAT_ID = obtener_secreto("TELEGRAM_CHAT_ID")
# ---------------------------------

def validar_conexion_telegram() -> bool:
    """Verifica si el token de Telegram es válido consultando a la API."""
    if not TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    try:
        respuesta = requests.get(url, timeout=10)
        return respuesta.status_code == 200
    except Exception:
        return False

def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        respuesta = requests.post(url, json=payload)
        return respuesta.status_code == 200
    except Exception as e:
        print(f"[ERROR] Falla de conexión con Telegram: {e}")
        return False

def main():
    print("=====================================================")
    print("🤖 INICIANDO ENLACE TELEGRAM (SEGUNDO PLANO) 🤖")
    print("=====================================================\n")
    
    if not validar_conexion_telegram():
        print("[ERROR] El token de Telegram no es válido o no está configurado. Verifica tu .env")
        return
        
    archivo_excel = "contactos_captacion.xlsx"
    
    if not os.path.exists(archivo_excel):
        print("[ERROR] No se encontró el archivo Excel base.")
        return
        
    df = pd.read_excel(archivo_excel)
    
    # Crear columna de control si no existe
    if "Notificado" not in df.columns:
        df["Notificado"] = "NO"
        print("[SYS] Columna de memoria 'Notificado' agregada al Excel.")
        
    # Filtrar los que no fueron notificados
    pendientes = df[df["Notificado"] == "NO"]
    
    if pendientes.empty:
        print("[SYS] 💤 No hay propiedades nuevas pendientes de notificación.")
        return
        
    print(f"[SYS] Transmitiendo {len(pendientes)} propiedades vía API de Telegram...")
    indices_actualizados = []
    
    for index, row in pendientes.iterrows():
        tipo = row.get("Tipo Propiedad", "Propiedad")
        analisis = row.get("Análisis IA", "Sin análisis")
        link = row.get("Link", "")
        
        mensaje = f"🏢 *{tipo}*\n💡 {analisis}\n🔗 [Abrir Publicación]({link})"
        
        if enviar_mensaje_telegram(mensaje):
            indices_actualizados.append(index)
            print(f"[SYS] ✅ Paquete {index} enviado exitosamente.")
        else:
            print(f"[ERROR] ❌ Falló el envío del paquete {index}.")
            
        # Pausa en segundo plano de 2 segundos para no saturar la API
        time.sleep(2)
            
    # Actualizar Excel
    for idx in indices_actualizados:
        df.at[idx, "Notificado"] = "SÍ"
        
    df.to_excel(archivo_excel, index=False, engine='openpyxl')
    print("\n[SYS] 📡 Transmisión finalizada y base de datos actualizada.")

if __name__ == "__main__":
    main()
