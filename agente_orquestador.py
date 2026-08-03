"""
AGENTE CENTRAL (ORQUESTADOR) - SISTEMA MULTI-AGENTE A COSTO CERO
Fase 1: Coordinación de Agentes, Anti-duplicados estricto y Registro Cloud.
"""
import sys
import os
import time
from datetime import datetime, timezone

import db_client
from agente_scraper import AgenteBuscador, enviar_a_telegram

# Cargar variables de entorno si existen
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from notificador_telegram import validar_conexion_telegram
except ImportError:
    def validar_conexion_telegram():
        return False

class AgenteOrquestador:
    """
    Agente Central Orquestador que coordina el flujo de trabajo multi-agente:
    - Invoca al Agente Buscador (agente_scraper)
    - Aplica filtrado anti-duplicados estricto por URL/Hash (db_client)
    - Clasifica mediante heurística local (Dueño Directo vs Inmobiliaria)
    - Registra en Supabase y notifica vía Telegram
    - Mantiene actualizado el estado del escáner en Supabase
    """
    def __init__(self, plataforma: str = "instagram", indice_inicial: int = None, paginas_escanear: int = 1):
        self.plataforma = plataforma.lower().strip()
        self.paginas_escanear = max(1, paginas_escanear)
        
        # Cargar puntero de paginación desde Supabase si no se proporciona
        if indice_inicial is None:
            self.indice_inicial = db_client.obtener_ultimo_indice(self.plataforma)
        else:
            self.indice_inicial = max(0, indice_inicial)
            
        self.buscador = AgenteBuscador()
        self.metricas = {
            "candidatos_encontrados": 0,
            "duplicados_omitidos": 0,
            "dueños_directos_guardados": 0,
            "inmobiliarias_descartadas": 0
        }

    def verificar_servicios(self) -> bool:
        """Verifica la conectividad de los servicios requeridos."""
        print("[ORQUESTADOR] 🔍 Verificando estado de servicios...")
        supabase_ok = db_client.validar_conexion_supabase()
        telegram_ok = validar_conexion_telegram()
        
        print(f"[ORQUESTADOR] Supabase DB: {'✅ CONECTADO' if supabase_ok else '❌ DESCONECTADO'}")
        print(f"[ORQUESTADOR] Telegram Bot: {'✅ ACTIVO' if telegram_ok else '⚠️ DESCONECTADO/SIN CONFIGURAR'}")
        
        return supabase_ok

    def ejecutar_ciclo(self) -> dict:
        """Ejecuta la secuencia completa del orquestador central."""
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        print("=========================================================")
        print("🤖 AGENTE CENTRAL (ORQUESTADOR) - INICIANDO FASE 1 🤖")
        print("=========================================================")
        print(f"[ORQUESTADOR] Plataforma objetivo: {self.plataforma.upper()}")
        print(f"[ORQUESTADOR] Índice inicial: {self.indice_inicial}")
        print(f"[ORQUESTADOR] Páginas a escanear: {self.paginas_escanear}\n")

        # 1. Verificación de entorno y servicios
        if not self.verificar_servicios():
            print("[ORQUESTADOR] ⚠️ Supabase no está disponible en este momento. Se ejecutará el rastreo y clasificación en modo evaluación local.")

        # 2. Delegar rastreo al Agente Buscador
        print(f"\n[ORQUESTADOR -> AGENTE BUSCADOR] Solicitando búsqueda limpia en Mar del Plata...")
        candidatos = self.buscador.buscar_candidatos(
            plataforma=self.plataforma,
            indice_inicial=self.indice_inicial,
            paginas_a_escanear=self.paginas_escanear
        )
        self.metricas["candidatos_encontrados"] = len(candidatos)
        print(f"[ORQUESTADOR] Candidatos recuperados por Agente Buscador: {len(candidatos)}")

        if not candidatos:
            print("[ORQUESTADOR] No se hallaron publicaciones adicionales en esta página.")
            nuevo_indice = self.indice_inicial + (self.paginas_escanear * 10)
            db_client.actualizar_indice(self.plataforma, nuevo_indice)
            return self.metricas

        # 3. Filtrado Anti-Duplicados y Evaluación Heurística Local
        for idx, candidato in enumerate(candidatos):
            link = candidato.get('link', '')
            titulo = candidato.get('titulo', '')
            texto = candidato.get('texto', '')

            print(f"\n[ORQUESTADOR] [Candidato {idx + 1}/{len(candidatos)}] Evaluando URL: {link}")

            # Control Anti-Duplicados Estricto por URL / Hash
            if db_client.existe_captacion_por_link(link):
                print(f"[ORQUESTADOR ANTI-DUPLICADOS] 🛑 Omitiendo link duplicado en Supabase: {link}")
                self.metricas["duplicados_omitidos"] += 1
                continue

            # Clasificación Heurística Local del Agente Buscador
            evaluacion = self.buscador.clasificar_publicacion(titulo, texto, link)
            cumple = evaluacion.get("Cumple", False)
            es_dueno = evaluacion.get("Dueño/Contacto") == "Dueño Directo"
            telefono = evaluacion.get("Teléfono", "A revisar")
            analisis = evaluacion.get("Análisis IA", "Captación Heurística Local")

            if cumple and es_dueno:
                # Guardar captación válida en Supabase
                exito, msg = db_client.guardar_captacion(
                    titulo=titulo,
                    link=link,
                    telefono=telefono,
                    plataforma=self.plataforma,
                    analisis_ia=analisis
                )
                if exito:
                    self.metricas["dueños_directos_guardados"] += 1
                    # Enviar notificación en vivo por Telegram
                    evaluacion["Link"] = link
                    evaluacion["Plataforma"] = self.plataforma
                    enviar_a_telegram(evaluacion)
                else:
                    self.metricas["duplicados_omitidos"] += 1
            else:
                # Guardar descarte para registrar el hash en Supabase y evitar re-procesamiento
                db_client.guardar_captacion(
                    titulo=titulo,
                    link=link,
                    telefono="Descartado",
                    plataforma=self.plataforma,
                    analisis_ia=f"Descartado localmente (Inmobiliaria / Criterios no cumplidos)."
                )
                self.metricas["inmobiliarias_descartadas"] += 1
                print(f"[ORQUESTADOR] Publicación descartada por filtro de inmobiliarias o criterios.")

            time.sleep(1.0)

        # 4. Actualización del Puntero de Paginación en Supabase
        nuevo_indice = self.indice_inicial + (self.paginas_escanear * 10)
        db_client.actualizar_indice(self.plataforma, nuevo_indice)
        print(f"\n[ORQUESTADOR] Puntero de paginación guardado en Supabase: {nuevo_indice}")

        # 5. Resumen final de ejecución
        self.reportar_resumen(nuevo_indice)
        return self.metricas

    def reportar_resumen(self, nuevo_indice: int):
        print("\n=========================================================")
        print("📊 RESUMEN DE OPERACIÓN - AGENTE CENTRAL ORQUESTADOR")
        print("=========================================================")
        print(f"🔹 Candidatos Encontrados        : {self.metricas['candidatos_encontrados']}")
        print(f"🛑 Duplicados Omitidos (Supabase): {self.metricas['duplicados_omitidos']}")
        print(f"✅ Dueños Directos Registrados   : {self.metricas['dueños_directos_guardados']}")
        print(f"🚫 Inmobiliarias / Descartados  : {self.metricas['inmobiliarias_descartadas']}")
        print(f"🔑 Paginación Actualizada a     : {nuevo_indice}")
        print("=========================================================\n")


def main():
    plataforma = sys.argv[1] if len(sys.argv) > 1 else "instagram"
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
