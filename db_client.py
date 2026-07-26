import os
import hashlib
from datetime import datetime, timezone
from supabase import create_client, Client

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Configuración de variables de entorno para Supabase
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

SUPABASE_URL = obtener_secreto("SUPABASE_URL")
SUPABASE_KEY = obtener_secreto("SUPABASE_KEY")


def obtener_supabase_client() -> Client:
    """Inicializa y retorna el cliente de Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Faltan las variables de entorno SUPABASE_URL o SUPABASE_KEY. "
            "Por favor, configúralas para conectar con la base de datos cloud."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def validar_conexion_supabase() -> bool:
    """Valida la conexión a Supabase intentando realizar una consulta simple."""
    try:
        supabase = obtener_supabase_client()
        # Intentamos obtener un registro de prueba de estado_scraper
        supabase.table("estado_scraper").select("plataforma").limit(1).execute()
        return True
    except Exception as e:
        print(f"[DB] Error de validación de conexión: {e}")
        return False

def obtener_ultimo_indice(plataforma: str) -> int:
    """Obtiene el último índice de paginación de la plataforma especificada."""
    try:
        supabase = obtener_supabase_client()
        plat_lower = plataforma.lower().strip()
        response = supabase.table("estado_scraper").select("ultimo_indice").eq("plataforma", plat_lower).execute()
        if response.data:
            return response.data[0]["ultimo_indice"]
        else:
            # Inicializar registro si no existe
            supabase.table("estado_scraper").insert({"plataforma": plat_lower, "ultimo_indice": 0}).execute()
            return 0
    except Exception as e:
        print(f"[DB ERROR] No se pudo obtener el último índice para {plataforma}: {e}")
        return 0

def actualizar_indice(plataforma: str, nuevo_indice: int):
    """Actualiza o inserta el último índice de paginación para una plataforma."""
    try:
        supabase = obtener_supabase_client()
        plat_lower = plataforma.lower().strip()
        supabase.table("estado_scraper").upsert({
            "plataforma": plat_lower,
            "ultimo_indice": nuevo_indice,
            "actualizado_en": datetime.now(timezone.utc).isoformat()
        }, on_conflict="plataforma").execute()
        print(f"[DB] Índice de paginación para {plataforma} actualizado a {nuevo_indice}.")
    except Exception as e:
        print(f"[DB ERROR] No se pudo actualizar el índice para {plataforma}: {e}")

def guardar_captacion(titulo: str, link: str, telefono: str, plataforma: str, analisis_ia: str):
    """Guarda una propiedad captada en Supabase previniendo duplicados mediante el hash del link."""
    try:
        supabase = obtener_supabase_client()
        link_strip = link.strip()
        hash_url = hashlib.md5(link_strip.encode('utf-8')).hexdigest()
        
        data = {
            "titulo": titulo,
            "link": link_strip,
            "telefono": telefono,
            "plataforma": plataforma.lower().strip(),
            "hash_url": hash_url,
            "analisis_ia": analisis_ia
        }
        
        # Guardar o actualizar captación si ya existe mediante hash_url
        supabase.table("captaciones").upsert(data, on_conflict="hash_url").execute()
        print(f"[DB] Captación registrada/actualizada exitosamente: '{titulo[:40]}...'")
    except Exception as e:
        print(f"[DB ERROR] No se pudo guardar la captación: {e}")

def obtener_captaciones_recientes(limit: int = 50):
    """Obtiene una lista de las últimas captaciones ordenadas por fecha de creación descendente."""
    try:
        supabase = obtener_supabase_client()
        response = supabase.table("captaciones").select("*").order("creado_en", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[DB ERROR] No se pudo obtener las captaciones recientes: {e}")
        return []

def existe_captacion_por_link(link: str) -> bool:
    """Verifica si ya existe una captación con este link en la base de datos."""
    try:
        supabase = obtener_supabase_client()
        link_strip = link.strip()
        hash_url = hashlib.md5(link_strip.encode('utf-8')).hexdigest()
        response = supabase.table("captaciones").select("id").eq("hash_url", hash_url).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"[DB ERROR] Error al verificar existencia por link: {e}")
        return False

