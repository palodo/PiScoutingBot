#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de tarea programada para ejecutar final_pdf.py cada lunes a las 3 AM
y reiniciar el bot después.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Añadir el directorio raíz al path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Configurar logging
log_dir = BASE_DIR / "logs"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f"weekly_pdf_generation_{datetime.now().strftime('%Y%m')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """
    Función principal para generar PDFs semanalmente
    """
    try:
        logger.info("=" * 70)
        logger.info("INICIANDO GENERACIÓN SEMANAL DE PDFs")
        logger.info(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)
        
        # Importar la función de generación de PDF
        from pdf_generator.final_pdf import generar_pdf_final
        
        # Cargar datos históricos para obtener jugadores
        data_path = BASE_DIR / "data" / "datos_historicos.json"
        
        if not data_path.exists():
            logger.error(f"Archivo de datos no encontrado: {data_path}")
            return 1
        
        with open(data_path, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        # Temporada actual
        temporada = "2025"
        
        if temporada not in datos:
            logger.error(f"Temporada {temporada} no encontrada en datos")
            return 1
        
        jugadores = datos[temporada]
        total_jugadores = len(jugadores)
        
        logger.info(f"Total de jugadores encontrados: {total_jugadores}")
        logger.info("Iniciando generación de PDFs...")
        
        # Contadores
        exitosos = 0
        fallidos = 0
        
        # Generar PDF para cada jugador
        for idx, jugador_id in enumerate(jugadores.keys(), 1):
            try:
                logger.info(f"[{idx}/{total_jugadores}] Generando PDF para jugador: {jugador_id}")
                
                # Generar el PDF
                resultado = generar_pdf_final(
                    jugador_id=jugador_id,
                    temporada=temporada,
                    datos=datos
                )
                
                if resultado:
                    exitosos += 1
                    logger.info(f"✓ PDF generado exitosamente: {jugador_id}")
                else:
                    fallidos += 1
                    logger.warning(f"✗ Falló la generación del PDF: {jugador_id}")
                    
            except Exception as e:
                fallidos += 1
                logger.error(f"✗ Error al generar PDF para {jugador_id}: {str(e)}")
        
        # Resumen final
        logger.info("=" * 70)
        logger.info("RESUMEN DE GENERACIÓN DE PDFs")
        logger.info(f"Total de jugadores: {total_jugadores}")
        logger.info(f"PDFs generados exitosamente: {exitosos}")
        logger.info(f"PDFs fallidos: {fallidos}")
        logger.info(f"Tasa de éxito: {(exitosos/total_jugadores*100):.2f}%")
        logger.info("=" * 70)
        
        return 0 if fallidos == 0 else 1
        
    except Exception as e:
        logger.error(f"Error crítico en la generación de PDFs: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    logger.info(f"Script finalizado con código: {exit_code}")
    sys.exit(exit_code)
