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

def espera_humana(min_seg=2.0, max_seg=5.0):
    """Simula los tiempos de reacción de un humano para evitar bloqueos."""
    time.sleep(random.uniform(min_seg, max_seg))

def clasificar_publicacion_local(titulo: str, texto: str, link: str) -> dict:
    """
    Clasifica de forma 100% local y gratuita (sin IA externa) si la publicación
    se refiere a una venta de propiedad en Mar del Plata, y si es dueño directo.
    """
    text_to_check = f"{titulo} {texto}".lower()
    
    # 1. Palabras clave de Mar del Plata / Costa Atlántica
    mdp_keywords = ["mar del plata", "mdp", "punta mogotes", "luro", "chauvin", "playa grande", "stella maris", "constitucion", "parque luro", "la perla", "costa atlantica", "costa atlántica"]
    has_mdp = any(kw in text_to_check for kw in mdp_keywords) or "mar del plata" in link.lower()
    
    # 2. Palabras clave de Propiedades
    prop_keywords = ["casa", "depto", "departamento", "duplex", "dúplex", "lote", "terreno", "cochera", "ph", "monoambiente", "ambiente", "ambientes", "propiedad", "inmueble"]
    has_property = any(pw in text_to_check for pw in prop_keywords)
    
    # 3. Palabras clave de Ventas/Oportunidades
    sale_keywords = ["vende", "vendo", "venta", "compro", "oportunidad", "u$d", "usd", "dolares", "dólares", "pesos", "valor", "precio"]
    has_sale = any(sw in text_to_check for sw in sale_keywords)
    
    # 4. Palabras clave de Dueño Directo / Particular
    owner_keywords = ["dueño", "dueno", "directo", "particular", "propietario", "sin comision", "sin comisión"]
    is_owner = any(okw in text_to_check for okw in owner_keywords)
    
    # 5. Palabras clave de Inmobiliarias / Brokers
    broker_keywords = ["inmobiliaria", "propiedades", "remax", "re/max", "broker", "bienes raices", "gestion inmobiliaria"]
    is_broker = any(bkw in text_to_check for bkw in broker_keywords)
    
    # 6. Alquileres tradicionales (para descartar si no son ventas)
    rent_keywords = ["alquiler", "alquilo", "alquileres", "temporario", "mensual"]
    is_rent = any(rkw in text_to_check for rkw in rent_keywords) and not ("vendo" in text_to_check or "venta" in text_to_check)

    # Determinar si cumple
    cumple = False
    if (has_property or is_owner or has_mdp) and not is_rent:
        # Excluir vehículos a menos que explícitamente mencione propiedades
        if not ("auto" in text_to_check or "moto" in text_to_check or "camioneta" in text_to_check) or has_property:
            cumple = True
            
    # Extraer teléfono con Expresión Regular
    # Patrones comunes de teléfonos de Argentina
    telefono = "A revisar"
    # Buscar patrones que parezcan teléfonos
    phones = re.findall(r'(?:\+?54[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', text_to_check)
    valid_phones = []
    for ph in phones:
        digits = re.sub(r'\D', '', ph)
        if 8 <= len(digits) <= 13:
            # Descartar años comunes
            if not digits.startswith(('202', '203')):
                valid_phones.append(ph.strip())
    if valid_phones:
        telefono = valid_phones[0]
        
    # Clasificar el tipo de contacto
    contacto = "Dueño Directo" if is_owner else ("Inmobiliaria / Captación" if is_broker else "Contacto Directo")
    
    # Determinar el tipo de propiedad
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
        detalles.append("Particular/Dueño Directo")
    if is_broker:
        detalles.append("Inmobiliaria/Broker")
    if has_property:
        detalles.append("Inmueble identificado")
    if has_mdp:
        detalles.append("Zona Mar del Plata")
        
    analisis = f"Filtro Heurístico Local: {', '.join(detalles) if detalles else 'Propiedad detectada'}. Teléfono: {telefono}."

    return {
        "Cumple": cumple,
        "Tipo Propiedad": tipo_prop,
        "Teléfono": telefono,
        "Dueño/Contacto": contacto,
        "Análisis IA": analisis
    }

def extraer_candidatos_generico(html_text, plataforma):
    """
    Parsea de forma genérica el HTML buscando enlaces limpios de la plataforma
    especificada, junto con títulos y fragmentos de texto adyacentes.
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    candidatos = []
    
    for a in soup.find_all('a', href=True):
        raw_link = a['href']
        
        # Desempaquetar si viene de redirección de Google
        if '/url?q=' in raw_link:
            try:
                raw_link = raw_link.split('/url?q=')[1].split('&')[0]
            except Exception:
                pass
                
        # Desempaquetar si viene de redirección de DuckDuckGo
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
            
        # Limpieza de URL (eliminar query parameters como ?igsh=...)
        try:
            parsed_url = urllib.parse.urlparse(link)
            clean_link = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            # Remover barra final si existe para consistencia
            if clean_link.endswith('/'):
                clean_link = clean_link[:-1]
                
            # Evitar capturar sólo la página de inicio
            if parsed_url.path == "/" or not parsed_url.path:
                continue
        except Exception:
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
            titulo = snippet[:60] + "..." if len(snippet) > 10 else f"Publicación de {plataforma.capitalize()}"
            
        if clean_link not in [c['link'] for c in candidatos]:
            candidatos.append({
                'titulo': titulo.strip(),
                'link': clean_link,
                'texto': snippet.strip() or titulo.strip()
            })
            
    return candidatos

def realizar_busqueda(query, plataforma, start_val=0):
    """
    Realiza una búsqueda HTTP en Google Search y, si se detecta un bloqueo o
    no hay resultados, recurre a DuckDuckGo HTML Search de forma gratuita.
    """
    headers_list = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"},
        {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    ]
    headers = random.choice(headers_list)
    
    # 1. Intentar con Google
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
                print("[HTTP] Google no arrojó candidatos en el HTML.")
        else:
            print(f"[HTTP] Google bloqueado (código {response.status_code}) o captcha detectado.")
    except Exception as e:
        print(f"[HTTP] Error consultando Google: {e}")
        
    # Espera corta antes de fallback
    time.sleep(1)
    
    # 2. Fallback a DuckDuckGo HTML Search (Cero costo y alta tolerancia a scrapers)
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    print(f"[HTTP] [FALLBACK] Buscando en DuckDuckGo: {ddg_url}")
    try:
        response = requests.get(ddg_url, headers=headers, timeout=15)
        if response.status_code == 200:
            candidatos = extraer_candidatos_generico(response.text, plataforma)
            print(f"[HTTP] DuckDuckGo retornó {len(candidatos)} candidatos.")
            return candidatos
        else:
            print(f"[HTTP] DuckDuckGo falló con código {response.status_code}.")
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
        f"🏢 *NUEVA CAPTACIÓN GRATUITA ({prop.get('Plataforma', 'Redes').upper()})*\n\n"
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
            print(f"[TELEGRAM] ✅ Notificación enviada correctamente.")
        else:
            print(f"[TELEGRAM] ❌ Falló envío (Código {r.status_code}): {r.text}")
    except Exception as e:
        print(f"[TELEGRAM] [ERROR] Falló enlace con Telegram: {e}")

def main():
    # Asegurar codificación UTF-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    print("=====================================================")
    print("🤖 INICIANDO AGENTE SCRAPER AUTOMÁTICO - COSTO CERO 🤖")
    print("=====================================================\n")

    # 1. Verificación de conexiones de servicios
    print("[INIT] Verificando conexiones de servicios...")
    if db_client.validar_conexion_supabase():
        print("[INIT] ✅ Supabase: CONECTADO")
    else:
        print("[INIT] ❌ Supabase: DESCONECTADO (revisar credenciales)")
        
    if validar_conexion_telegram():
        print("[INIT] ✅ Telegram: BOT ACTIVO")
    else:
        print("[INIT] ⚠️ Telegram: DESCONECTADO o TOKEN INVÁLIDO")

    # 2. Argumentos de entrada
    plataforma = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "instagram"
    
    if len(sys.argv) > 2:
        try:
            indice_inicial = int(sys.argv[2])
        except ValueError:
            indice_inicial = db_client.obtener_ultimo_indice(plataforma)
    else:
        indice_inicial = db_client.obtener_ultimo_indice(plataforma)

    paginas_a_escanear = 1
    if len(sys.argv) > 3:
        try:
            paginas_a_escanear = int(sys.argv[3])
        except ValueError:
            pass

    print(f"\n[CONFIG] Plataforma: {plataforma.upper()}")
    print(f"[CONFIG] Índice inicial: {indice_inicial}")
    print(f"[CONFIG] Páginas a escanear: {paginas_a_escanear}")

    # 3. Armado de queries
    if plataforma == "instagram":
        queries = [
            'site:instagram.com "dueño vende" "mar del plata"',
            'site:instagram.com "dueño directo" "mar del plata"',
            'site:instagram.com "inmobiliarias mar del plata"',
            'site:instagram.com "captaciones costa atlántica"'
        ]
    elif plataforma == "facebook":
        queries = [
            'site:facebook.com "dueño vende" "mar del plata"',
            'site:facebook.com "dueño directo" "mar del plata"',
            'site:facebook.com "inmobiliarias mar del plata"',
            'site:facebook.com "captaciones costa atlántica"'
        ]
    else:
        queries = [
            f'site:{plataforma}.com "dueño directo" "mar del plata"',
            f'site:{plataforma}.com "inmobiliarias mar del plata"'
        ]

    anuncios_candidatos = []
    paginas_exitosas = 0

    # 4. Escaneo
    for p in range(paginas_a_escanear):
        start_val = indice_inicial + (p * 10)
        print(f"\n[PAGE] Escaneando página {p + 1}/{paginas_a_escanear} (start={start_val})...")
        
        pagina_ok = True
        for query_idx, query in enumerate(queries):
            # Reportar progreso
            query_num = p * len(queries) + query_idx + 1
            total_queries = paginas_a_escanear * len(queries)
            progreso_porcentaje = int((query_num / total_queries) * 100)
            print(f"[PROGRESS_PCT] {progreso_porcentaje}%")
            
            candidatos_tanda = realizar_busqueda(query, plataforma, start_val)
            
            for c in candidatos_tanda:
                if c['link'] not in [a['link'] for a in anuncios_candidatos]:
                    anuncios_candidatos.append(c)
            
            # Pausa humana para evitar bloqueos
            if query_num < total_queries:
                espera_humana(3.0, 6.0)
                
        paginas_exitosas += 1

    print(f"\n[SYS] Fin del escaneo. Candidatos únicos encontrados: {len(anuncios_candidatos)}")

    # 5. Procesamiento y Clasificación Local
    nuevos_registros = 0
    for idx, anuncio in enumerate(anuncios_candidatos):
        link_url = anuncio['link']
        
        # Verificar duplicado
        if db_client.existe_captacion_por_link(link_url):
            print(f"[DUPLICADO] Omitiendo '{link_url}' (ya en Supabase).")
            continue
            
        print(f"\n[CANDIDATO {idx+1}] Evaluando: {link_url}")
        
        # Clasificador Heurístico Cero Costo
        resultado = clasificar_publicacion_local(anuncio['titulo'], anuncio['texto'], link_url)
        
        if resultado.get("Cumple") is True:
            # Guardar en base de datos
            db_client.guardar_captacion(
                titulo=anuncio['titulo'],
                link=link_url,
                telefono=resultado.get("Teléfono", "A revisar"),
                plataforma=plataforma,
                analisis_ia=resultado.get("Análisis IA", "Captación local")
            )
            
            # Enviar alerta por Telegram
            resultado["Link"] = link_url
            resultado["Plataforma"] = plataforma
            enviar_a_telegram(resultado)
            nuevos_registros += 1
        else:
            # Guardar como descartado para registrar el hash y no volver a procesar
            db_client.guardar_captacion(
                titulo=anuncio['titulo'],
                link=link_url,
                telefono="Descartado",
                plataforma=plataforma,
                analisis_ia="Descartado localmente (no cumple filtros)."
            )
            print(f"[IA] Publicación descartada. Hash registrado.")
            
        espera_humana(1.0, 3.0)

    # 6. Actualización del puntero de paginación
    nuevo_indice = indice_inicial + (paginas_exitosas * 10)
    db_client.actualizar_indice(plataforma, nuevo_indice)
    
    print(f"\n=====================================================")
    print(f"✅ CICLO SCRAPER FINALIZADO.")
    print(f"📊 Nuevas captaciones registradas: {nuevos_registros}")
    print(f"🔑 Paginación actualizada a: {nuevo_indice}")
    print("=====================================================")

if __name__ == "__main__":
    main()