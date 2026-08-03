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

import urllib.parse

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

def normalizar_url(url: str) -> str:
    """
    Normaliza una URL a su forma canónica para evitar duplicados por diferencias menores
    (ej: parámetros de tracking como ?igsh=, slashes finales, diferencias de mayúsculas).
    """
    if not url:
        return ""
    url_strip = url.strip()
    try:
        parsed = urllib.parse.urlparse(url_strip)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        
        # Eliminar parámetros comunes de tracking de redes sociales
        query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        params_a_remover = {'igsh', 'ref', 'fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 's', 't'}
        query_filtrada = {k: v for k, v in query_params.items() if k.lower() not in params_a_remover}
        query_str = urllib.parse.urlencode(query_filtrada, doseq=True)
        
        url_canonized = urllib.parse.urlunparse((scheme, netloc, path, parsed.params, query_str, parsed.fragment))
        return url_canonized
    except Exception:
        return url_strip

def generar_hash_url(link: str) -> str:
    """Genera un hash MD5 unívoco para la URL normalizada."""
    url_norm = normalizar_url(link)
    return hashlib.md5(url_norm.encode('utf-8')).hexdigest()

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

def existe_captacion_por_link(link: str) -> bool:
    """Verifica de forma estricta si ya existe una captación con este link (o su hash) en la base de datos."""
    if not link:
        return False
    try:
        supabase = obtener_supabase_client()
        hash_url = generar_hash_url(link)
        response = supabase.table("captaciones").select("id").eq("hash_url", hash_url).execute()
        if response.data and len(response.data) > 0:
            return True
            
        # Fallback de comprobación directa por link normalizado
        link_norm = normalizar_url(link)
        response_link = supabase.table("captaciones").select("id").eq("link", link_norm).execute()
        return len(response_link.data) > 0 if response_link.data else False
    except Exception as e:
        print(f"[DB ERROR] Error al verificar existencia por link: {e}")
        return False

def guardar_captacion(titulo: str, link: str, telefono: str, plataforma: str, analisis_ia: str) -> tuple:
    """
    Guarda una propiedad captada en Supabase previniendo duplicados mediante el hash del link.
    Si la URL o su hash ya existen en Supabase, se descarta y no se duplica.
    Devuelve (True, "Mensaje success") o (False, "Duplicado / Error").
    """
    try:
        link_norm = normalizar_url(link)
        hash_url = generar_hash_url(link)
        
        if existe_captacion_por_link(link_norm):
            print(f"[DB DUPLICADO] Omitiendo '{link_norm}' (ya registrado en Supabase).")
            return False, "Duplicado omitido (ya registrado)"
            
        supabase = obtener_supabase_client()
        data = {
            "titulo": titulo.strip(),
            "link": link_norm,
            "telefono": telefono.strip(),
            "plataforma": plataforma.lower().strip(),
            "hash_url": hash_url,
            "analisis_ia": analisis_ia
        }
        
        supabase.table("captaciones").upsert(data, on_conflict="hash_url").execute()
        print(f"[DB] ✅ Captación registrada exitosamente: '{titulo[:40]}...'")
        return True, "Guardado exitosamente"
    except Exception as e:
        print(f"[DB ERROR] No se pudo guardar la captación: {e}")
        return False, f"Error al guardar: {e}"

def obtener_captaciones_recientes(limit: int = 50):
    """Obtiene una lista de las últimas captaciones ordenadas por fecha de creación descendente."""
    try:
        supabase = obtener_supabase_client()
        response = supabase.table("captaciones").select("*").order("creado_en", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[DB ERROR] No se pudo obtener las captaciones recientes: {e}")
        return []


