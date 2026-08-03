import sys
import os
import time
import random
import requests
import json
import hashlib
import urllib.parse
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import db_client

# Cargar variables de entorno explícitamente al inicio
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Importar validadores
try:
    from notificador_telegram import validar_conexion_telegram
except ImportError:
    def validar_conexion_telegram():
        return False

def espera_humana(min_seg=2.0, max_seg=4.5):
    """Simula los tiempos de reacción de un humano para evitar bloqueos."""
    time.sleep(random.uniform(min_seg, max_seg))

def clasificar_publicacion_local(titulo: str, texto: str, link: str) -> dict:
    """
    Clasifica de forma 100% local y gratuita (sin IA externa) si la publicación
    se refiere a una venta de propiedad en Mar del Plata por Dueño Directo,
    filtrando rigurosamente inmobiliarias y intermediarios.
    """
    text_to_check = f"{titulo} {texto}".lower()
    
    # 1. Palabras clave de Mar del Plata / Costa Atlántica
    mdp_keywords = [
        "mar del plata", "mdp", "punta mogotes", "luro", "chauvin", "chauvín",
        "playa grande", "stella maris", "constitucion", "constitución", "parque luro",
        "la perla", "costa atlantica", "costa atlántica", "güemes", "guemes",
        "los troncos", "caisamar", "alvarado", "plaza mitre", "macrocentro"
    ]
    has_mdp = any(kw in text_to_check for kw in mdp_keywords) or "mar del plata" in link.lower() or "mdp" in link.lower()
    
    # 2. Palabras clave de Propiedades
    prop_keywords = [
        "casa", "depto", "departamento", "duplex", "dúplex", "lote", "terreno",
        "cochera", "ph", "monoambiente", "ambiente", "ambientes", "propiedad", "inmueble"
    ]
    has_property = any(pw in text_to_check for pw in prop_keywords)
    
    # 3. Palabras clave de Ventas/Oportunidades
    sale_keywords = ["vende", "vendo", "venta", "compro", "oportunidad", "u$d", "usd", "dolares", "dólares", "pesos", "valor", "precio"]
    has_sale = any(sw in text_to_check for sw in sale_keywords)
    
    # 4. Palabras clave de Dueño Directo / Particular (Positivas)
    owner_keywords = [
        "dueño directo", "dueño vende", "vende dueño", "sin comisión", "sin comision",
        "particular", "propietario", "sin intermediario", "sin intermediarios",
        "dueno directo", "dueno vende", "trato directo", "sin expensas ni comision"
    ]
    is_owner = any(okw in text_to_check for okw in owner_keywords) or "dueño" in text_to_check or "dueno" in text_to_check
    
    # 5. Palabras clave de Inmobiliarias / Brokers / Intermediarios (Filtro Negativo Estricto)
    broker_keywords = [
        "inmobiliaria", "inmobiliarias", "remax", "re/max", "broker", "bienes raices",
        "bienes raíces", "gestion inmobiliaria", "gestión inmobiliaria", "comisión",
        "comision", "honorarios", "asesor inmobiliario", "estudio inmobiliario",
        "martillero", "matrícula", "matricula"
    ]
    is_broker = any(bkw in text_to_check for bkw in broker_keywords)
    
    # 6. Alquileres tradicionales (para descartar si no son ventas)
    rent_keywords = ["alquiler", "alquilo", "alquileres", "temporario", "mensual"]
    is_rent = any(rkw in text_to_check for rkw in rent_keywords) and not ("vendo" in text_to_check or "venta" in text_to_check or "dueño" in text_to_check)

    # Regla de clasificación estricta
    cumple = False
    if not is_broker and not is_rent and (has_property or is_owner or has_mdp):
        # Excluir vehículos a menos que explícitamente mencione inmuebles
        if not ("auto" in text_to_check or "moto" in text_to_check or "camioneta" in text_to_check) or has_property:
            cumple = True
            
    # Extraer teléfono con Expresión Regular adaptada a Argentina
    telefono = "A revisar"
    phones = re.findall(r'(?:\+?54[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', text_to_check)
    valid_phones = []
    for ph in phones:
        digits = re.sub(r'\D', '', ph)
        if 8 <= len(digits) <= 13:
            if not digits.startswith(('202', '203', '2024', '2025', '2026')):
                valid_phones.append(ph.strip())
    if valid_phones:
        telefono = valid_phones[0]
        
    # Tipo de contacto
    contacto = "Dueño Directo" if (is_owner or not is_broker) else "Inmobiliaria / Intermediario"
    
    # Tipo de propiedad
    tipo_prop = "Propiedad"
    if "casa" in text_to_check:
        tipo_prop = "Casa"
    elif "depto" in text_to_check or "departamento" in text_to_check:
        tipo_prop = "Departamento"
    elif "duplex" in text_to_check or "dúplex" in text_to_check:
        tipo_prop = "Duplex"
    elif "terreno" in text_to_check or "lote" in text_to_check:
        tipo_prop = "Terreno"

    # Detalles del análisis
    detalles = []
    if is_owner:
        detalles.append("Palabras clave Dueño Directo")
    if is_broker:
        detalles.append("Inmobiliaria detectada")
    if has_property:
        detalles.append("Tipo Inmueble identificado")
    if has_mdp:
        detalles.append("Ubicación Mar del Plata ok")
        
    analisis = f"Filtro Heurístico Local: {', '.join(detalles) if detalles else 'Propiedad en Mar del Plata'}. Teléfono: {telefono}."

    return {
        "Cumple": cumple,
        "Tipo Propiedad": tipo_prop,
        "Teléfono": telefono,
        "Dueño/Contacto": contacto,
        "Análisis IA": analisis
    }

def extraer_candidatos_generico(html_text, plataforma):
    """
    Parsea el HTML buscando enlaces limpios de la plataforma especificada,
    extrayendo título y snippet de texto adyacente.
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    candidatos = []
    
    for a in soup.find_all('a', href=True):
        raw_link = a['href']
        
        # Desempaquetar redirecciones
        if '/url?q=' in raw_link:
            try:
                raw_link = raw_link.split('/url?q=')[1].split('&')[0]
            except Exception:
                pass
                
        if 'uddg=' in raw_link:
            try:
                raw_link = raw_link.split('uddg=')[1].split('&')[0]
            except Exception:
                pass
                
        link = urllib.parse.unquote(raw_link)
        
        if not link.startswith('https://') or 'google.com' in link or 'duckduckgo.com' in link:
            continue
            
        # Filtrar por plataforma
        if plataforma == "instagram" and "instagram.com" not in link:
            continue
        if plataforma == "facebook" and "facebook.com" not in link:
            continue
            
        # Limpieza de URL (usando db_client.normalizar_url)
        clean_link = db_client.normalizar_url(link)
        if not clean_link or clean_link.endswith(".com") or clean_link.endswith(".com/"):
            continue
            
        # Extraer título y snippet
        titulo = a.get_text(strip=True)
        h3 = a.find('h3')
        if h3:
            titulo = h3.get_text(strip=True)
            
        snippet = ""
        parent = a.parent
        for _ in range(4):
            if not parent:
                break
            text = parent.get_text(" ", strip=True)
            if len(text) > len(titulo) + 20:
                snippet = text
                break
            parent = parent.parent
            
        if not titulo or len(titulo) < 5:
            titulo = snippet[:60] + "..." if len(snippet) > 10 else f"Publicación {plataforma.capitalize()}"
            
        if clean_link not in [c['link'] for c in candidatos]:
            candidatos.append({
                'titulo': titulo.strip(),
                'link': clean_link,
                'texto': snippet.strip() or titulo.strip()
            })
            
    return candidatos

def realizar_busqueda(query, plataforma, start_val=0):
    """
    Realiza búsqueda HTTP en Google Search o DuckDuckGo HTML Search de forma gratuita.
    """
    headers_list = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"}
    ]
    headers = random.choice(headers_list)
    
    # 1. Intentar Google
    google_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&start={start_val}"
    print(f"[HTTP] Buscando en Google: {google_url}")
    try:
        response = requests.get(google_url, headers=headers, timeout=15)
        if response.status_code == 200 and "detected unusual traffic" not in response.text:
            candidatos = extraer_candidatos_generico(response.text, plataforma)
            if candidatos:
                print(f"[HTTP] Google retornó {len(candidatos)} candidatos.")
                return candidatos
            else:
                print("[HTTP] Google sin candidatos en respuesta.")
        else:
            print(f"[HTTP] Google respuesta no-200 o captcha (código {response.status_code}).")
    except Exception as e:
        print(f"[HTTP] Error consultando Google: {e}")
        
    time.sleep(1)
    
    # 2. Fallback a DuckDuckGo HTML
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    print(f"[HTTP] [FALLBACK] Buscando en DuckDuckGo: {ddg_url}")
    try:
        response = requests.get(ddg_url, headers=headers, timeout=15)
        if response.status_code == 200:
            candidatos = extraer_candidatos_generico(response.text, plataforma)
            print(f"[HTTP] DuckDuckGo retornó {len(candidatos)} candidatos.")
            return candidatos
    except Exception as e:
        print(f"[HTTP] Error consultando DuckDuckGo: {e}")
        
    return []

def enviar_a_telegram(prop):
    """Envía alertas del inmueble captado por Telegram."""
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    
    if not TOKEN or not CHAT_ID:
        print("[TELEGRAM] Omitiendo notificación: Credenciales ausentes en el .env.")
        return
        
    url_telegram = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    tipo = prop.get("Tipo Propiedad", "Propiedad")
    analisis = prop.get("Análisis IA", "Sin detalles")
    link = prop.get("Link", "")
    telefono = prop.get("Teléfono", "A revisar")
    contacto = prop.get("Dueño/Contacto", "Dueño Directo")
    
    mensaje = (
        f"🏢 *NUEVA CAPTACIÓN DUEÑO DIRECTO ({prop.get('Plataforma', 'Redes').upper()})*\n\n"
        f"📍 *Tipo:* {tipo}\n"
        f"👤 *Contacto:* {contacto}\n"
        f"📞 *Teléfono:* {telefono}\n"
        f"💡 *Detalles:* {analisis}\n\n"
        f"🔗 [Abrir Publicación]({link})"
    )
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url_telegram, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"[TELEGRAM] ✅ Notificación enviada.")
        else:
            print(f"[TELEGRAM] ❌ Error en envío (Código {r.status_code}).")
    except Exception as e:
        print(f"[TELEGRAM] [ERROR] Falló enlace con Telegram: {e}")

class AgenteBuscador:
    """
    Agente Buscador (Scraper): Especializado en rastrear publicaciones y clasificar
    dueños directos en Mar del Plata mediante heurística local de cero costo.
    """
    def armar_queries(self, plataforma: str) -> list:
        plat = plataforma.lower().strip()
        if plat == "instagram":
            return [
                'site:instagram.com "dueño directo" "mar del plata"',
                'site:instagram.com "dueño vende" "mar del plata"',
                'site:instagram.com "sin comisión" "mar del plata" propiedad',
                'site:instagram.com "particular vende" "mar del plata"'
            ]
        elif plat == "facebook":
            return [
                'site:facebook.com "dueño directo" "mar del plata"',
                'site:facebook.com "dueño vende" "mar del plata"',
                'site:facebook.com "sin comisión" "mar del plata" propiedad',
                'site:facebook.com "particular vende" "mar del plata"'
            ]
        else:
            return [
                f'site:{plat}.com "dueño directo" "mar del plata"',
                f'site:{plat}.com "dueño vende" "mar del plata"'
            ]

    def buscar_candidatos(self, plataforma: str, indice_inicial: int = 0, paginas_a_escanear: int = 1) -> list:
        queries = self.armar_queries(plataforma)
        anuncios_candidatos = []
        total_queries = paginas_a_escanear * len(queries)

        for p in range(paginas_a_escanear):
            start_val = indice_inicial + (p * 10)
            print(f"[BUSCADOR] Escaneando página {p + 1}/{paginas_a_escanear} (start={start_val})...")
            for query_idx, query in enumerate(queries):
                query_num = p * len(queries) + query_idx + 1
                progreso_porcentaje = int((query_num / total_queries) * 100)
                print(f"[PROGRESS_PCT] {progreso_porcentaje}%")

                tanda = realizar_busqueda(query, plataforma, start_val)
                for item in tanda:
                    if item['link'] not in [a['link'] for a in anuncios_candidatos]:
                        anuncios_candidatos.append(item)

                if query_num < total_queries:
                    espera_humana(2.5, 4.5)

        return anuncios_candidatos

    def clasificar_publicacion(self, titulo: str, texto: str, link: str) -> dict:
        return clasificar_publicacion_local(titulo, texto, link)


def main():
    # Delegar la ejecución completa al Agente Central Orquestador
    from agente_orquestador import AgenteOrquestador
    
    plataforma = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "instagram"
    indice_inicial = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    paginas = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1

    orquestador = AgenteOrquestador(
        plataforma=plataforma,
        indice_inicial=indice_inicial,
        paginas_escanear=paginas
    )
    orquestador.ejecutar_ciclo()

if __name__ == "__main__":
    main()