# -*- coding: utf-8 -*-
"""
Generador final de PDF que combina el informe estadístico y los shot charts
Combina la funcionalidad de generar.py y shotchart_pdf.py en un único PDF
"""

import os
import io
import re
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from typing import List, Dict, Optional, Any
from pathlib import Path

# OpenAI and environment variables
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Importaciones de ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus.flowables import Image as ReportLabImage

# Importar todas las funciones necesarias de generar.py
from .generar import (
    normalizar_dataframe,
    cargar_logos_equipos,
    calcular_estadisticas_avanzadas,
    normalizar_estadisticas_jugadores,
    crear_rankings_jugadores,
    descargar_fotos_jugadores,
    calcular_usg_correcto
)

# Importar funciones necesarias del módulo de scraping para shot charts
from scrapping_folder.shortchart_class import (
    select_team_from_datos,
    coerce_str,
    parse_qs_param,
    ensure_dir,
    load_results_csv,
    filter_matches_by_team_url,
    ShotChartScraper,
    build_player_maps_for_team,
    accumulate_player_shots_from_match,
    union_shotlists,
    plot_player_shots_to_buffer,
    get_player_photo_buffer,
    DEFAULT_DATOS_JSON,
    DEFAULT_RESULTS_CSV,
    DEFAULT_COURT_IMAGE,
    DEFAULT_OUTPUT_DIR
)

# =============== SISTEMA DE NORMALIZACIÓN DE NOMBRES DE EQUIPOS ===============

def cargar_mapper_equipos():
    """
    Carga el mapper de nombres de equipos desde el archivo JSON
    
    Returns:
        dict: Diccionario con mapeo nombre_original -> nombre_normalizado
    """
    import json
    from pathlib import Path
    
    # Ruta al archivo mapper
    mapper_path = Path(__file__).parent.parent / "data" / "equipos_mapper.json"
    
    try:
        with open(mapper_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Crear diccionario de mapeo
        mapper = {}
        for equipo in data.get("equipos", []):
            nombre_original = equipo.get("nombre_original", "")
            nombre_normalizado = equipo.get("nombre_normalizado", "")
            if nombre_original and nombre_normalizado:
                mapper[nombre_original] = nombre_normalizado
        
        print(f"✅ Mapper de equipos cargado: {len(mapper)} mapeos")
        return mapper
    
    except Exception as e:
        print(f"⚠️ Error cargando mapper de equipos: {e}")
        return {}

def normalizar_nombre_equipo(nombre_original: str) -> str:
    """
    Normaliza el nombre de un equipo usando el mapper.
    Si no encuentra el mapeo, devuelve el nombre original.
    
    Args:
        nombre_original: Nombre original del equipo
        
    Returns:
        str: Nombre normalizado del equipo
    """
    # Cargar mapper (se podría optimizar cacheando esto)
    mapper = cargar_mapper_equipos()
    
    # Aplicar normalización si existe el mapeo
    return mapper.get(nombre_original, nombre_original)

def aplicar_normalizacion_dataframe(df, columna_equipo='Equipo'):
    """
    Aplica normalización de nombres a un DataFrame para visualización
    
    Args:
        df: DataFrame de pandas
        columna_equipo: Nombre de la columna que contiene nombres de equipos
        
    Returns:
        DataFrame: Copia del DataFrame con nombres normalizados
    """
    import pandas as pd
    
    df_normalizado = df.copy()
    
    # Aplicar normalización solo si la columna existe
    if columna_equipo in df_normalizado.columns:
        df_normalizado[columna_equipo] = df_normalizado[columna_equipo].apply(normalizar_nombre_equipo)
    
    return df_normalizado


def eliminar_paginas_en_blanco_pdf(input_pdf_path: str, output_pdf_path: str = None) -> str:
    """
    Post-procesa un PDF para eliminar páginas en blanco o casi vacías.
    
    Args:
        input_pdf_path: Ruta del PDF original
        output_pdf_path: Ruta del PDF limpio (opcional, si no se especifica sobrescribe el original)
    
    Returns:
        str: Ruta del PDF limpio
    """
    try:
        import PyPDF2
        from io import BytesIO
        
        print("📄 Post-procesando PDF para eliminar páginas en blanco...")
        
        if output_pdf_path is None:
            output_pdf_path = input_pdf_path
        
        # Leer el PDF original
        with open(input_pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_writer = PyPDF2.PdfWriter()
            
            paginas_eliminadas = []
            total_paginas = len(pdf_reader.pages)
            
            for i, page in enumerate(pdf_reader.pages):
                # Extraer texto de la página
                try:
                    text = page.extract_text().strip()
                    
                    # Criterios para considerar una página "vacía":
                    # 1. Sin texto (completamente vacía)
                    # 2. Solo espacios en blanco
                    # 3. Solo caracteres de control o saltos de línea
                    text_limpio = re.sub(r'\s+', '', text)  # Remover todos los espacios
                    
                    es_pagina_vacia = (
                        len(text_limpio) == 0 or  # Sin contenido real
                        len(text_limpio) < 5 or   # Muy poco contenido (menos de 5 caracteres)
                        text_limpio.replace('\n', '').replace('\r', '').replace('\f', '') == ''  # Solo saltos de línea
                    )
                    
                    if es_pagina_vacia:
                        paginas_eliminadas.append(i + 1)
                        print(f"   🗑️ Eliminando página {i + 1} (vacía): '{text[:50]}...'")
                    else:
                        pdf_writer.add_page(page)
                        
                except Exception as e:
                    # Si hay error extrayendo texto, mantener la página por seguridad
                    print(f"   ⚠️ No se pudo analizar página {i + 1}, manteniéndola: {e}")
                    pdf_writer.add_page(page)
            
            # Escribir el PDF limpio
            with open(output_pdf_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            paginas_finales = len(pdf_writer.pages)
            
            if paginas_eliminadas:
                print(f"✅ PDF limpiado: {total_paginas} → {paginas_finales} páginas")
                print(f"   Páginas eliminadas: {paginas_eliminadas}")
            else:
                print(f"✅ PDF verificado: No se encontraron páginas en blanco ({total_paginas} páginas)")
                
            return output_pdf_path
            
    except ImportError:
        print("⚠️ PyPDF2 no está instalado. Instalando...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyPDF2'])
        # Reintentar después de la instalación
        return eliminar_paginas_en_blanco_pdf(input_pdf_path, output_pdf_path)
        
    except Exception as e:
        print(f"❌ Error en post-procesado de PDF: {e}")
        print("   Devolviendo PDF original sin cambios")
        return input_pdf_path


def obtener_ultimos_partidos_equipo(nombre_equipo: str, liga: str = None, csv_path: str = None, num_partidos: int = 3) -> List[Dict[str, str]]:
    """
    Obtiene los últimos partidos jugados de un equipo específico filtrado por liga.
    
    Args:
        nombre_equipo: Nombre exacto del equipo
        liga: Liga del equipo (ej: "1ª FEB", "2ª FEB", "3ª FEB")
        csv_path: Ruta al archivo CSV (opcional, usa ruta por defecto si no se especifica)
        num_partidos: Número de partidos a obtener (por defecto 3)
        
    Returns:
        Lista de diccionarios con información de los partidos:
        [
            {
                'fecha': 'dd/mm/yyyy',
                'resultado': 'XX-YY',
                'estado': 'W' o 'L',
                'oponente': 'Nombre del equipo rival',
                'enlace': 'URL del partido'
            }
        ]
    """
    from datetime import datetime
    import re
    
    # Usar ruta por defecto si no se especifica
    if csv_path is None:
        csv_path = "data/datos_completos.csv"
    
    # Mapper de liga a número en source_url
    liga_mapper = {
        "1ª FEB": "1",
        "2ª FEB": "2", 
        "3ª FEB": "3"
    }
    
    try:
        # Cargar el CSV
        df = pd.read_csv(csv_path)
        
        # Filtrar partidos donde el equipo participa (como local o visitante)
        partidos_equipo = df[
            ((df['local'] == nombre_equipo) | (df['visitante'] == nombre_equipo)) &
            (df['resultado'].notna()) &  # Solo partidos con resultado
            (df['resultado'] != '') &    # Resultado no vacío
            (df['resultado'].str.strip() != '')  # Resultado no solo espacios
        ].copy()
        
        if partidos_equipo.empty:
            print(f"⚠️ No se encontraron partidos jugados para el equipo: {nombre_equipo}")
            return []
        
        # Filtrar por liga si se especifica
        if liga and liga in liga_mapper:
            liga_numero = liga_mapper[liga]
            print(f"🔍 Filtrando por liga: {liga} (número {liga_numero})")
            
            # El CSV actual tiene columna 'liga' con formato "Liga X"
            # Filtrar por el formato correcto de liga
            liga_formato = f"Liga {liga_numero}"
            partidos_liga = partidos_equipo[partidos_equipo['liga'] == liga_formato]
            
            if partidos_liga.empty:
                print(f"⚠️ No se encontraron partidos para {nombre_equipo} en {liga}")
                return []
            
            print(f"✅ Encontrados {len(partidos_liga)} partidos de {nombre_equipo} en {liga}")
            partidos_equipo = partidos_liga
        
        # Convertir fechas al formato datetime para ordenar
        partidos_equipo['fecha_dt'] = pd.to_datetime(partidos_equipo['fecha'], format='%d/%m/%Y', errors='coerce')
        
        # Filtrar solo fechas válidas y anteriores a hoy
        hoy = datetime.now()
        partidos_equipo = partidos_equipo[
            (partidos_equipo['fecha_dt'].notna()) &
            (partidos_equipo['fecha_dt'] <= hoy)
        ]
        
        # Ordenar por fecha descendente (más reciente primero)
        partidos_equipo = partidos_equipo.sort_values('fecha_dt', ascending=False)
        
        # Tomar solo los últimos N partidos
        ultimos_partidos = partidos_equipo.head(num_partidos)
        
        resultados = []
        
        for _, partido in ultimos_partidos.iterrows():
            # Determinar si es local o visitante
            es_local = partido['local'] == nombre_equipo
            oponente = partido['visitante'] if es_local else partido['local']
            
            # Extraer resultado y determinar W/L
            resultado = partido['resultado'].strip()
            try:
                # Formato esperado: "XX-YY"
                puntos_local, puntos_visitante = map(int, resultado.split('-'))
                
                if es_local:
                    estado = 'W' if puntos_local > puntos_visitante else 'L'
                else:
                    estado = 'W' if puntos_visitante > puntos_local else 'L'
            except (ValueError, AttributeError):
                estado = '?'  # No se pudo determinar
            
            # Crear entrada del resultado
            resultado_partido = {
                'fecha': partido['fecha'],
                'resultado': resultado,
                'estado': estado,
                'oponente': oponente,
                'enlace': partido.get('partido_url', '')
            }
            
            resultados.append(resultado_partido)
        
        print(f"✅ Se encontraron {len(resultados)} partidos recientes para {nombre_equipo} en {liga if liga else 'todas las ligas'}")
        return resultados
        
    except Exception as e:
        print(f"❌ Error obteniendo partidos del equipo {nombre_equipo}: {e}")
        return []


def crear_pagina_ultimos_partidos(nombre_equipo: str, liga: str = None, csv_path: str = None) -> List:
    """
    Crea una página con los últimos 3 partidos del equipo rival filtrados por liga.
    
    Args:
        nombre_equipo: Nombre del equipo
        liga: Liga del equipo (ej: "1ª FEB", "2ª FEB", "3ª FEB")
        csv_path: Ruta al archivo CSV (opcional)
        
    Returns:
        Lista de elementos para añadir al story del PDF
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    
    # Obtener los últimos partidos filtrados por liga
    partidos = obtener_ultimos_partidos_equipo(nombre_equipo, liga, csv_path, num_partidos=5)
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para el título de la página
    titulo_partidos_style = ParagraphStyle(
        'TituloPartidos',
        parent=styles['Heading1'],
        fontSize=32,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
        spaceAfter=30,
        fontName='Helvetica-Bold',
        leading=36
    )
    
    # Estilo para subtítulo
    subtitulo_partidos_style = ParagraphStyle(
        'SubtituloPartidos',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=25,
        fontName='Helvetica-Bold',
    )
    
    # Estilo para fecha
    fecha_style = ParagraphStyle(
        'FechaPartido',
        parent=styles['Normal'],
        fontSize=16,
        textColor=colors.HexColor('#4a5568'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    # Estilo para resultado
    resultado_style = ParagraphStyle(
        'ResultadoPartido',
        parent=styles['Normal'],
        fontSize=24,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=3
    )
    
    # Estilo para estado (W/L)
    estado_win_style = ParagraphStyle(
        'EstadoWin',
        parent=styles['Normal'],
        fontSize=20,
        textColor=colors.HexColor('#38a169'),  # Verde para W
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    estado_loss_style = ParagraphStyle(
        'EstadoLoss',
        parent=styles['Normal'],
        fontSize=20,
        textColor=colors.HexColor('#e53e3e'),  # Rojo para L
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    # Estilo para oponente
    oponente_style = ParagraphStyle(
        'OponentePartido',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=8
    )
    
    # Estilo para enlace
    enlace_style = ParagraphStyle(
        'EnlacePartido',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#3182ce'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        leftIndent=10,
        rightIndent=10
    )
    
    # Elementos de la página
    elementos = []
    
    # Spacer inicial
    elementos.append(Spacer(1, 0.5*inch))
    
    # Título principal
    titulo = Paragraph(f"ÚLTIMOS PARTIDOS", titulo_partidos_style)
    elementos.append(titulo)
    
    if not partidos:
        # Mensaje si no hay partidos
        sin_datos_style = ParagraphStyle(
            'SinDatos',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#e53e3e'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        mensaje = Paragraph("⚠️ No se encontraron partidos recientes con resultado", sin_datos_style)
        elementos.append(Spacer(1, 1*inch))
        elementos.append(mensaje)
        return elementos
    
    # Crear tabla con los partidos
    tabla_data = []
    
    # Encabezados
    headers = ["Fecha", "Resultado", "Estado", "Oponente", "Link"]
    tabla_data.append(headers)
    
    # Datos de partidos
    for partido in partidos:
        # Crear Paragraph con enlace para la columna de enlace
        if partido['enlace']:
            # Crear un Paragraph con enlace clickeable usando ReportLab
            enlace_paragraph = Paragraph(
                f'<a href="{partido["enlace"]}" color="#3182ce"><u>View</u></a>',
                enlace_style
            )
        else:
            enlace_paragraph = Paragraph("N/A", enlace_style)
        
        fila = [
            partido['fecha'],
            partido['resultado'],
            partido['estado'],
            partido['oponente'],
            enlace_paragraph  # Usar Paragraph en lugar de string
        ]
        tabla_data.append(fila)
    
    # Si no hay 5 partidos, añadir filas para partidos no jugados
    partidos_faltantes = 5 - len(partidos)
    if partidos_faltantes > 0:
        for i in range(partidos_faltantes):
            fila_vacia = [
                "Próximamente",
                "-",
                "-",
                "Pendiente",
                Paragraph("N/A", enlace_style)
            ]
            tabla_data.append(fila_vacia)
    
    # Crear tabla
    tabla = Table(tabla_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 4.5*inch, 1*inch])
    
    # Estilos de la tabla - TODO CENTRADO
    tabla_estilos = [
        # Estilo general - TODO CENTRADO
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # TODO centrado
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # TODO centrado verticalmente
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        
        # Encabezados
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        
        # Celdas de datos
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        
        # Columna de estado (W/L)
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, 1), (2, -1), 16),
        
        # Padding - reducido para menor altura de celdas
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]
    
    # Añadir colores específicos para W/L solo para partidos reales
    for i, partido in enumerate(partidos, 1):
        if partido['estado'] == 'W':
            tabla_estilos.append(('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#38a169')))
        elif partido['estado'] == 'L':
            tabla_estilos.append(('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#e53e3e')))
    
    # Estilo especial para filas de partidos pendientes (más tenue)
    if partidos_faltantes > 0:
        for i in range(len(partidos) + 1, len(partidos) + partidos_faltantes + 1):
            tabla_estilos.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#9ca3af')))  # Gris más tenue
            tabla_estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f9fafb')))  # Fondo gris muy claro
    
    tabla.setStyle(TableStyle(tabla_estilos))
    
    # Añadir espaciador y tabla
    elementos.append(Spacer(1, 0.5*inch))
    elementos.append(tabla)
    
    # Spacer final
    elementos.append(Spacer(1, 0.5*inch))
    
    # Nota informativa
    nota_style = ParagraphStyle(
        'NotaPartidos',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#718096'),
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique',
        leftIndent=50,
        rightIndent=50
    )
    
    nota = Paragraph(
        "💡 Esta información muestra los últimos 5 partidos jugados por el equipo rival, "
        "ordenados desde el más reciente al más antiguo. Estado: W = Victoria, L = Derrota.",
        nota_style
    )
    elementos.append(nota)
    
    return elementos


def obtener_numeros_jugadores_equipo(equipo_url: str, df_resultados: pd.DataFrame = None) -> Dict[str, Dict[str, str]]:
    """
    Obtiene los números de camiseta de los jugadores de un equipo usando los shot charts.
    
    Args:
        equipo_url: URL del equipo
        df_resultados: DataFrame con los resultados, si no se proporciona se carga por defecto
        
    Returns:
        Dict con dos mapeos: 
        {
            'por_id': {player_id -> numero_camiseta},
            'por_nombre': {nombre_jugador -> numero_camiseta}
        }
    """
    if df_resultados is None:
        try:
            df_resultados = load_results_csv(DEFAULT_RESULTS_CSV)
        except:
            return {'por_id': {}, 'por_nombre': {}}
    
    # Filtrar partidos del equipo
    subset = filter_matches_by_team_url(df_resultados, equipo_url)
    if subset.empty:
        return {'por_id': {}, 'por_nombre': {}}
    
    # Tomar solo unos pocos partidos para obtener los números (no necesitamos todos)
    subset = subset.head(3)  # Solo los primeros 3 partidos
    
    numero_por_player: Dict[str, str] = {}
    numero_por_nombre: Dict[str, str] = {}
    scraper = ShotChartScraper()
    
    for _, row in subset.iterrows():
        pid = str(row['partido_id'])
        team_idx = int(row['team_idx'])
        
        try:
            full_data = scraper.get_shot_chart_data(pid)
            shots_data = scraper.extract_shots_data(full_data)
            if not shots_data:
                continue
                
            # Obtener mapa de jugadores con números de camiseta
            dorsal_map = build_player_maps_for_team(shots_data, team_idx)
            
            # Guardar números de camiseta por ID y por nombre
            for dorsal, info in dorsal_map.items():
                player_id = info['player_id']
                player_name = info.get('player_name', '').strip()
                
                if player_id and dorsal:
                    numero_por_player[player_id] = dorsal
                
                if player_name and dorsal:
                    # Limpiar el nombre para hacer mejor match
                    nombre_limpio = player_name.strip()
                    # Remover posibles sufijos como "(C)" o números al final
                    import re
                    nombre_limpio = re.sub(r'\s*\([^)]*\)$', '', nombre_limpio)
                    nombre_limpio = re.sub(r'\s*\d+$', '', nombre_limpio)
                    numero_por_nombre[nombre_limpio] = dorsal
            
            # Si ya tenemos suficientes números, parar
            if len(numero_por_player) > 10:  # Suficientes para un equipo
                break
                
        except Exception as e:
            continue  # Ignorar errores y seguir con el siguiente partido
    
    print(f"\n� DEBUG SCRAPING - Números extraídos de la web:")
    print(f"   🆔 Por ID ({len(numero_por_player)} jugadores):")
    for player_id, dorsal in numero_por_player.items():
        print(f"      ID: '{player_id}' → #{dorsal}")
    
    print(f"   � Por nombre ({len(numero_por_nombre)} jugadores):")
    for nombre, dorsal in numero_por_nombre.items():
        print(f"      Nombre: '{nombre}' → #{dorsal}")
    
    return {
        'por_id': numero_por_player,
        'por_nombre': numero_por_nombre
    }


def buscar_numero_jugador(jugador_data, numeros_jugadores):
    """
    Busca el número de camiseta de un jugador usando tanto ID como nombre.
    
    Args:
        jugador_data: Datos del jugador (Serie de pandas o dict con campos 'ID', 'Jugador')
        numeros_jugadores: Dict con mapeos 'por_id' y 'por_nombre'
    
    Returns:
        str: Número de camiseta o None si no se encuentra
    """
    # Verificar que tenemos datos válidos
    if not numeros_jugadores:
        return None
    
    # Verificar si jugador_data está vacío (funciona tanto para Series como dict)
    try:
        if jugador_data is None or (hasattr(jugador_data, 'empty') and jugador_data.empty):
            return None
    except:
        if not jugador_data:  # Para casos donde no es una Serie
            return None

    # Método 1: Buscar por ID del enlace
    player_id = str(jugador_data.get('ID', ''))
    if player_id and player_id in numeros_jugadores.get('por_id', {}):
        numero = numeros_jugadores['por_id'][player_id]
        return numero
    
    # Método 2: Buscar por nombre
    nombre = jugador_data.get('Jugador', '').strip()
    # Método 2: Buscar por nombre
    if nombre:
        # Limpiar el nombre para hacer mejor match
        import re
        nombre_limpio = nombre.strip()
        # Remover posibles comas y sufijos
        if ',' in nombre_limpio:
            nombre_limpio = nombre_limpio.split(',')[0].strip()
        
        # Buscar match exacto primero
        if nombre_limpio in numeros_jugadores.get('por_nombre', {}):
            numero = numeros_jugadores['por_nombre'][nombre_limpio]
            return numero
        
        # Buscar match parcial (por si hay diferencias menores)
        for nombre_web, numero in numeros_jugadores.get('por_nombre', {}).items():
            if nombre_limpio.lower() in nombre_web.lower() or nombre_web.lower() in nombre_limpio.lower():
                return numero
    
    return None


def pil_buffer_to_reportlab_image(img_buffer: io.BytesIO, width, height):
    """Convierte buffer PIL a imagen ReportLab"""
    img_buffer.seek(0)
    return ReportLabImage(img_buffer, width=width, height=height)


def create_player_cell_from_buffers(player_name: str, player_number: str, photo_buffer: io.BytesIO, chart_buffer: io.BytesIO):
    """Crea celda de jugador usando buffers en memoria"""
    # Convertir buffers a imágenes ReportLab (foto más pequeña, pista más grande)
    photo_img = pil_buffer_to_reportlab_image(photo_buffer, width=17*mm, height=22*mm)
    chart_img = pil_buffer_to_reportlab_image(chart_buffer, width=40*mm, height=35*mm)
    
    # Crear texto con número y nombre
    if player_number and player_number.strip():
        display_text = f"#{player_number} - {player_name}"
    else:
        display_text = player_name
    
    # Crear tabla interna (columna de foto más pequeña, columna de pista más grande)
    player_content = [
        [display_text, ""],  # Nombre del jugador (y número si disponible)
        [photo_img, chart_img]  # Foto | Gráfica
    ]
    
    player_table = Table(player_content, colWidths=[20*mm, 40*mm], rowHeights=[8*mm, 37*mm])
    player_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (1, 0), 8),  # Tamaño un poco más pequeño para que quepa
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),  # Texto blanco para el nombre
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#4a5568')),  # Fondo gris profesional para consistencia
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    return player_table


def formatear_numero_sin_salto(valor):
    """
    Formatea un número evitando saltos de línea en los decimales
    usando un formato más compacto
    """
    if pd.isna(valor):
        return "N/A"
    
    try:
        valor_num = float(valor)
        if valor_num == int(valor_num):
            return f"{int(valor_num)}"
        else:
            # Formato con un solo decimal, usando texto más compacto
            # Redondeamos a 1 decimal para evitar números muy largos
            return f"{valor_num:.1f}"
    except:
        return str(valor)


def formatear_porcentaje_sin_salto(valor):
    """
    Formatea un porcentaje evitando saltos de línea.
    Convierte 100.0% a 100% para evitar saltos de línea.
    """
    if pd.isna(valor):
        return "0.0%"
    
    try:
        if valor == 100.0:
            return "100%"
        else:
            return f"{valor:.1f}%"
    except:
        return f"{valor}%"


def crear_rankings_equipos(df_equipos):
    """
    Crea rankings de estadísticas de equipos.
    
    Args:
        df_equipos: DataFrame con estadísticas de todos los equipos del grupo
        
    Returns:
        dict: Diccionario con rankings de equipos por categoría
    """
    rankings = {}
    
    # Solo procesar si hay más de un equipo
    if len(df_equipos) <= 1:
        return rankings
        
    # Anotación (Puntos por partido)
    rankings['Puntos_Equipo'] = df_equipos.sort_values('PTS/PJ', ascending=False).reset_index(drop=True)
    
    # Triples por partido con porcentaje
    rankings['Triples_Equipo'] = df_equipos.sort_values('FG3A', ascending=False).reset_index(drop=True)
    
    # Rebotes por partido
    rankings['Rebotes_Equipo'] = df_equipos.sort_values('REB/PJ', ascending=False).reset_index(drop=True)
    
    # Asistencias por partido
    rankings['Asistencias_Equipo'] = df_equipos.sort_values('AST/PJ', ascending=False).reset_index(drop=True)
    
    # Pérdidas por partido (ascendente porque menos es mejor)
    rankings['Perdidas_Equipo'] = df_equipos.sort_values('TO/PJ', ascending=True).reset_index(drop=True)
    
    # Porcentaje de victorias
    rankings['Victorias_Equipo'] = df_equipos.sort_values('Win%', ascending=False).reset_index(drop=True)
    
    # Porcentaje de tiros de campo
    rankings['FG_Percentage_Equipo'] = df_equipos.sort_values('FG%', ascending=False).reset_index(drop=True)
    
    # Porcentaje de tiros de 2
    rankings['FG2_Percentage_Equipo'] = df_equipos.sort_values('FG2%', ascending=False).reset_index(drop=True)
    
    # Porcentaje de triples
    rankings['FG3_Percentage_Equipo'] = df_equipos.sort_values('FG3%', ascending=False).reset_index(drop=True)
    
    # Porcentaje de tiros libres
    rankings['FT_Percentage_Equipo'] = df_equipos.sort_values('FT%', ascending=False).reset_index(drop=True)
    
    # Rebotes ofensivos por partido
    rankings['Rebotes_Ofensivos_Equipo'] = df_equipos.sort_values('OREB/PJ', ascending=False).reset_index(drop=True)
    
    # Robos por partido
    rankings['Robos_Equipo'] = df_equipos.sort_values('STL/PJ', ascending=False).reset_index(drop=True)
    
    # Defensive Rating (menor es mejor)
    if 'DefRtg' in df_equipos.columns:
        rankings['Defensive_Rating_Equipo'] = df_equipos.sort_values('DefRtg', ascending=True).reset_index(drop=True)
    
    # Offensive Rating (mayor es mejor)
    if 'OffRtg' in df_equipos.columns:
        rankings['Offensive_Rating_Equipo'] = df_equipos.sort_values('OffRtg', ascending=False).reset_index(drop=True)
        
    return rankings


# Funciones de formato para porcentajes
def format_percentage_fg(row):
    """Formatea el porcentaje de tiros de campo"""
    return f"{row['FG%']:.1f}%"

def format_percentage_fg3(row):
    """Formatea el porcentaje de triples"""
    return f"{row['FG3%']:.1f}%"

def format_percentage_ft(row):
    """Formatea el porcentaje de tiros libres"""
    return f"{row['FT%']:.1f}%"

def crear_pagina_rankings_equipos(story, rankings_equipos, df_equipos, equipo_seleccionado, styles):
    """
    Crea una página de rankings de equipos en formato similar a la página de comparativa
    con tablas separadas y completas para cada estadística principal
    """
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus.doctemplate import NextPageTemplate
    from pathlib import Path
    import os
    import pandas as pd  # Aseguramos que pandas está importado

    # Solo crear la página si hay rankings de equipos y más de un equipo
    if not rankings_equipos or len(df_equipos) <= 1:
        return
    
    # Cambiar a plantilla landscape y añadir salto de página
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Título principal
    titulo_style = ParagraphStyle(
        'TituloEquipos',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("RANKINGS DE EQUIPOS", titulo_style)
    story.append(titulo)
    
    # Nota explicativa en lugar de línea decorativa
    nota_style = ParagraphStyle(
        'NotaRankings',
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=15,
    )
    nota = Paragraph("* Los datos mostrados son promedios por partido de la temporada", nota_style)
    story.append(nota)

    # Función para crear ranking con tabla premium - LIMITAR A 12 EQUIPOS MÁXIMO
    def crear_ranking_premium(titulo, df_sorted, columna, color_header):
        # LIMITAR A 12 EQUIPOS para que quepa en la página landscape
        MAX_EQUIPOS = 12
        total_equipos = len(df_sorted)
        if total_equipos > MAX_EQUIPOS:
            df_sorted = df_sorted.head(MAX_EQUIPOS)
            print(f"⚠️  Tabla '{titulo}' (primera página) limitada a {MAX_EQUIPOS} equipos (había {total_equipos} totales)")
        
        # Función para acortar nombres largos (versión simplificada)
        def acortar_nombre(nombre, max_chars=22):
            if len(nombre) <= max_chars:
                return nombre
            palabras = nombre.split()
            if len(palabras) > 1:
                iniciales = [p[0] + '.' for p in palabras[:-1]]
                resultado = ' '.join(iniciales + [palabras[-1]])
                if len(resultado) <= max_chars:
                    return resultado
                return resultado[:max_chars-2] + '..'
            return nombre[:max_chars-2] + '..'
        
        # Crear la tabla con los datos - VERSION COMPACTA PRIMERA
        datos_ranking = []
        
        # Header con color
        header_style = ParagraphStyle(
            'HeaderSimpleCompacta',
            fontSize=11,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        
        datos_ranking.append([Paragraph(titulo, header_style), ""])
        
        # Añadir filas de equipos
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            equipo_nombre = row['Equipo']
            equipo_nombre_normalizado = normalizar_nombre_equipo(equipo_nombre)  # ✅ APLICAR NORMALIZACIÓN
            valor = row[columna]
            posicion = i + 1  # Posición en el ranking (1º, 2º, 3º, etc.)
            
            # Crear nombre con ranking en negrita
            ranking_bold = f"<b>{posicion}º</b>"
            nombre_acortado = acortar_nombre(equipo_nombre_normalizado, 22)  # ✅ USAR NOMBRE NORMALIZADO
            nombre_mostrar = f"{ranking_bold} {nombre_acortado}"
            es_nuestro = equipo_nombre == equipo_seleccionado  # ✅ COMPARAR CON NOMBRE ORIGINAL
            
            # Formatear número en negrita
            if columna in ['FG%', 'FG3%', 'FT%', 'Win%']:
                # Si es 100.0%, mostrar como 100% sin decimal
                if valor == 100.0:
                    valor_texto = f"<b>{int(valor)}%</b>"
                else:
                    valor_texto = f"<b>{valor:.1f}%</b>"
            elif 'FG3A' in columna and 'PJ' in row.index:  # Para triples, mostrar intentos y porcentaje
                intentos = valor / row['PJ'] if row['PJ'] > 0 else 0
                porcentaje = row['FG3%'] if 'FG3%' in row and pd.notna(row['FG3%']) else 0
                valor_texto = f"<b>{intentos:.1f} ({porcentaje:.1f}%)</b>"
            else:
                # Formato en negrita: sin decimales si es entero
                valor_formateado = f"{int(valor)}" if valor == int(valor) else f"{valor:.1f}"
                valor_texto = f"<b>{valor_formateado}</b>"
            
            # Estilos con ranking y valores en negrita
            if es_nuestro:
                color_texto = color_header
                nombre_style = ParagraphStyle('', fontSize=10, textColor=color_texto, 
                                            alignment=0, fontName='Helvetica-Bold', leading=11)  # Reducido de 13 a 11
                valor_style = ParagraphStyle('', fontSize=11, textColor=color_texto, 
                                        alignment=2, fontName='Helvetica', leading=11)  # Reducido de 13 a 11
            else:
                nombre_style = ParagraphStyle('', fontSize=9.5, textColor=colors.black, 
                                            alignment=0, fontName='Helvetica', leading=12)  # Permite HTML
                valor_style = ParagraphStyle('', fontSize=10.5, textColor=colors.black, 
                                        alignment=2, fontName='Helvetica', leading=12)  # Permite HTML para negrita
            
            datos_ranking.append([
                Paragraph(nombre_mostrar, nombre_style),
                Paragraph(valor_texto, valor_style)
            ])
        
        # Crear tabla con diseño mejorado - usando los mismos tamaños que en COMPARATIVA
        # 📏 PRIMERA PÁGINA RANKINGS: Altura automática con mejor espaciado interno
        tabla = Table(datos_ranking, colWidths=[1.6*inch, 0.7*inch], rowHeights=None, splitByRow=True)
        
        # Estilos con colores consistentes
        estilos = [
            # Header con color
            ('SPAN', (0, 0), (1, 0)),  # Unir celdas del header
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), color_header),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Contenido - usando los mismos paddings que COMPARATIVA
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, -1), 8),
            ('RIGHTPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 5),    # ✅ Aumentado de 3 a 5 para mejor espaciado
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5), # ✅ Aumentado de 3 a 5 para mejor espaciado
            
            # Bordes
            ('BOX', (0, 0), (-1, -1), 1, color_header),
            ('LINEBELOW', (0, 0), (-1, 0), 1, color_header),
        ]
        
        # Alternar colores de fondo para las filas y colores para equipo seleccionado
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            equipo_nombre = row['Equipo']
            valor = row[columna]
            
            # Verificar si es número de 3 cifras con decimal (como 104.4)
            es_numero_3_cifras_decimal = (isinstance(valor, (int, float)) and 
                                        valor >= 100 and valor < 1000 and 
                                        valor != int(valor))  # Tiene decimal
            
            if equipo_nombre == equipo_seleccionado:
                estilos_equipo = [
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor("#ffe6e6")),  # Fondo rojito claro para equipo seleccionado
                    ('LINEBELOW', (0, i), (-1, i), 0.5, color_header),
                ]
                
                # Solo aplicar RIGHTPADDING reducido si es número de 3 cifras con decimal
                if es_numero_3_cifras_decimal:
                    estilos_equipo.append(('RIGHTPADDING', (0, i), (0, i), 2))  # Reducir espacio solo para 3 cifras con decimal
                
                estilos.extend(estilos_equipo)
            else:
                # Filas zebra CONSISTENTE con rankings individuales: fila par -> gris claro, fila impar -> blanco
                if i % 2 == 0:  # Filas pares (2,4,6...) -> gris claro (consistente con rankings individuales)
                    estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8f9fa")))  # Mismo gris que rankings individuales
                # Las filas impares (1,3,5...) quedan blancas por defecto
                # Líneas horizontales entre filas
                estilos.append(('LINEBELOW', (0, i), (-1, i), 0.25, color_header))
        
        tabla.setStyle(TableStyle(estilos))
        
        # Contenedor con borde suave del color correspondiente - igual que en COMPARATIVA
        contenedor_data = [[tabla]]
        contenedor = Table(contenedor_data, colWidths=[2.3*inch])
        contenedor.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),  # Fondo removido para permitir patrón alternado
        ]))
        
        return contenedor

    # Seleccionar solo 4 rankings principales para mantener claridad
    rankings_premium = []
    
    # 1. Puntos por partido
    if 'Puntos_Equipo' in rankings_equipos:
        ranking_puntos = crear_ranking_premium(
            "🏀 ANOTACIÓN", 
            rankings_equipos['Puntos_Equipo'], 
            'PTS/PJ', 
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_puntos)
    
    # 2. Rebotes por partido
    if 'Rebotes_Equipo' in rankings_equipos:
        ranking_rebotes = crear_ranking_premium(
            "💪 REBOTES",
            rankings_equipos['Rebotes_Equipo'],
            'REB/PJ',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_rebotes)
    
    # 3. Asistencias por partido
    if 'Asistencias_Equipo' in rankings_equipos:
        ranking_asistencias = crear_ranking_premium(
            "🤝 ASISTENCIAS",
            rankings_equipos['Asistencias_Equipo'],
            'AST/PJ',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_asistencias)
    
    # 4. Pérdidas por partido
    if 'Perdidas_Equipo' in rankings_equipos:
        ranking_perdidas = crear_ranking_premium(
            "❌ PÉRDIDAS",
            rankings_equipos['Perdidas_Equipo'],
            'TO/PJ',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_perdidas)
    
    # Crear separador para poner entre tablas
    separador = Table([[""],], colWidths=[0.4*inch])
    separador.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
    
    # Distribuir las 4 tablas principales en UNA SOLA FILA (formato landscape)
    if len(rankings_premium) >= 4:
        # Ajustar tamaños para que las 4 tablas quepan en una fila en landscape
        ancho_tabla = 2.3*inch  # Mismo tamaño que en COMPARATIVA
        espacio_entre = 0.4*inch  # Separador entre tablas
        
        # UNA SOLA FILA con las 4 tablas: ANOTACIÓN | REBOTES | ASISTENCIAS | PÉRDIDAS
        fila_completa = Table([[rankings_premium[0], separador, rankings_premium[1], separador, rankings_premium[2], separador, rankings_premium[3]]], 
                             colWidths=[ancho_tabla, espacio_entre, ancho_tabla, espacio_entre, ancho_tabla, espacio_entre, ancho_tabla])
        fila_completa.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        fila_completa.hAlign = 'CENTER'
        story.append(fila_completa)
        
    elif len(rankings_premium) >= 2:
        # Fallback para menos de 4 tablas (distribución flexible)
        ancho_tabla = 2.3*inch
        espacio_entre = 0.4*inch
        
        # Primera fila: primeras 2 tablas
        primera_fila = Table([[rankings_premium[0], separador, rankings_premium[1]]], 
                            colWidths=[ancho_tabla, espacio_entre, ancho_tabla])
        primera_fila.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        primera_fila.hAlign = 'CENTER'
        story.append(primera_fila)
        
        # Si hay una tercera tabla, mostrarla centrada en segunda fila
        if len(rankings_premium) > 2:
            story.append(Spacer(1, 0.5*inch))
            tercera_fila = Table([[rankings_premium[2]]], colWidths=[ancho_tabla])
            tercera_fila.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            tercera_fila.hAlign = 'CENTER'
            story.append(tercera_fila)
    
    # Reducir espacio final
    story.append(Spacer(1, 0.2*inch))  # Reducido de 0.5 a 0.2


def crear_pagina_rankings_equipos_continuacion(story, rankings_equipos, df_equipos, equipo_seleccionado, styles):
    """
    Crea una segunda sección de rankings de equipos con estadísticas adicionales en la misma página
    Formato: Tiros libres, Robos, Tiros de campo, Triples
    """
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus.doctemplate import NextPageTemplate
    from pathlib import Path
    import os
    import pandas as pd

    # Solo crear la página si hay rankings de equipos y más de un equipo
    if not rankings_equipos or len(df_equipos) <= 1:
        return
    
    # Salto de página para la continuación y asegurar landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Título principal
    titulo_style = ParagraphStyle(
        'TituloEquipos',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("RANKINGS DE EQUIPOS - CONTINUACIÓN", titulo_style)
    story.append(titulo)
    
    # Nota explicativa en lugar de línea decorativa
    nota_style = ParagraphStyle(
        'NotaRankings',
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=15,
    )
    nota = Paragraph("* Los porcentajes mostrados son promedios de la temporada", nota_style)
    story.append(nota)

    # Función para crear ranking con tabla premium - LIMITAR A 12 EQUIPOS MÁXIMO
    def crear_ranking_premium(titulo, df_sorted, columna, color_header):
        # LIMITAR A 12 EQUIPOS para que quepa en la página landscape
        MAX_EQUIPOS = 12
        total_equipos = len(df_sorted)
        if total_equipos > MAX_EQUIPOS:
            df_sorted = df_sorted.head(MAX_EQUIPOS)
            print(f"⚠️  Tabla '{titulo}' limitada a {MAX_EQUIPOS} equipos (había {total_equipos} totales)")
        
        # Función para acortar nombres largos (versión simplificada)
        def acortar_nombre(nombre, max_chars=22):
            if len(nombre) <= max_chars:
                return nombre
            palabras = nombre.split()
            if len(palabras) > 1:
                iniciales = [p[0] + '.' for p in palabras[:-1]]
                resultado = ' '.join(iniciales + [palabras[-1]])
                if len(resultado) <= max_chars:
                    return resultado
                return resultado[:max_chars-2] + '..'
            return nombre[:max_chars-2] + '..'
        
        # Crear la tabla con los datos
        datos_ranking = []
        
        # Header con color
        header_style = ParagraphStyle(
            'HeaderSimple',
            fontSize=11,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        
        datos_ranking.append([Paragraph(titulo, header_style), ""])
        
        # Añadir filas de equipos
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            equipo_nombre = row['Equipo']
            equipo_nombre_normalizado = normalizar_nombre_equipo(equipo_nombre)  # ✅ APLICAR NORMALIZACIÓN
            valor = row[columna]
            posicion = i + 1  # Posición en el ranking (1º, 2º, 3º, etc.)
            
            # Crear nombre con ranking en negrita
            ranking_bold = f"<b>{posicion}º</b>"
            nombre_acortado = acortar_nombre(equipo_nombre_normalizado, 22)  # ✅ USAR NOMBRE NORMALIZADO
            nombre_mostrar = f"{ranking_bold} {nombre_acortado}"
            es_nuestro = equipo_nombre == equipo_seleccionado  # ✅ COMPARAR CON NOMBRE ORIGINAL
            
            # DEBUG LOGS - VERSIÓN MEJORADA
            if i < 3:  # Solo mostrar primeros 3 equipos para no saturar
                print(f"\n{'='*70}")
                print(f"🔍 DEBUG CONTINUACION - Procesando equipo {i+1} de {len(df_sorted)}")
                print(f"{'='*70}")
                print(f"   � Título tabla: '{titulo}'")
                print(f"   � Columna solicitada: '{columna}'") 
                print(f"   � Equipo: '{row['Equipo']}'")
                print(f"   � Valor en columna '{columna}': {valor}")
                print(f"\n   📊 Datos del equipo:")
                print(f"      - PJ (partidos): {row.get('PJ', 'NO EXISTE')}")
                print(f"      - FG3A (intentos triples): {row.get('FG3A', 'NO EXISTE')}")
                print(f"      - FG3% (porcentaje triples): {row.get('FG3%', 'NO EXISTE')}")
                print(f"\n   � Condiciones evaluadas:")
                print(f"      - ¿columna in ['FG%', 'FG3%', 'FT%', 'Win%']? {columna in ['FG%', 'FG3%', 'FT%', 'Win%']}")
                print(f"      - ¿'FG3A' in columna? {'FG3A' in columna}")
                print(f"      - ¿'FG3%' in columna? {'FG3%' in columna}")
                print(f"      - ¿'PJ' in row.index? {'PJ' in row.index if hasattr(row, 'index') else 'NO INDEX'}")
                print(f"      - ¿'TRIPLES' in titulo? {'TRIPLES' in titulo}")
            
            # Formatear número en negrita
            # ⚠️ IMPORTANTE: Primero verificar si es tabla de TRIPLES antes de otras condiciones
            if ('FG3A' in columna or 'FG3%' in columna) and 'PJ' in row.index and "TRIPLES" in titulo:
                # 🎯 LÓGICA ESPECÍFICA PARA TABLA DE TRIPLES
                if i < 3:
                    print(f"\n   🎯🎯🎯 RAMA TRIPLES: ENTRANDO EN LÓGICA DE TABLA DE TRIPLES! 🎯🎯🎯")
                
                # Para la tabla de triples: mostrar intentos por partido y porcentaje
                # Obtener intentos por partido desde FG3A
                intentos_por_partido = row['FG3A'] / row['PJ'] if row['PJ'] > 0 and 'FG3A' in row else 0
                porcentaje = row['FG3%'] if 'FG3%' in row and pd.notna(row['FG3%']) else 0
                
                if i < 3:
                    print(f"      📊 FG3A (total intentos): {row.get('FG3A', 'NO EXISTE')}")
                    print(f"      📊 PJ (partidos): {row.get('PJ', 'NO EXISTE')}")
                    print(f"      ➗ Cálculo: {row.get('FG3A', 0)} / {row.get('PJ', 1)} = {intentos_por_partido:.1f} intentos/partido")
                    print(f"      📈 Porcentaje: {porcentaje:.1f}%")
                
                # Formato en una sola línea: "34.0 41.2%"
                if porcentaje == 100.0:
                    valor_texto = f"<b>{intentos_por_partido:.1f} 100%</b>"
                else:
                    valor_texto = f"<b>{intentos_por_partido:.1f} {porcentaje:.1f}%</b>"
                
                if i < 3:
                    print(f"   🎯 Valor FINAL formateado (una línea):")
                    print(f"      Formato: {intentos_por_partido:.1f} {porcentaje:.1f}%")
                    print(f"      HTML: {valor_texto}")
                    
            elif columna in ['FG%', 'FG3%', 'FT%', 'Win%', 'eFG%']:
                # Condición de porcentajes (para otras tablas que no sean TRIPLES)
                if i < 3:
                    print(f"\n   ✅ RAMA 1: Entrando en condición de PORCENTAJES (no es tabla de triples)")
                # Si es 100.0%, mostrar como 100% sin decimal
                if valor == 100.0:
                    valor_texto = f"<b>{int(valor)}%</b>"
                else:
                    valor_texto = f"<b>{valor:.1f}%</b>"
                if i < 3:
                    print(f"   🎯 Valor formateado (solo porcentaje): {valor_texto}")
            
            elif columna == 'FTr':
                # Para FTr mostrar como decimal (ej: 0.22)
                if i < 3:
                    print(f"\n   ✅ RAMA FTr: Mostrando como decimal")
                valor_texto = f"<b>{valor:.2f}</b>"
                if i < 3:
                    print(f"   🎯 Valor formateado (decimal): {valor_texto}")
                    
            elif ('FG3A' in columna or 'FG3%' in columna) and 'PJ' in row.index:
                # Para otras tablas con estadísticas de triples (no la tabla principal de TRIPLES)
                if i < 3:
                    print(f"\n   ✅ RAMA 2: Formato alternativo para estadísticas de triples")
                intentos = valor / row['PJ'] if row['PJ'] > 0 else 0
                porcentaje = row['FG3%'] if 'FG3%' in row and pd.notna(row['FG3%']) else 0
                valor_texto = f"<b>{intentos:.1f} ({porcentaje:.1f}%)</b>"
                if i < 3:
                    print(f"   🎯 Valor formateado: {valor_texto}")
                    
            else:
                if i < 3:
                    print(f"\n   ✅ RAMA 3: Formato numérico simple")
                # Formato en negrita: sin decimales si es entero
                valor_formateado = f"{int(valor)}" if valor == int(valor) else f"{valor:.1f}"
                valor_texto = f"<b>{valor_formateado}</b>"
                if i < 3:
                    print(f"   🎯 Valor formateado (número): {valor_texto}")
            
            # Estilos con ranking y valores en negrita
            if es_nuestro:
                color_texto = color_header
                nombre_style = ParagraphStyle('', fontSize=10, textColor=color_texto, 
                                            alignment=0, fontName='Helvetica-Bold', leading=11)  # Reducido de 13 a 11
                valor_style = ParagraphStyle('', fontSize=11, textColor=color_texto, 
                                        alignment=2, fontName='Helvetica', leading=11)  # Reducido de 13 a 11
            else:
                nombre_style = ParagraphStyle('', fontSize=9.5, textColor=colors.black, 
                                            alignment=0, fontName='Helvetica', leading=12)  # Permite HTML
                valor_style = ParagraphStyle('', fontSize=10.5, textColor=colors.black, 
                                        alignment=2, fontName='Helvetica', leading=12)  # Permite HTML para negrita
            
            datos_ranking.append([
                Paragraph(nombre_mostrar, nombre_style),
                Paragraph(valor_texto, valor_style)
            ])
        
        # Crear tabla con diseño mejorado - usando los mismos tamaños que en COMPARATIVA
        tabla = Table(datos_ranking, colWidths=[1.6*inch, 0.7*inch], rowHeights=None, splitByRow=True)
        
        # Estilos con colores consistentes
        estilos = [
            # Header con color
            ('SPAN', (0, 0), (1, 0)),  # Unir celdas del header
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), color_header),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Contenido - usando los mismos paddings que COMPARATIVA
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, -1), 8),
            ('RIGHTPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 5),    # ✅ SEGUNDA PÁGINA: Aumentado de 3 a 5 para mejor espaciado
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5), # ✅ SEGUNDA PÁGINA: Aumentado de 3 a 5 para mejor espaciado
            
            # Bordes
            ('BOX', (0, 0), (-1, -1), 1, color_header),
            ('LINEBELOW', (0, 0), (-1, 0), 1, color_header),
        ]
        
        # Alternar colores de fondo para las filas y colores para equipo seleccionado
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            equipo_nombre = row['Equipo']
            valor = row[columna]
            
            # Verificar si es número de 3 cifras con decimal (como 104.4)
            es_numero_3_cifras_decimal = (isinstance(valor, (int, float)) and 
                                        valor >= 100 and valor < 1000 and 
                                        valor != int(valor))  # Tiene decimal
            
            if equipo_nombre == equipo_seleccionado:
                estilos_equipo = [
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor("#ffe6e6")),  # Fondo rojito claro para equipo seleccionado
                    ('LINEBELOW', (0, i), (-1, i), 0.5, color_header),
                ]
                
                # Solo aplicar RIGHTPADDING reducido si es número de 3 cifras con decimal
                if es_numero_3_cifras_decimal:
                    estilos_equipo.append(('RIGHTPADDING', (0, i), (0, i), 2))  # Reducir espacio solo para 3 cifras con decimal
                
                estilos.extend(estilos_equipo)
            else:
                # Filas zebra CONSISTENTE con rankings individuales: fila par -> gris claro, fila impar -> blanco
                if i % 2 == 0:  # Filas pares (2,4,6...) -> gris claro (consistente con rankings individuales)
                    estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8f9fa")))  # Mismo gris que rankings individuales
                # Las filas impares (1,3,5...) quedan blancas por defecto
                # Líneas horizontales entre filas
                estilos.append(('LINEBELOW', (0, i), (-1, i), 0.25, color_header))
        
        tabla.setStyle(TableStyle(estilos))
        
        # Contenedor con borde suave del color correspondiente - igual que en COMPARATIVA
        contenedor_data = [[tabla]]
        contenedor = Table(contenedor_data, colWidths=[2.3*inch])
        contenedor.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),  # Fondo gris claro
        ]))
        
        return contenedor

    # Seleccionar las 4 nuevas estadísticas
    rankings_premium = []
    
    # 1. eFG% (Porcentaje de tiro efectivo)
    if 'FG_Percentage_Equipo' in rankings_equipos:
        # Calcular eFG% para cada equipo: (FGM + 0.5 * 3PM) / FGA
        df_efg = rankings_equipos['FG_Percentage_Equipo'].copy()
        df_efg['eFG%'] = ((df_efg['FGM'] + 0.5 * df_efg['FG3M']) / df_efg['FGA'] * 100).round(1)
        df_efg_sorted = df_efg.sort_values('eFG%', ascending=False).reset_index(drop=True)
        
        ranking_efg = crear_ranking_premium(
            "📊 eFG% (TIRO EFECTIVO)", 
            df_efg_sorted, 
            'eFG%', 
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_efg)
    
    # 2. Robos
    if 'Robos_Equipo' in rankings_equipos:
        ranking_robos = crear_ranking_premium(
            "🔓 ROBOS",
            rankings_equipos['Robos_Equipo'],
            'STL/PJ',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_robos)
    
    # 3. Tiros de campo
    if 'FG_Percentage_Equipo' in rankings_equipos:
        ranking_tc = crear_ranking_premium(
            "🏀 TIROS DE CAMPO",
            rankings_equipos['FG_Percentage_Equipo'],
            'FG%',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_tc)
    
    # 4. FTr (Ratio de tiros libres)
    if 'FT_Percentage_Equipo' in rankings_equipos:
        # Calcular FTr para cada equipo: FTA / FGA
        df_ftr = rankings_equipos['FT_Percentage_Equipo'].copy()
        df_ftr['FTr'] = (df_ftr['FTA'] / df_ftr['FGA']).round(2)
        df_ftr_sorted = df_ftr.sort_values('FTr', ascending=False).reset_index(drop=True)
        
        ranking_ftr = crear_ranking_premium(
            "⚡ FTr (AGRESIVIDAD)",
            df_ftr_sorted,
            'FTr',
            colors.HexColor('#4a5568')  # Gris oscuro uniforme
        )
        rankings_premium.append(ranking_ftr)
    
    # Crear separador para poner entre tablas
    separador = Table([[""],], colWidths=[0.4*inch])
    separador.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
    
    # Distribuir las 4 tablas en UNA SOLA FILA (formato landscape)
    if len(rankings_premium) >= 4:
        # Usando los mismos tamaños que en COMPARATIVA
        ancho_tabla = 2.3*inch  # Mismo tamaño que en COMPARATIVA
        espacio_entre = 0.4*inch  # Separador entre tablas
        
        # UNA SOLA FILA con las 4 tablas: eFG% | ROBOS | TIROS DE CAMPO | FTr
        fila_completa = Table([[rankings_premium[0], separador, rankings_premium[1], separador, rankings_premium[2], separador, rankings_premium[3]]], 
                             colWidths=[ancho_tabla, espacio_entre, ancho_tabla, espacio_entre, ancho_tabla, espacio_entre, ancho_tabla])
        fila_completa.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        fila_completa.hAlign = 'CENTER'
        story.append(fila_completa)
        
    elif len(rankings_premium) >= 2:
        # Fallback para menos de 4 tablas (distribución flexible)
        ancho_tabla = 2.3*inch
        espacio_entre = 0.4*inch
        
        # Primera fila: primeras 2 tablas
        primera_fila = Table([[rankings_premium[0], separador, rankings_premium[1]]], 
                            colWidths=[ancho_tabla, espacio_entre, ancho_tabla])
        primera_fila.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        primera_fila.hAlign = 'CENTER'
        story.append(primera_fila)
        
        # Si hay más tablas, mostrarlas en segunda fila
        if len(rankings_premium) > 2:
            story.append(Spacer(1, 0.5*inch))
            if len(rankings_premium) == 3:
                # Una tabla centrada
                tercera_fila = Table([[rankings_premium[2]]], colWidths=[ancho_tabla])
                tercera_fila.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                tercera_fila.hAlign = 'CENTER'
                story.append(tercera_fila)
    
    # Reducir espacio final
    story.append(Spacer(1, 0.2*inch))  # Reducido de 0.5 a 0.2


def crear_pagina_rankings_tiros(story, rankings_equipos, df_equipos, equipo_seleccionado, styles):
    """
    Crea una página adicional con tablas anchas para TIROS LIBRES y TRIPLES
    Formato ancho: Muestra tanto intentos como porcentaje en la misma línea
    """
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus.doctemplate import NextPageTemplate
    import pandas as pd

    # Solo crear la página si hay datos
    if not rankings_equipos or len(df_equipos) <= 1:
        return
    
    # Salto de página y asegurar landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Título principal
    titulo_style = ParagraphStyle(
        'TituloEquipos',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("RANKINGS DE EQUIPOS - CONTINUACIÓN", titulo_style)
    story.append(titulo)
    
    # Nota explicativa
    nota_style = ParagraphStyle(
        'NotaRankings',
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=15,
    )
    nota = Paragraph("* Valores mostrados: (Intentos por partido) Porcentaje de acierto", nota_style)
    story.append(nota)
    
    # Función para crear tabla ancha con intentos + porcentaje (MISMO FORMATO QUE OTRAS TABLAS)
    def crear_ranking_ancho(titulo, df_sorted, columna_intentos, columna_pct, color_header, emoji):
        MAX_EQUIPOS = 12
        total_equipos = len(df_sorted)
        if total_equipos > MAX_EQUIPOS:
            df_sorted = df_sorted.head(MAX_EQUIPOS)
            print(f"⚠️  Tabla '{titulo}' limitada a {MAX_EQUIPOS} equipos (había {total_equipos} totales)")
        
        def acortar_nombre(nombre, max_chars=22):
            if len(nombre) <= max_chars:
                return nombre
            palabras = nombre.split()
            if len(palabras) > 1:
                iniciales = [p[0] + '.' for p in palabras[:-1]]
                resultado = ' '.join(iniciales + [palabras[-1]])
                if len(resultado) <= max_chars:
                    return resultado
                return resultado[:max_chars-2] + '..'
            return nombre[:max_chars-2] + '..'
        
        # Crear datos de la tabla
        datos_ranking = []
        
        # Header
        header_style = ParagraphStyle(
            'HeaderSimple',
            fontSize=11,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        datos_ranking.append([Paragraph(f"{emoji} {titulo}", header_style), ""])
        
        # Añadir filas
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            equipo_nombre = row['Equipo']
            equipo_nombre_normalizado = normalizar_nombre_equipo(equipo_nombre)
            posicion = i + 1
            es_nuestro = equipo_nombre == equipo_seleccionado
            
            # Calcular intentos por partido y porcentaje
            intentos_total = row.get(columna_intentos, 0)
            pj = row.get('PJ', 1)
            intentos_pp = intentos_total / pj if pj > 0 else 0
            porcentaje = row.get(columna_pct, 0)
            
            # Formato: "(34.0) 41.2%" (con paréntesis)
            if porcentaje == 100.0:
                valor_texto = f"<b>({intentos_pp:.1f}) 100%</b>"
            else:
                valor_texto = f"<b>({intentos_pp:.1f}) {porcentaje:.1f}%</b>"
            
            # Nombre con ranking
            ranking_bold = f"<b>{posicion}º</b>"
            nombre_acortado = acortar_nombre(equipo_nombre_normalizado, 22)
            nombre_mostrar = f"{ranking_bold} {nombre_acortado}"
            
            # Estilos (MISMO QUE OTRAS TABLAS)
            if es_nuestro:
                color_texto = color_header
                nombre_style = ParagraphStyle('', fontSize=10, textColor=color_texto, 
                                            alignment=0, fontName='Helvetica-Bold', leading=11)
                valor_style = ParagraphStyle('', fontSize=11, textColor=color_texto, 
                                        alignment=2, fontName='Helvetica', leading=11)
            else:
                nombre_style = ParagraphStyle('', fontSize=9.5, textColor=colors.black, 
                                            alignment=0, fontName='Helvetica', leading=12)
                valor_style = ParagraphStyle('', fontSize=10.5, textColor=colors.black, 
                                        alignment=2, fontName='Helvetica', leading=12)
            
            datos_ranking.append([
                Paragraph(nombre_mostrar, nombre_style),
                Paragraph(valor_texto, valor_style)
            ])
        
        # Crear tabla MÁS ANCHA para que no haya saltos de línea (3.0 inch cada una)
        tabla = Table(datos_ranking, colWidths=[1.8*inch, 1.2*inch], rowHeights=None, splitByRow=True)
        
        # Estilos EXACTAMENTE IGUALES a crear_ranking_premium
        estilos = [
            # Header con color
            ('SPAN', (0, 0), (1, 0)),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), color_header),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Contenido
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, -1), 8),
            ('RIGHTPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            
            # Bordes
            ('BOX', (0, 0), (-1, -1), 1, color_header),
            ('LINEBELOW', (0, 0), (-1, 0), 1, color_header),
        ]
        
        # Alternar colores de fondo y resaltar equipo seleccionado (EXACTAMENTE IGUAL)
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            equipo_nombre = row['Equipo']
            
            if equipo_nombre == equipo_seleccionado:
                estilos_equipo = [
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor("#ffe6e6")),  # Fondo rojito claro
                    ('LINEBELOW', (0, i), (-1, i), 0.5, color_header),
                ]
                estilos.extend(estilos_equipo)
            else:
                # Filas zebra: fila par -> gris claro, fila impar -> blanco
                if i % 2 == 0:
                    estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8f9fa")))
                estilos.append(('LINEBELOW', (0, i), (-1, i), 0.25, color_header))
        
        tabla.setStyle(TableStyle(estilos))
        
        # Contenedor MÁS ANCHO (3.0 inch para evitar saltos de línea)
        contenedor_data = [[tabla]]
        contenedor = Table(contenedor_data, colWidths=[3.0*inch])
        contenedor.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
        ]))
        
        return contenedor
    
    # Crear las TRES tablas
    tablas_anchas = []
    
    # 1. TIROS LIBRES
    if 'FT_Percentage_Equipo' in rankings_equipos:
        df_tl = rankings_equipos['FT_Percentage_Equipo'].copy()
        df_tl_sorted = df_tl.sort_values('FT%', ascending=False).reset_index(drop=True)
        
        ranking_tl_ancho = crear_ranking_ancho(
            "TIROS LIBRES",
            df_tl_sorted,
            'FTA',  # Columna de intentos
            'FT%',  # Columna de porcentaje
            colors.HexColor('#4a5568'),
            "🎯"
        )
        tablas_anchas.append(ranking_tl_ancho)
    
    # 2. TRIPLES
    if 'Triples_Equipo' in rankings_equipos:
        df_triples = rankings_equipos['Triples_Equipo'].copy()
        df_triples_sorted = df_triples.sort_values('FG3%', ascending=False).reset_index(drop=True)
        
        ranking_triples_ancho = crear_ranking_ancho(
            "TRIPLES",
            df_triples_sorted,
            'FG3A',  # Columna de intentos
            'FG3%',  # Columna de porcentaje
            colors.HexColor('#4a5568'),
            "🏹"
        )
        tablas_anchas.append(ranking_triples_ancho)
    
    # 3. TIROS DE 2 (nuevos!)
    if 'FG2_Percentage_Equipo' in rankings_equipos:
        df_fg2 = rankings_equipos['FG2_Percentage_Equipo'].copy()
        df_fg2_sorted = df_fg2.sort_values('FG2%', ascending=False).reset_index(drop=True)
        
        ranking_fg2_ancho = crear_ranking_ancho(
            "TIROS DE 2",
            df_fg2_sorted,
            'FG2A',  # Columna de intentos
            'FG2%',  # Columna de porcentaje
            colors.HexColor('#4a5568'),
            "🏀"
        )
        tablas_anchas.append(ranking_fg2_ancho)
    
    # Distribuir las 3 tablas centradas en UNA FILA (más anchas, separadas menos)
    if len(tablas_anchas) >= 3:
        separador = Table([[""],], colWidths=[0.3*inch])
        separador.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
        
        fila_tablas = Table([[tablas_anchas[0], separador, tablas_anchas[1], separador, tablas_anchas[2]]], 
                           colWidths=[3.0*inch, 0.3*inch, 3.0*inch, 0.3*inch, 3.0*inch])
        fila_tablas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        story.append(fila_tablas)
    elif len(tablas_anchas) == 2:
        # Fallback: solo 2 tablas
        separador = Table([[""],], colWidths=[0.5*inch])
        separador.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
        
        fila_tablas = Table([[tablas_anchas[0], separador, tablas_anchas[1]]], 
                           colWidths=[3.0*inch, 0.5*inch, 3.0*inch])
        fila_tablas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        story.append(fila_tablas)
        fila_tablas.hAlign = 'CENTER'
        story.append(fila_tablas)
    
    story.append(Spacer(1, 0.2*inch))


def crear_pagina_rankings(story, rankings, styles, equipo_url=None, df_resultados=None):
    """
    Crea páginas de rankings de jugadores con 3 tablas independientes por página
    Cada tabla es completamente independiente con su propio espacio
    """
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.styles import ParagraphStyle
    from pathlib import Path
    import os
    
    # Obtener números de jugadores si tenemos información del equipo
    numeros_jugadores = {}
    if equipo_url:
        try:
            print(f"🔍 DEBUG - Obteniendo números para equipo: {equipo_url}")
            numeros_jugadores = obtener_numeros_jugadores_equipo(equipo_url, df_resultados)
            print(f"📋 Obtenidos números para {len(numeros_jugadores.get('por_id', {}))} jugadores por ID")
            print(f"📋 Obtenidos números para {len(numeros_jugadores.get('por_nombre', {}))} jugadores por nombre")
        except Exception as e:
            print(f"⚠️ Error obteniendo números de jugadores: {e}")
    else:
        print(f"⚠️ DEBUG - No se recibió equipo_url en crear_pagina_rankings")
    
    # Cambiar a plantilla landscape y añadir salto de página
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # 🏀 TÍTULO PRINCIPAL ELEGANTE
    titulo_style = ParagraphStyle(
        'TituloElegante',
        parent=styles['Heading1'],
        fontSize=26,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=25,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("RANKINGS DE JUGADORES", titulo_style)
    story.append(titulo)
    
    # Nota explicativa en lugar de línea decorativa
    nota_style = ParagraphStyle(
        'NotaRankings',
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        fontName='Helvetica',
        spaceAfter=20,
    )
    nota = Paragraph("* Las estadísticas mostradas son promedios por partido de la temporada", nota_style)
    story.append(nota)
    
    def crear_tabla_ranking_independiente(categoria, df_ranking):
        """Crea una tabla completamente independiente para cada categoría"""
        
        # 🏷️ Configuración de categorías
        config_categorias = {
            'Puntos': {'titulo': 'ANOTACIÓN', 'emoji': '🏀'},
            'Valoracion': {'titulo': 'VALORACIÓN', 'emoji': '⭐'},
            'Rebotes': {'titulo': 'REBOTES', 'emoji': '💪'},
            'Triples_Intentados': {'titulo': 'T3 TIRADOS POR PARTIDO (%T3)', 'emoji': '🎯'},
            'Robos': {'titulo': 'ROBOS', 'emoji': '🛡️'},
            'Uso': {'titulo': 'PROTAGONISMO', 'emoji': '👑'},
            'Rebotes_Ofensivos': {'titulo': 'REB. OFENSIVO', 'emoji': '🚀'},
            'Asistencias': {'titulo': 'ASISTENCIAS', 'emoji': '🎯'},
            'Tiros_Libres': {'titulo': 'TIROS LIBRES (TL/PJ - %)', 'emoji': '🎯'},
            'True_Shooting': {'titulo': 'EFIC. TIRO (TS%)', 'emoji': '📈'}
        }
        
        config = config_categorias.get(categoria, {'titulo': categoria, 'emoji': '📊'})
        
        # Crear datos de la tabla
        tabla_data = []
        
        # Header con fondo gris oscuro y texto blanco - TAMAÑO MEDIO
        header_style = ParagraphStyle(
            'HeaderRankingJugadores',
            fontSize=12,  # Reducido de 14 a 12
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=14  # Reducido de 16 a 14
        )
        
        # Header unificado - MÁS ALTO
        tabla_data.append([
            Paragraph(f"{config['emoji']} {config['titulo']}", header_style)
        ])
        
        # Top 7 jugadores en lugar de 8
        for i, (_, jugador) in enumerate(df_ranking.head(7).iterrows()):
            nombre = jugador['Jugador'].split(',')[0] if ',' in jugador['Jugador'] else jugador['Jugador']
            foto_path = jugador.get('foto_path', '')
            
            # Buscar número de camiseta usando la nueva función
            numero = buscar_numero_jugador(jugador, numeros_jugadores)
            if numero:
                nombre = f"<b>#{numero}</b> {nombre}"
            
            # Obtener foto del jugador - TAMAÑO MEDIO
            img = None
            
            # Método 1: Buffer con player_id (intentar con ID del enlace)
            player_id = jugador.get('ID', '')
            if player_id:
                try:
                    photo_buffer = get_player_photo_buffer(str(player_id))
                    if photo_buffer:
                        img = pil_buffer_to_reportlab_image(photo_buffer, width=0.5*inch, height=0.5*inch)  # Reducido de 0.6 a 0.5
                except Exception as e:
                    pass
            
            # Método 2: Ruta de archivo
            if img is None and foto_path and os.path.exists(foto_path):
                try:
                    img = Image(foto_path, width=0.5*inch, height=0.5*inch)  # Reducido de 0.6 a 0.5
                except Exception as e:
                    pass
            
            # Método 3: Placeholder
            if img is None:
                placeholder_style = ParagraphStyle('', fontSize=16, alignment=TA_CENTER)  # Reducido de 18 a 16
                img = Paragraph("👤", placeholder_style)
            
            # Obtener valor estadístico
            valor = 0.0
            if categoria == 'Puntos':
                valor = jugador['PTS/PJ']
            elif categoria == 'Valoracion':
                valor = jugador['VAL/PJ']
            elif categoria == 'Rebotes':
                valor = jugador['REB/PJ']
            elif categoria == 'Robos':
                valor = jugador['STL/PJ']
            elif categoria == 'Triples_Intentados':
                valor = jugador['FG3A/PJ']
            elif categoria == 'Rebotes_Ofensivos':
                valor = jugador['OREB/PJ']
            elif categoria == 'Uso':
                valor = jugador['USG%']
            elif categoria == 'Asistencias':
                valor = jugador['AST/PJ']
            elif categoria == 'Tiros_Libres':
                valor = jugador['FT%']
                # Obtener también los tiros libres tirados por partido
                tiros_libres_pp = jugador.get('FTA/PJ', 0) if 'FTA/PJ' in jugador else 0
            elif categoria == 'True_Shooting':
                valor = jugador['TS%']
            
            # Formatear valor según categoría
            if categoria == 'Triples_Intentados':
                porcentaje = jugador['FG3%'] if 'FG3%' in jugador and jugador['FG3%'] > 0 else 0
                porcentaje_formateado = formatear_porcentaje_sin_salto(porcentaje)
                valor_texto = f"{valor:.1f}<br/>{porcentaje_formateado}"
            elif categoria == 'Tiros_Libres':
                # Incluir tanto el porcentaje como los tiros tirados por partido
                porcentaje_formateado = formatear_porcentaje_sin_salto(valor)
                valor_texto = f"{tiros_libres_pp:.1f}<br/>{porcentaje_formateado}"
            elif categoria in ['True_Shooting', 'Uso']:
                valor_texto = formatear_porcentaje_sin_salto(valor)
            else:
                valor_texto = f"{valor:.1f}"
            
            # Crear fila interna para cada jugador (posición + foto + nombre + valor) - NÚMEROS CENTRADOS
            fila_data = [
                [
                    Paragraph(f"{i+1}º", ParagraphStyle('', fontSize=11, textColor=colors.black, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=13, spaceBefore=0, spaceAfter=0)),  # Centrado perfecto
                    img,
                    Paragraph(nombre, ParagraphStyle('', fontSize=10, textColor=colors.black, alignment=TA_LEFT, fontName='Helvetica')),
                    Paragraph(valor_texto, ParagraphStyle('', fontSize=11, textColor=colors.black, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=13, spaceBefore=0, spaceAfter=0))  # Centrado perfecto para valores
                ]
            ]
            
            # Crear subtabla para esta fila de jugador - CENTRADO PERFECTO
            fila_tabla = Table(fila_data, colWidths=[0.35*inch, 0.6*inch, 1.7*inch, 0.65*inch])
            fila_tabla.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centrado vertical perfecto
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),    # Posición centrada horizontal y verticalmente
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),    # Foto centrada
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),      # Nombre a la izquierda
                ('ALIGN', (3, 0), (3, -1), 'CENTER'),    # Valor centrado horizontal y verticalmente
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa") if i % 2 == 0 else colors.white),
                ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#4a5568')),  # Solo líneas horizontales
            ]))
            
            # Añadir la subtabla como una celda
            tabla_data.append([fila_tabla])
        
        # Crear tabla principal con estructura unificada - ANCHO MEDIO
        tabla = Table(tabla_data, colWidths=[3.3*inch])  # Reducido de 3.8 a 3.3
        
        # Estilos de tabla principal
        estilos = [
            # Header - ALTURA MEDIA
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),  # Fondo gris
            ('TOPPADDING', (0, 0), (-1, 0), 8),   # Reducido de 14 a 8 para menor altura
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8), # Reducido de 14 a 8 para menor altura
            
            # Contenido
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 1), (-1, -1), 0),
            ('RIGHTPADDING', (0, 1), (-1, -1), 0),
            ('TOPPADDING', (0, 1), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 0),
            
            # Bordes principales
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#4a5568')),  # Borde exterior fino como equipos
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#4a5568')),  # Línea bajo header fina
        ]
        
        tabla.setStyle(TableStyle(estilos))
        
        return tabla
    
    # Organizar rankings - Primera página
    orden_rankings_pagina1 = ['Puntos', 'Valoracion', 'Rebotes', 'Triples_Intentados']
    if 'Uso' in rankings:
        orden_rankings_pagina1.extend(['Uso', 'Robos'])
    else:
        orden_rankings_pagina1.extend(['Robos', 'Rebotes_Ofensivos'])
    
    # Segunda página - Nuevas categorías
    orden_rankings_pagina2 = ['Asistencias', 'Tiros_Libres', 'True_Shooting']
    
    # Combinar todas las categorías
    orden_rankings_completo = orden_rankings_pagina1 + orden_rankings_pagina2
    
    # Crear tablas independientes
    tablas_creadas = []
    for categoria in orden_rankings_completo:
        if categoria in rankings and not rankings[categoria].empty:
            tabla = crear_tabla_ranking_independiente(categoria, rankings[categoria])
            tablas_creadas.append(tabla)
    
    if not tablas_creadas:
        mensaje_error_style = ParagraphStyle(
            'MensajeError',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#e53e3e'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        mensaje = Paragraph("⚠️  No hay datos disponibles para mostrar rankings", mensaje_error_style)
        story.append(mensaje)
        return
    
    # Agrupar de 3 en 3 y crear páginas
    for i in range(0, len(tablas_creadas), 3):
        if i > 0:  # Salto de página antes de cada nueva página (excepto la primera)
            story.append(NextPageTemplate('landscape'))  # Asegurar plantilla con watermark
            story.append(PageBreak())
            story.append(titulo)  # Repetir título en cada página
            story.append(nota)   # Repetir nota en cada página
        
        # Tomar hasta 3 tablas para esta página
        tablas_pagina = tablas_creadas[i:i+3]
        
        # Crear una fila con las 3 tablas independientes
        fila_tablas = []
        
        # Rellenar hasta 3 elementos
        while len(tablas_pagina) < 3:
            # Crear tabla vacía del mismo tamaño
            tabla_vacia = Table([[""]], colWidths=[3.3*inch], rowHeights=[1*inch])  # Reducido de 3.8 a 3.3
            tabla_vacia.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
            tablas_pagina.append(tabla_vacia)
        
        # Crear tabla contenedora con las 3 tablas - ANCHO MEDIO
        tabla_contenedora = Table([tablas_pagina], colWidths=[3.5*inch, 3.5*inch, 3.5*inch])  # Reducido de 4.0 a 3.5
        tabla_contenedora.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centrado para distribución uniforme
            ('LEFTPADDING', (0, 0), (-1, -1), 0.275*inch),   # Espaciado calculado uniformemente
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.275*inch),  # Espaciado calculado uniformemente
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        tabla_contenedora.hAlign = 'CENTER'  # Centrado para distribución uniforme
        story.append(tabla_contenedora)
        
        # Añadir explicaciones específicas al final de cada página
        story.append(Spacer(1, 15))
        explicacion_style = ParagraphStyle(
            'Explicacion',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER,
            fontName='Helvetica',
        )
        
        # Determinar qué categorías están en esta página
        categorias_pagina = orden_rankings_completo[i:i+3]
        
        # Primera página (incluye "Uso" - Protagonismo)
        if 'Uso' in categorias_pagina and 'Uso' in rankings and not rankings['Uso'].empty:
            explicacion_uso = Paragraph("* Protagonismo = % USG (Porcentaje de posesiones del equipo utilizadas)", explicacion_style)
            story.append(explicacion_uso)
        
        # Segunda página (incluye "True_Shooting" - TS%)
        if 'True_Shooting' in categorias_pagina and 'True_Shooting' in rankings and not rankings['True_Shooting'].empty:
            explicacion_ts = Paragraph("* TS% Eficiencia total de tiro que incluye tiros de campo, triples y libres ponderados.", explicacion_style)
            story.append(explicacion_ts)


def generar_pdf_informe(equipo_data, df_jugadores_norm, df_principales, df_apoyo, rankings, df_grupo=None, rankings_equipos=None, filename=None, equipo_url=None, df_resultados=None, JSON_PATH=None, temporada="2025", liga=None):
    """
    Genera un PDF completo del informe del equipo con diseño atractivo.
    Retorna una lista de elementos para ser añadidos al story principal.
    
    Args:
        equipo_data: Serie con datos del equipo
        df_jugadores_norm: DataFrame con jugadores normalizados
        df_principales: DataFrame con jugadores principales
        df_apoyo: DataFrame con jugadores de apoyo
        rankings: Diccionario con rankings de jugadores
        df_grupo: DataFrame con todos los equipos del grupo
        rankings_equipos: Diccionario con rankings de equipos
        filename: No se usa en esta versión (retorna elementos)
        equipo_url: URL del equipo para obtener números de jugadores
        df_resultados: DataFrame con resultados para shot charts
        JSON_PATH: Path al archivo JSON de datos (para historial de jugadores)
        temporada: Temporada actual (para buscar historial en temporadas anteriores)
        liga: Liga del equipo (para filtrar partidos por liga en la página de últimos partidos)
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, BaseDocTemplate, Frame, PageTemplate
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from pathlib import Path
    import os
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para título principal (más compacto)
    titulo_style = ParagraphStyle(
        'TituloEquipo',
        parent=styles['Heading1'],
        fontSize=28,  # Reducido de 36 a 28
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
        spaceAfter=20,  # Reducido de 30 a 20
        fontName='Helvetica-Bold',
        leading=32  # Reducido de 44 a 32
    )

    # Estilo específico para el título de la comparativa (más compacto)
    titulo_comparativa_style = ParagraphStyle(
        'TituloComparativa',
        parent=titulo_style,
        fontSize=24,     # Reducido para ser más compacto
        leading=28,      # Reducido para menos espacio
        spaceAfter=10,   # Reducido de 18 a 10
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos
    subtitulo_style = ParagraphStyle(
        'Subtitulo',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold',
    )
    
    # Estilo para números grandes (más pequeños)
    numero_grande_style = ParagraphStyle(
        'NumeroGrande',
        parent=styles['Normal'],
        fontSize=36,
        textColor=colors.HexColor('#2b6cb0'),
        alignment=TA_CENTER,
        spaceAfter=5,
        fontName='Helvetica-Bold',
    )
    
    # Estilo para etiquetas de números (más pequeñas)
    etiqueta_style = ParagraphStyle(
        'Etiqueta',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#4a5568'),
        alignment=TA_CENTER,
        spaceAfter=12,
        fontName='Helvetica'
    )
    
    story = []
    
    # === CONFIGURAR PLANTILLAS DE PÁGINA ===
    from reportlab.platypus import NextPageTemplate
    
    # Usar plantilla de primera página (sin watermark) para la portada
    story.append(NextPageTemplate('primera_pagina'))
    
    # === PÁGINA 1: PORTADA DEL EQUIPO (LANDSCAPE) ===
    
    # IMPORTANTE: Para que la primera página sea landscape, necesitamos usar NextPageTemplate 
    # al inicio de story, antes de cualquier contenido
    from reportlab.platypus import NextPageTemplate
    
    # Crear una portada en landscape simplificada y elegante
    def crear_portada_landscape():
        """Crea una portada elegante en formato landscape - SIMPLIFICADA"""
        
        def buscar_logo_equipo():
            """Busca el logo del equipo"""
            logo_path = equipo_data.get('logo_path')
            if logo_path and os.path.exists(logo_path):
                return logo_path
            return None
        
        # Obtener ruta del logo del equipo
        logo_equipo_path = buscar_logo_equipo()
        
        # === NOMBRE DEL EQUIPO MUY GRANDE EN LA PARTE SUPERIOR ===
        nombre_equipo = equipo_data['Equipo']
        
        # Estilo para el título del equipo en landscape - MÁS GRANDE
        titulo_landscape_style = ParagraphStyle(
            'TituloLandscape',
            parent=titulo_style,
            fontSize=36,  # Más grande que antes (era 28)
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_CENTER,
            spaceAfter=30,  # Más espacio después
            fontName='Helvetica-Bold',
        )
        
        titulo_equipo = Paragraph(nombre_equipo, titulo_landscape_style)
        
        # === LOGO DEL EQUIPO EN EL CENTRO ===
        if logo_equipo_path:
            try:
                # Usar dimensiones moderadas para buen balance entre tamaño y layout
                logo_equipo = Image(logo_equipo_path, width=2.8*inch, height=2.3*inch, kind='proportional')
            except:
                logo_equipo = Paragraph("🏀", ParagraphStyle('EmojiEquipo', fontSize=96, alignment=TA_CENTER))  # Emoji más grande
        else:
            logo_equipo = Paragraph("🏀", ParagraphStyle('EmojiEquipo', fontSize=96, alignment=TA_CENTER))
        
        # === LOGOS HORIZONTALES: PI SCOUTING + EQUIPO + PI SCOUTING ===
        from pathlib import Path
        
        # Detectar si estamos ejecutando desde notebooks o desde raíz
        current_dir = Path.cwd()
        if current_dir.name == 'notebooks':
            # Ejecutándose desde notebooks/, subir un nivel
            logo_pi_path = current_dir.parent / "data" / "logo_PI_scouting_resize.jpeg"
        else:
            # Ejecutándose desde raíz del proyecto
            logo_pi_path = Path("data") / "logo_PI_scouting_resize.jpeg"
        
        print(f"🔍 DEBUG: Directorio actual: {current_dir}")
        print(f"🔍 DEBUG: Buscando logo PI Scouting en: {logo_pi_path}")
        print(f"🔍 DEBUG: Path absoluto: {logo_pi_path.absolute()}")
        print(f"🔍 DEBUG: Archivo existe: {logo_pi_path.exists()}")
        
        if logo_pi_path.exists():
            print(f"✅ DEBUG: Logo PI Scouting encontrado, intentando cargar...")
        else:
            print(f"❌ DEBUG: Logo PI Scouting NO encontrado")
            # Veamos qué hay en la carpeta data
            data_path = logo_pi_path.parent
            if data_path.exists():
                print(f"📁 DEBUG: Contenido de carpeta data:")
                for item in data_path.iterdir():
                    if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                        print(f"   - {item.name}")
            else:
                print(f"❌ DEBUG: Carpeta 'data' no existe en {data_path}")
        
        # Crear logos PI Scouting más pequeños
        if logo_pi_path.exists():
            try:
                print(f"🖼️ DEBUG: Creando imágenes del logo PI Scouting...")
                logo_pi_izq = Image(str(logo_pi_path), width=1.5*inch, height=1.5*inch, kind='proportional')
                logo_pi_der = Image(str(logo_pi_path), width=1.5*inch, height=1.5*inch, kind='proportional')
                print(f"✅ DEBUG: Logos PI Scouting creados exitosamente")
            except Exception as e:
                print(f"❌ DEBUG: Error al cargar logo PI Scouting: {e}")
                # Fallback si no se puede cargar la imagen
                logo_pi_izq = Paragraph("")
                logo_pi_der = Paragraph("")
        else:
            print(f"⚠️ DEBUG: Usando placeholders vacíos para logos PI Scouting")
            logo_pi_izq = Paragraph("")
            logo_pi_der = Paragraph("")
        
        # Crear espaciadores
        espaciador = Paragraph("")
        
        # Crear tabla horizontal con los tres logos
        print(f"📋 DEBUG: Creando tabla horizontal de logos...")
        logos_horizontales_data = [[logo_pi_izq, espaciador, logo_equipo, espaciador, logo_pi_der]]
        logos_horizontales = Table(logos_horizontales_data, 
                                  colWidths=[1.5*inch, 0.5*inch, 3*inch, 0.5*inch, 1.5*inch],
                                  rowHeights=[2.4*inch])  # Altura ligeramente aumentada para logo moderado
        logos_horizontales.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0, colors.white),  # Sin bordes
        ]))
        print(f"✅ DEBUG: Tabla horizontal de logos creada")
        
        # === SECCIÓN INFERIOR: Las tres cajas de estadísticas ===
        
        # Determinar color del porcentaje
        win_percentage = equipo_data['Win%']
        if win_percentage < 50:
            bg_color = colors.HexColor('#ffebee')
            border_color = colors.HexColor('#f44336')
            text_color = colors.HexColor('#c62828')
        else:
            bg_color = colors.HexColor('#e8f5e8')
            border_color = colors.HexColor('#4caf50')
            text_color = colors.HexColor('#2e7d32')
        
        # Estilos para las cajas en landscape (más grandes y elegantes)
        numero_caja_landscape_style = ParagraphStyle(
            'NumeroCajaLandscape',
            fontSize=42,
            textColor=colors.HexColor('#1565c0'),
            alignment=TA_CENTER,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        )
        
        numero_porcentaje_landscape_style = ParagraphStyle(
            'NumeroPorcentajeLandscape',
            fontSize=42,
            textColor=text_color,
            alignment=TA_CENTER,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        )
        
        etiqueta_caja_landscape_style = ParagraphStyle(
            'EtiquetaCajaLandscape',
            fontSize=12,
            textColor=colors.HexColor('#37474f'),
            alignment=TA_CENTER,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            leading=14,
        )
        
        # Crear las tres cajas
        cuadro1_data = [
            [Paragraph(str(equipo_data['PJ']), numero_caja_landscape_style)],
            [Paragraph("PARTIDOS<br/>JUGADOS", etiqueta_caja_landscape_style)]
        ]
        cuadro1 = Table(cuadro1_data, colWidths=[2*inch], rowHeights=[1*inch, 0.8*inch])
        cuadro1.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4fd')),
            ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#1976d2')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        cuadro2_data = [
            [Paragraph(str(equipo_data['PG']), numero_caja_landscape_style)],
            [Paragraph("PARTIDOS<br/>GANADOS", etiqueta_caja_landscape_style)]
        ]
        cuadro2 = Table(cuadro2_data, colWidths=[2*inch], rowHeights=[1*inch, 0.8*inch])
        cuadro2.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e1f5fe')),
            ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#0288d1')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        # Formatear porcentaje de victoria: sin decimal si es 100.0%
        win_percentage_texto = f"{int(win_percentage)}%" if win_percentage == 100.0 else f"{win_percentage:.1f}%"
        
        cuadro3_data = [
            [Paragraph(win_percentage_texto, numero_porcentaje_landscape_style)],
            [Paragraph("% DE<br/>VICTORIA", etiqueta_caja_landscape_style)]
        ]
        cuadro3 = Table(cuadro3_data, colWidths=[2*inch], rowHeights=[1*inch, 0.8*inch])
        cuadro3.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), bg_color),
            ('BOX', (0, 0), (-1, -1), 3, border_color),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        # === DISEÑO FINAL SIMPLIFICADO EN LANDSCAPE ===
        # Estructura simple: Título grande -> Logo -> Cajas estadísticas
        
        # Crear tabla principal con diseño vertical simple
        portada_data = [
            # Fila 1: Título del equipo (span completo)
            [titulo_equipo, "", ""],
            
            # Fila 2: Spacer
            ["", "", ""],
            
            # Fila 3: Línea horizontal con los tres logos (span completo)
            [logos_horizontales, "", ""],
            
            # Fila 4: Spacer
            ["", "", ""],
            
            # Fila 5: Spacer adicional para más separación
            ["", "", ""],
            
            # Fila 6: Las tres cajas estadísticas
            [cuadro1, cuadro2, cuadro3]
        ]
        
        portada_table = Table(portada_data, 
                             colWidths=[3.5*inch, 3.5*inch, 3.5*inch],  # Más anchos para landscape
                             rowHeights=[1*inch, 0.4*inch, 2.4*inch, 0.4*inch, 0.5*inch, 2*inch])  # Altura moderada para logo
        
        portada_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            
            # Título del equipo - span 3 columnas
            ('SPAN', (0, 0), (2, 0)),
            
            # Línea horizontal de logos - span 3 columnas  
            ('SPAN', (0, 2), (2, 2)),
            
            # Sin bordes visibles
            ('GRID', (0, 0), (-1, -1), 0, colors.white),
            
            # Padding uniforme
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        return portada_table
    
    # Crear y añadir la portada
    portada = crear_portada_landscape()
    story.append(portada)
    
    # Variable necesaria para el resto del código
    nombre_equipo = equipo_data['Equipo']
    
    # === PÁGINA 2: ÚLTIMOS PARTIDOS DEL EQUIPO RIVAL ===
    # Salto de página para la nueva página de últimos partidos
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Añadir página de últimos partidos
    elementos_partidos = crear_pagina_ultimos_partidos(nombre_equipo, liga=liga, csv_path="data/datos_completos.csv")
    story.extend(elementos_partidos)
    
    # Salto de página para continuar con más contenido y mantener landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # === PÁGINA 2: RESUMEN GENERAL DEL EQUIPO (LANDSCAPE) ===
    
    # Sin título - más espacio para contenido
    story.append(Spacer(1, 0.3*inch))
    
    # Crear estilos para las estadísticas (números un poco más grandes)
    estadistica_numero_style = ParagraphStyle(
        'EstadisticaNumero',
        parent=styles['Normal'],
        fontSize=24,  # Aumentado de 20 a 24
        textColor=colors.black,  # Negro para los números
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName='Helvetica-Bold',
    )
    
    estadistica_label_style = ParagraphStyle(
        'EstadisticaLabel',
        parent=styles['Normal'],
        fontSize=9,  # Aumentado de 8 a 9
        textColor=colors.black,  # Negro para las etiquetas
        alignment=TA_CENTER,
        spaceAfter=3,
        fontName='Helvetica-Bold',
        leading=10,  # Aumentado de 9 a 10
    )
    
    # Calcular todas las estadísticas por partido
    pts_por_partido = round(equipo_data['PTS_Favor'] / equipo_data['PJ'], 1)
    fg3_por_partido = round(equipo_data['FG3A'] / equipo_data['PJ'], 1)
    fg3_aciertos = round(equipo_data['FG3M'] / equipo_data['PJ'], 1)
    ast_por_partido = round(equipo_data['AST_Total'] / equipo_data['PJ'], 1)
    reb_por_partido = round(equipo_data['REB_Total'] / equipo_data['PJ'], 1)
    oreb_por_partido = round(equipo_data['OREB_Total'] / equipo_data['PJ'], 1)
    dreb_por_partido = round(equipo_data['DREB_Total'] / equipo_data['PJ'], 1)
    stl_por_partido = round(equipo_data['STL'] / equipo_data['PJ'], 1)
    fg_porcentaje = round(equipo_data.get('FG%', 0), 1)
    fg2_pct = round(equipo_data.get('FG2%', 0), 1)
    fg3_pct = round(equipo_data.get('FG3%', 0), 1)
    ft_pct = round(equipo_data.get('FT%', 0), 1)
    
    # Calcular posiciones en el grupo para cada estadística (si hay datos del grupo)
    posiciones = {}
    total_equipos = len(df_grupo) if df_grupo is not None else 0
    nombre_equipo = equipo_data['Equipo']
    
    if df_grupo is not None and len(df_grupo) > 1:
        # Calcular estadísticas por partido para todos los equipos
        df_grupo_stats = df_grupo.copy()
        df_grupo_stats['PTS_PJ'] = df_grupo_stats['PTS_Favor'] / df_grupo_stats['PJ']
        df_grupo_stats['FG3A_PJ'] = df_grupo_stats['FG3A'] / df_grupo_stats['PJ']
        df_grupo_stats['FG3M_PJ'] = df_grupo_stats['FG3M'] / df_grupo_stats['PJ']
        df_grupo_stats['AST_PJ'] = df_grupo_stats['AST_Total'] / df_grupo_stats['PJ']
        df_grupo_stats['REB_PJ'] = df_grupo_stats['REB_Total'] / df_grupo_stats['PJ']
        df_grupo_stats['OREB_PJ'] = df_grupo_stats['OREB_Total'] / df_grupo_stats['PJ']
        df_grupo_stats['DREB_PJ'] = df_grupo_stats['DREB_Total'] / df_grupo_stats['PJ']
        df_grupo_stats['STL_PJ'] = df_grupo_stats['STL'] / df_grupo_stats['PJ']
        
        # Calcular posiciones (1 = mejor)
        posiciones['pts'] = (df_grupo_stats['PTS_PJ'] > pts_por_partido).sum() + 1
        posiciones['fg3a'] = (df_grupo_stats['FG3A_PJ'] > fg3_por_partido).sum() + 1
        posiciones['fg3m'] = (df_grupo_stats['FG3M_PJ'] > fg3_aciertos).sum() + 1
        posiciones['ast'] = (df_grupo_stats['AST_PJ'] > ast_por_partido).sum() + 1
        posiciones['reb'] = (df_grupo_stats['REB_PJ'] > reb_por_partido).sum() + 1
        posiciones['oreb'] = (df_grupo_stats['OREB_PJ'] > oreb_por_partido).sum() + 1
        posiciones['dreb'] = (df_grupo_stats['DREB_PJ'] > dreb_por_partido).sum() + 1
        posiciones['stl'] = (df_grupo_stats['STL_PJ'] > stl_por_partido).sum() + 1
        posiciones['fg_pct'] = (df_grupo_stats['FG%'] > fg_porcentaje).sum() + 1
        posiciones['fg2_pct'] = (df_grupo_stats['FG2%'] > fg2_pct).sum() + 1
        posiciones['fg3_pct'] = (df_grupo_stats['FG3%'] > fg3_pct).sum() + 1
        posiciones['ft_pct'] = (df_grupo_stats['FT%'] > ft_pct).sum() + 1
    
    # Función para crear caja estadística con colores por cuantiles y ranking - CAJAS UN POCO MÁS GRANDES
    def crear_caja_estadistica(valor, etiqueta, posicion=None, total_equipos=None, ancho=1.4):  # Aumentado de 1.1 a 1.4
        # Si no se proporciona posición, usar colores por defecto
        if posicion is None or total_equipos is None or total_equipos <= 1:
            color_fondo = colors.HexColor('#e8f4fd')  # Azul claro por defecto
            color_borde = colors.HexColor('#1976d2')  # Azul por defecto
            ranking_text = ""
        else:
            # Calcular cuantiles basados en el total de equipos
            cuantil_33 = int(total_equipos * 0.33) + 1  # 33% superior
            cuantil_66 = int(total_equipos * 0.66) + 1  # 66% superior
            
            # Sistema de colores por cuantiles (verde=bueno, amarillo=medio, rojo=malo)
            if posicion <= cuantil_33:
                # TOP 33% - VERDE
                color_fondo = colors.HexColor('#d4edda')  # Verde claro
                color_borde = colors.HexColor('#28a745')  # Verde oscuro
            elif posicion <= cuantil_66:
                # MEDIO 33%-66% - AMARILLO
                color_fondo = colors.HexColor('#fff3cd')  # Amarillo claro
                color_borde = colors.HexColor('#ffc107')  # Amarillo oscuro
            else:
                # BAJO 66%-100% - ROJO
                color_fondo = colors.HexColor('#f8d7da')  # Rojo claro
                color_borde = colors.HexColor('#dc3545')  # Rojo oscuro
            
            # Texto del ranking
            ranking_text = f"{posicion}º de {total_equipos}"
        
        # Estilo para el ranking (gris)
        ranking_style = ParagraphStyle(
            'RankingStyle',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=8,
        )
        
        # Crear filas: valor, etiqueta, ranking (si existe) - UN POCO MÁS ALTAS
        if ranking_text:
            data = [
                [Paragraph(str(valor), estadistica_numero_style)],
                [Paragraph(etiqueta, estadistica_label_style)],
                [Paragraph(ranking_text, ranking_style)]
            ]
            tabla = Table(data, colWidths=[ancho*inch], rowHeights=[0.5*inch, 0.4*inch, 0.25*inch])  # Aumentado moderadamente
        else:
            data = [
                [Paragraph(str(valor), estadistica_numero_style)],
                [Paragraph(etiqueta, estadistica_label_style)]
            ]
            tabla = Table(data, colWidths=[ancho*inch], rowHeights=[0.6*inch, 0.45*inch])  # Aumentado moderadamente
        
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (0, -1), color_fondo),
            ('BOX', (0, 0), (-1, -1), 1.5, color_borde),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        return tabla
    
    # === LAYOUT LANDSCAPE OPTIMIZADO ===
    # Crear títulos más compactos para landscape
    titulo_ofensivo_style = ParagraphStyle(
        'TituloOfensivo',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName='Helvetica-Bold',
    )
    
    # === SECCIÓN 1: ESTADÍSTICAS OFENSIVAS ===
    story.append(Paragraph("ESTADÍSTICAS OFENSIVAS", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))  # Espacio entre título y cajas
    
    # Estadísticas ofensivas en una fila con más espacio para landscape
    ofensivas = [
        crear_caja_estadistica(pts_por_partido, "PUNTOS<br/>POR PARTIDO", 
                             posiciones.get('pts'), total_equipos),
        crear_caja_estadistica(ast_por_partido, "ASISTENCIAS<br/>POR PARTIDO", 
                             posiciones.get('ast'), total_equipos),
        crear_caja_estadistica(fg3_aciertos, "TRIPLES<br/>ANOTADOS", 
                             posiciones.get('fg3m'), total_equipos),
        crear_caja_estadistica(fg3_por_partido, "TRIPLES<br/>INTENTADOS", 
                             posiciones.get('fg3a'), total_equipos)
    ]
    
    tabla_ofensivas = Table([ofensivas], colWidths=[2.2*inch]*4)  # Aumentado de 2.0 a 2.2 para cajas un poco más grandes
    tabla_ofensivas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_ofensivas.hAlign = 'CENTER'
    story.append(tabla_ofensivas)
    story.append(Spacer(1, 0.2*inch))  # Reducido para landscape
    
    # === SECCIÓN 2: ESTADÍSTICAS DEFENSIVAS ===
    story.append(Paragraph("ESTADÍSTICAS DEFENSIVAS", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))  # Espacio entre título y cajas
    
    # Estadísticas defensivas en una fila
    defensivas = [
        crear_caja_estadistica(reb_por_partido, "REBOTES<br/>TOTALES", 
                             posiciones.get('reb'), total_equipos),
        crear_caja_estadistica(oreb_por_partido, "REBOTES<br/>OFENSIVOS", 
                             posiciones.get('oreb'), total_equipos),
        crear_caja_estadistica(dreb_por_partido, "REBOTES<br/>DEFENSIVOS", 
                             posiciones.get('dreb'), total_equipos),
        crear_caja_estadistica(stl_por_partido, "ROBOS<br/>POR PARTIDO", 
                             posiciones.get('stl'), total_equipos)
    ]
    
    tabla_defensivas = Table([defensivas], colWidths=[2.2*inch]*4)  # Aumentado de 2.0 a 2.2 para cajas un poco más grandes
    tabla_defensivas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_defensivas.hAlign = 'CENTER'
    story.append(tabla_defensivas)
    story.append(Spacer(1, 0.2*inch))  # Reducido para landscape
    
    # === SECCIÓN 3: PORCENTAJES DE ACIERTO ===
    story.append(Paragraph("PORCENTAJES DE ACIERTO", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))  # Espacio entre título y cajas
    
    # Porcentajes en una fila
    porcentajes = [
        crear_caja_estadistica(f"{fg_porcentaje}%", "% TIROS<br/>DE CAMPO", 
                             posiciones.get('fg_pct'), total_equipos),
        crear_caja_estadistica(f"{fg2_pct}%", "% TIROS<br/>DE 2", 
                             posiciones.get('fg2_pct'), total_equipos),
        crear_caja_estadistica(f"{fg3_pct}%", "% TIROS<br/>DE 3", 
                             posiciones.get('fg3_pct'), total_equipos),
        crear_caja_estadistica(f"{ft_pct}%", "% TIROS<br/>LIBRES", 
                             posiciones.get('ft_pct'), total_equipos)
    ]
    
    tabla_porcentajes = Table([porcentajes], colWidths=[2.2*inch]*4)  # Aumentado de 2.0 a 2.2 para cajas un poco más grandes
    tabla_porcentajes.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_porcentajes.hAlign = 'CENTER'
    story.append(tabla_porcentajes)
    
    # ============== TERCERA PÁGINA: COMPARATIVA (LANDSCAPE) ==============
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Título de la tercera página (más corto y compacto)
    titulo_comparativa = Paragraph("COMPARATIVA", titulo_comparativa_style)
    story.append(titulo_comparativa)
    story.append(Spacer(1, 12))  # Reducido de 25 a 12
    
    # Calcular rankings y posiciones para nuestro equipo
    df_grupo_sorted_ortg = df_grupo.sort_values('ORtg', ascending=False).reset_index(drop=True)
    df_grupo_sorted_drtg = df_grupo.sort_values('DRtg', ascending=True).reset_index(drop=True)  # Menor es mejor en DRtg
    df_grupo_sorted_ritmo = df_grupo.sort_values('Ritmo', ascending=False).reset_index(drop=True)
    
    # Encontrar posiciones de nuestro equipo con verificación de seguridad
    try:
        mask_ortg = df_grupo_sorted_ortg['Equipo'] == nombre_equipo
        if mask_ortg.any():
            pos_ortg = df_grupo_sorted_ortg[mask_ortg].index[0] + 1
        else:
            print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking ORtg")
            pos_ortg = len(df_grupo_sorted_ortg)  # Posición por defecto
    except (IndexError, KeyError):
        pos_ortg = len(df_grupo_sorted_ortg)
        
    try:
        mask_drtg = df_grupo_sorted_drtg['Equipo'] == nombre_equipo
        if mask_drtg.any():
            pos_drtg = df_grupo_sorted_drtg[mask_drtg].index[0] + 1
        else:
            print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking DRtg")
            pos_drtg = len(df_grupo_sorted_drtg)
    except (IndexError, KeyError):
        pos_drtg = len(df_grupo_sorted_drtg)
        
    try:
        mask_ritmo = df_grupo_sorted_ritmo['Equipo'] == nombre_equipo
        if mask_ritmo.any():
            pos_ritmo = df_grupo_sorted_ritmo[mask_ritmo].index[0] + 1
        else:
            print(f"Advertencia: Equipo '{nombre_equipo}' no encontrado en ranking Ritmo")
            pos_ritmo = len(df_grupo_sorted_ritmo)
    except (IndexError, KeyError):
        pos_ritmo = len(df_grupo_sorted_ritmo)
    
    # Obtener valores de nuestro equipo directamente de equipo_data
    nuestro_ortg = equipo_data['ORtg']
    nuestro_drtg = equipo_data['DRtg'] 
    nuestro_ritmo = equipo_data['Ritmo']
    
    # Función para crear caja de comparativa con altura uniforme
    def crear_caja_comparativa(titulo, valor, posicion, total_equipos, es_mejor_mayor=True):
        # Calcular cuantiles basados en el total de equipos
        cuantil_33 = int(total_equipos * 0.33) + 1  # 33% superior
        cuantil_66 = int(total_equipos * 0.66) + 1  # 66% superior
        
        # Sistema de colores por cuantiles (verde=bueno, amarillo=medio, rojo=malo)
        if posicion <= cuantil_33:
            # TOP 33% - VERDE
            color_fondo = colors.HexColor('#d4edda')  # Verde claro
            color_borde = colors.HexColor('#28a745')  # Verde oscuro
        elif posicion <= cuantil_66:
            # MEDIO 33%-66% - AMARILLO
            color_fondo = colors.HexColor('#fff3cd')  # Amarillo claro
            color_borde = colors.HexColor('#ffc107')  # Amarillo oscuro
        else:
            # BAJO 66%-100% - ROJO
            color_fondo = colors.HexColor('#f8d7da')  # Rojo claro
            color_borde = colors.HexColor('#dc3545')  # Rojo oscuro
        
        posicion_text = f"{posicion}º de {total_equipos}"
        
        # Estilos con altura optimizada para números grandes - CAJAS UN POCO MÁS GRANDES
        titulo_style = ParagraphStyle('', fontSize=9, alignment=1, textColor=colors.black, 
                                    fontName='Helvetica-Bold', leading=10)  # Aumentado de 8 a 9
        valor_style = ParagraphStyle('', fontSize=24, alignment=1, textColor=colors.black, 
                                    fontName='Helvetica-Bold', leading=26, spaceAfter=6)  # Aumentado de 20 a 24
        pos_style = ParagraphStyle('', fontSize=8, alignment=1, textColor=colors.HexColor('#666666'), 
                                leading=9)  # Aumentado de 7 a 8
        
        data = [
            [Paragraph(titulo, titulo_style)],
            [Paragraph(f"{valor:.1f}", valor_style)],
            [Paragraph(posicion_text, pos_style)]
        ]
        
        # Altura fija para todas las cajas - UN POCO MÁS GRANDES
        tabla = Table(data, colWidths=[1.5*inch], rowHeights=[0.3*inch, 0.5*inch, 0.25*inch])  # Aumentado ancho y alturas
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
            ('BOX', (0, 0), (-1, -1), 1.5, color_borde),  # Borde exterior más fino
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        return tabla
    
    # ============== DISEÑO LANDSCAPE: TABLAS A LA IZQUIERDA, CAJAS A LA DERECHA ==============
    total_equipos = len(df_grupo)
    
    # Crear cajas individuales (más compactas para landscape)
    caja_ortg = crear_caja_comparativa("OFFENSIVE RATING", nuestro_ortg, pos_ortg, total_equipos, True)
    caja_drtg = crear_caja_comparativa("DEFENSIVE RATING", nuestro_drtg, pos_drtg, total_equipos, False)
    caja_ritmo = crear_caja_comparativa("RITMO", nuestro_ritmo, pos_ritmo, total_equipos, True)

    
    # Función para crear ranking con tabla simple en negro
    def crear_ranking_premium(titulo, df_sorted, columna, nombre_equipo, color_principal, color_secundario):
        # Función para acortar nombres largos
        def acortar_nombre(nombre, max_chars=22):
            if len(nombre) <= max_chars:
                return nombre
            palabras = nombre.split()
            if len(palabras) > 1:
                iniciales = [p[0] + '.' for p in palabras[:-1]]
                resultado = ' '.join(iniciales + [palabras[-1]])
                if len(resultado) <= max_chars:
                    return resultado
                return resultado[:max_chars-2] + '..'
            return nombre[:max_chars-2] + '..'
        
        # Crear la tabla con los datos
        datos_ranking = []
        
        # Header con color
        header_style = ParagraphStyle(
            'HeaderSimple',
            fontSize=11,
            textColor=colors.white,
            alignment=1,
            fontName='Helvetica-Bold',
            leading=14
        )
        
        datos_ranking.append([Paragraph(titulo, header_style), ""])
        
        # Definir colores consistentes con las cajas de arriba - CAMBIADO A GRIS UNIFORME
        if "OFFENSIVE" in titulo:
            color_header = colors.HexColor("#4a5568")  # Gris igual que página de rankings
        elif "DEFENSIVE" in titulo:
            color_header = colors.HexColor("#4a5568")  # Gris igual que página de rankings
        else:
            color_header = colors.HexColor("#4a5568")  # Gris igual que página de rankings (Ritmo)
        
        # Determinar si necesitamos formato compacto
        num_equipos_total = len(df_sorted)
        usar_compacto = num_equipos_total > 14
        
        # Añadir filas de equipos
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            equipo_nombre = row['Equipo']
            equipo_nombre_normalizado = normalizar_nombre_equipo(equipo_nombre)  # ✅ APLICAR NORMALIZACIÓN
            valor = row[columna]
            ranking_pos = i + 1  # Posición en el ranking (1, 2, 3, etc.)
            
            nombre_mostrar = acortar_nombre(equipo_nombre_normalizado, 24)  # ✅ USAR NOMBRE NORMALIZADO
            es_nuestro = equipo_nombre == nombre_equipo  # ✅ COMPARAR CON NOMBRE ORIGINAL
            
            # Formatear número usando la función anti-salto de línea
            valor_formateado = formatear_numero_sin_salto(valor)
            valor_texto = f"<b>{valor_formateado}</b>"
            
            # Formatear nombre con ranking en bold - NOMBRE DEL EQUIPO SELECCIONADO EN NEGRITA
            if es_nuestro:
                # Equipo seleccionado: nombre completo en negrita
                nombre_con_ranking = f"<b>{ranking_pos}. {nombre_mostrar}</b>"
            else:
                # Otros equipos: solo el número en negrita
                nombre_con_ranking = f"<b>{ranking_pos}.</b> {nombre_mostrar}"
            
            # Estilos con color para el equipo seleccionado - AJUSTAR SEGÚN COMPACTO O NORMAL
            if es_nuestro:
                color_texto = color_header
                if usar_compacto:
                    nombre_style = ParagraphStyle('', fontSize=9, textColor=color_texto, 
                                                alignment=0, fontName='Helvetica', leading=10)
                    valor_style = ParagraphStyle('', fontSize=10, textColor=color_texto, 
                                            alignment=2, fontName='Helvetica', leading=10)
                else:
                    nombre_style = ParagraphStyle('', fontSize=10, textColor=color_texto, 
                                                alignment=0, fontName='Helvetica', leading=12)
                    valor_style = ParagraphStyle('', fontSize=11, textColor=color_texto, 
                                            alignment=2, fontName='Helvetica', leading=12)
            else:
                if usar_compacto:
                    nombre_style = ParagraphStyle('', fontSize=8.5, textColor=colors.black, 
                                                alignment=0, fontName='Helvetica', leading=10)
                    valor_style = ParagraphStyle('', fontSize=9.5, textColor=colors.black, 
                                            alignment=2, fontName='Helvetica', leading=10)
                else:
                    nombre_style = ParagraphStyle('', fontSize=9.5, textColor=colors.black, 
                                                alignment=0, fontName='Helvetica', leading=12)
                    valor_style = ParagraphStyle('', fontSize=10.5, textColor=colors.black, 
                                            alignment=2, fontName='Helvetica', leading=12)
            
            datos_ranking.append([
                Paragraph(nombre_con_ranking, nombre_style),
                Paragraph(valor_texto, valor_style)
            ])
        
        # Crear tabla con diseño mejorado - Más espacio para ranking
        # 📏 COMPARATIVA: Ajustar altura según número de equipos
        num_filas = len(datos_ranking)
        num_equipos = num_filas - 1  # Restar 1 por el header
        
        # Si hay más de 14 equipos, usar filas compactas para evitar overflow
        if num_equipos > 14:
            row_heights = [30] + [16] * num_equipos  # Header alto, filas compactas
        else:
            row_heights = [30] + [20] * num_equipos  # Header alto, filas normales
        
        tabla = Table(datos_ranking, colWidths=[1.6*inch, 0.6*inch], rowHeights=row_heights, splitByRow=True)
        
        # Estilos con colores consistentes
        estilos = [
            # Header con color
            ('SPAN', (0, 0), (1, 0)),  # Unir celdas del header
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), color_header),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Contenido - ajustar padding según si es compacto o normal
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 1), (-1, -1), 6),
            ('RIGHTPADDING', (0, 1), (-1, -1), 6),
        ]
        
        # Añadir padding según formato
        if num_equipos > 14:
            estilos.extend([
                ('TOPPADDING', (0, 1), (-1, -1), 2),    # Compacto
                ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
            ])
        else:
            estilos.extend([
                ('TOPPADDING', (0, 1), (-1, -1), 5),    # Normal
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ])
        
        estilos.extend([
            # Bordes
            ('BOX', (0, 0), (-1, -1), 1, color_header),
            ('LINEBELOW', (0, 0), (-1, 0), 1, color_header),
        ])
        
        # Alternar colores de fondo para las filas y colores para equipo seleccionado
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            equipo_nombre = row['Equipo']
            valor = row[columna]
            
            # Verificar si es número de 3 cifras con decimal (como 104.4)
            es_numero_3_cifras_decimal = (isinstance(valor, (int, float)) and 
                                        valor >= 100 and valor < 1000 and 
                                        valor != int(valor))  # Tiene decimal
            
            if equipo_nombre == nombre_equipo:
                estilos_equipo = [
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor("#ffe6e6")),  # Fondo rojito claro para equipo seleccionado
                    ('LINEBELOW', (0, i), (-1, i), 0.5, color_header),
                ]
                
                # Solo aplicar RIGHTPADDING reducido si es número de 3 cifras con decimal
                if es_numero_3_cifras_decimal:
                    estilos_equipo.append(('RIGHTPADDING', (0, i), (0, i), 2))  # Reducir espacio solo para 3 cifras con decimal
                
                estilos.extend(estilos_equipo)
            else:
                if i % 2 == 0:
                    estilos.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8f9fa")))
                # Líneas horizontales entre filas
                estilos.append(('LINEBELOW', (0, i), (-1, i), 0.25, color_header))
        
        tabla.setStyle(TableStyle(estilos))
        
        # Devolver la tabla directamente sin contenedor adicional
        return tabla
    
    # Crear los tres rankings con diseño premium y colores modernos
    ranking_ortg = crear_ranking_premium(
        "🎯 OFFENSIVE RATING", 
        df_grupo_sorted_ortg, 'ORtg', nombre_equipo,
        colors.HexColor('#4a5568'),  # Gris oscuro uniforme
        colors.HexColor('#4a5568')   # Gris oscuro uniforme
    )
    
    ranking_drtg = crear_ranking_premium(
        "🛡️ DEFENSIVE RATING", 
        df_grupo_sorted_drtg, 'DRtg', nombre_equipo,
        colors.HexColor('#4a5568'),  # Gris oscuro uniforme
        colors.HexColor('#4a5568')   # Gris oscuro uniforme
    )
    
    ranking_ritmo = crear_ranking_premium(
        "⚡ RITMO", 
        df_grupo_sorted_ritmo, 'Ritmo', nombre_equipo,
        colors.HexColor('#4a5568'),  # Gris oscuro uniforme
        colors.HexColor('#4a5568')   # Gris oscuro uniforme
    )
    
    # ============== NUEVO LAYOUT LANDSCAPE - ESPACIADO COMO 4 TABLAS ==============
    # Crear columna de cajas (lado derecho)
    columna_cajas_data = [
        [caja_ortg],
        [caja_drtg], 
        [caja_ritmo]
    ]
    
    columna_cajas = Table(columna_cajas_data, colWidths=[2.0*inch], rowHeights=[1.7*inch, 1.7*inch, 1.7*inch])  # Aumentado ancho y alto para cajas más grandes
    columna_cajas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    # Usar los mismos separadores que en rankings de equipos (4 tablas)
    separador_tablas = Table([[""],], colWidths=[0.4*inch])  # Mismo separador que rankings
    separador_tablas.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
    
    # Organizar las 3 tablas con espaciado de 4 tablas + columna de cajas
    # Usamos el mismo ancho de tabla que en rankings (2.3*inch) y espaciado (0.4*inch)
    layout_landscape_data = [[
        ranking_ortg, 
        separador_tablas, 
        ranking_drtg, 
        separador_tablas, 
        ranking_ritmo,
        separador_tablas,
        columna_cajas
    ]]
    
    # Usar los mismos tamaños que en la página de rankings para 4 tablas
    # ancho_tabla = 2.3*inch, espacio_entre = 0.4*inch (como en línea 411 del código)
    layout_landscape = Table(layout_landscape_data, 
                           colWidths=[2.3*inch, 0.4*inch, 2.3*inch, 0.4*inch, 2.3*inch, 0.4*inch, 2.0*inch])  # Aumentado última columna de 1.8 a 2.0
    layout_landscape.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # ✅ CENTRAR VERTICALMENTE: Cambiar de 'TOP' a 'MIDDLE' para alinear cajas con tablas
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    
    layout_landscape.hAlign = 'CENTER'
    story.append(layout_landscape)
    
    # Añadir explicaciones compactas al final
    story.append(Spacer(1, 10))
    
    # Estilo para las explicaciones (más compacto)
    explicacion_style = ParagraphStyle(
        'ExplicacionStyle',
        fontSize=6,
        textColor=colors.HexColor('#666666'),
        alignment=1,  # Centrado
        fontName='Helvetica',
        leading=7,
        spaceAfter=1
    )
    
    # Crear las explicaciones centradas
    explicaciones = [
        "* OFFENSIVE RATING: Puntos anotados por cada 100 posesiones | * DEFENSIVE RATING: Puntos permitidos por cada 100 posesiones | * RITMO: Número promedio de posesiones por partido"
    ]
    
    for explicacion in explicaciones:
        story.append(Paragraph(explicacion, explicacion_style))
    
    # ============== NUEVA SECCIÓN: ESTADÍSTICAS AVANZADAS (EQUIPO) ==============
    story.append(NextPageTemplate('landscape'))  # Asegurar plantilla con watermark
    story.append(PageBreak())
    
    # Sin título general - empezamos directamente con el primer subtítulo
    story.append(Spacer(1, 0.3*inch))
    
    # Función para calcular métricas avanzadas de forma segura
    def calc_safe(formula_fn, default="—"):
        try:
            result = formula_fn()
            if result is None or (isinstance(result, float) and (np.isnan(result) or np.isinf(result))):
                return default
            return result
        except (ZeroDivisionError, TypeError, KeyError, AttributeError, Exception):
            return default
    
    # Obtener datos del equipo y oponentes para cálculos
    try:
        # Datos del equipo seleccionado (TOTALES de la temporada)
        fgm = float(equipo_data.get('FGM', 0) or 0)
        fga = float(equipo_data.get('FGA', 0) or 0)
        fg3m = float(equipo_data.get('FG3M', 0) or 0)
        fg3a = float(equipo_data.get('FG3A', 0) or 0)
        ftm = float(equipo_data.get('FTM', 0) or 0)
        fta = float(equipo_data.get('FTA', 0) or 0)
        pts = float(equipo_data.get('PTS_Favor', 0) or 0)
        orb = float(equipo_data.get('OREB_Total', 0) or 0)
        drb = float(equipo_data.get('DREB_Total', 0) or 0)
        ast = float(equipo_data.get('AST_Total', 0) or 0)
        stl = float(equipo_data.get('STL', 0) or 0)
        blk = float(equipo_data.get('BLK', 0) or 0)
        # TOV puede estar como TO_Total o TO
        tov = float(equipo_data.get('TO_Total', equipo_data.get('TO', 0)) or 0)
        pf = float(equipo_data.get('PF', 0) or 0)
        pj = float(equipo_data.get('PJ', 1) or 1)
        ortg = float(equipo_data.get('ORtg', 0) or 0)
        drtg = float(equipo_data.get('DRtg', 0) or 0)
        
        # Debug: Imprimir valores clave para verificar
        print(f"\n📊 DEBUG - Valores para estadísticas avanzadas:")
        print(f"   Equipo: {nombre_equipo}")
        print(f"   Partidos jugados (PJ): {pj}")
        print(f"   Puntos totales (PTS): {pts}")
        print(f"   Tiros campo (FGM/FGA): {fgm}/{fga}")
        print(f"   Triples (FG3M/FG3A): {fg3m}/{fg3a}")
        print(f"   Tiros libres (FTM/FTA): {ftm}/{fta}")
        print(f"   Pérdidas (TOV): {tov}")
        print(f"   Asistencias (AST): {ast}")
        print(f"   Rebotes (ORB/DRB): {orb}/{drb}")
        
        # Promedios de oponentes (sumar todos los oponentes y promediar)
        opp_orb = float(df_grupo[df_grupo['Equipo'] != nombre_equipo]['OREB_Total'].sum() / max(len(df_grupo) - 1, 1))
        opp_drb = float(df_grupo[df_grupo['Equipo'] != nombre_equipo]['DREB_Total'].sum() / max(len(df_grupo) - 1, 1))
        
    except Exception as e:
        print(f"⚠️ Error obteniendo datos para estadísticas avanzadas: {e}")
        import traceback
        traceback.print_exc()
        # Valores por defecto
        fgm = fga = fg3m = fg3a = ftm = fta = pts = 0.0
        orb = drb = ast = stl = blk = tov = pf = pj = 1.0
        ortg = drtg = opp_orb = opp_drb = 0.0
    
    # Calcular las 12 métricas avanzadas PARA TODOS LOS EQUIPOS (para calcular rankings)
    df_grupo_avanzadas = df_grupo.copy()
    total_equipos = len(df_grupo)
    
    # Calcular cada métrica para todos los equipos
    for idx, equipo_row in df_grupo_avanzadas.iterrows():
        eq_fgm = float(equipo_row.get('FGM', 0) or 0)
        eq_fga = float(equipo_row.get('FGA', 0) or 0)
        eq_fg3m = float(equipo_row.get('FG3M', 0) or 0)
        eq_fg3a = float(equipo_row.get('FG3A', 0) or 0)
        eq_ftm = float(equipo_row.get('FTM', 0) or 0)
        eq_fta = float(equipo_row.get('FTA', 0) or 0)
        eq_pts = float(equipo_row.get('PTS_Favor', 0) or 0)
        eq_orb = float(equipo_row.get('OREB_Total', 0) or 0)
        eq_drb = float(equipo_row.get('DREB_Total', 0) or 0)
        eq_ast = float(equipo_row.get('AST_Total', 0) or 0)
        eq_tov = float(equipo_row.get('TO_Total', equipo_row.get('TO', 0)) or 0)
        eq_ortg = float(equipo_row.get('ORtg', 0) or 0)
        eq_drtg = float(equipo_row.get('DRtg', 0) or 0)
        eq_pj = float(equipo_row.get('PJ', 1) or 1)
        
        # Calcular métricas
        df_grupo_avanzadas.loc[idx, 'eFG%'] = ((eq_fgm + 0.5 * eq_fg3m) / eq_fga * 100) if eq_fga > 0 else 0
        df_grupo_avanzadas.loc[idx, 'TS%'] = (eq_pts / (2 * (eq_fga + 0.44 * eq_fta)) * 100) if (eq_fga + 0.44 * eq_fta) > 0 else 0
        df_grupo_avanzadas.loc[idx, '3PAr'] = (eq_fg3a / eq_fga) if eq_fga > 0 else 0
        df_grupo_avanzadas.loc[idx, 'FTr'] = (eq_fta / eq_fga) if eq_fga > 0 else 0
        df_grupo_avanzadas.loc[idx, 'TOV%'] = (eq_tov / (eq_fga + 0.44 * eq_fta + eq_tov) * 100) if (eq_fga + 0.44 * eq_fta + eq_tov) > 0 else 0
        df_grupo_avanzadas.loc[idx, 'AST/TOV'] = (eq_ast / eq_tov) if eq_tov > 0 else 0
        df_grupo_avanzadas.loc[idx, 'ORB%'] = (eq_orb / (eq_orb + opp_drb) * 100) if (eq_orb + opp_drb) > 0 else 0
        df_grupo_avanzadas.loc[idx, 'DRB%'] = (eq_drb / (eq_drb + opp_orb) * 100) if (eq_drb + opp_orb) > 0 else 0
        posesiones_eq = (eq_fga + 0.44 * eq_fta + eq_tov - eq_orb)
        df_grupo_avanzadas.loc[idx, 'PPP'] = (eq_pts / posesiones_eq) if posesiones_eq > 0 else 0
        df_grupo_avanzadas.loc[idx, 'NetRtg'] = (eq_ortg - eq_drtg) if eq_ortg and eq_drtg else 0
        # Nuevas métricas: AST% y FT Efficiency
        df_grupo_avanzadas.loc[idx, 'AST%'] = (eq_ast / eq_fgm * 100) if eq_fgm > 0 else 0
        df_grupo_avanzadas.loc[idx, 'FT_Eff'] = (eq_ftm / eq_fga) if eq_fga > 0 else 0
    
    # Calcular rankings (posición de nuestro equipo)
    posiciones_avanzadas = {}
    
    # Para métricas donde MAYOR es MEJOR
    metricas_mayor_mejor = ['eFG%', 'TS%', '3PAr', 'FTr', 'AST/TOV', 'ORB%', 'DRB%', 'PPP', 'NetRtg', 'AST%', 'FT_Eff']
    for metrica in metricas_mayor_mejor:
        if metrica in df_grupo_avanzadas.columns:
            valor_nuestro = df_grupo_avanzadas[df_grupo_avanzadas['Equipo'] == nombre_equipo][metrica].values[0] if len(df_grupo_avanzadas[df_grupo_avanzadas['Equipo'] == nombre_equipo]) > 0 else 0
            posiciones_avanzadas[metrica] = (df_grupo_avanzadas[metrica] > valor_nuestro).sum() + 1
    
    # Para TOV% MENOR es MEJOR
    if 'TOV%' in df_grupo_avanzadas.columns:
        valor_nuestro_tov = df_grupo_avanzadas[df_grupo_avanzadas['Equipo'] == nombre_equipo]['TOV%'].values[0] if len(df_grupo_avanzadas[df_grupo_avanzadas['Equipo'] == nombre_equipo]) > 0 else 0
        posiciones_avanzadas['TOV%'] = (df_grupo_avanzadas['TOV%'] < valor_nuestro_tov).sum() + 1
    
    # Calcular las 12 métricas para nuestro equipo (valores ya calculados antes)
    # 1. eFG% (Porcentaje de tiro efectivo)
    efg = calc_safe(lambda: ((fgm + 0.5 * fg3m) / fga * 100) if fga > 0 else None)
    efg_texto = f"{efg:.1f}%" if efg != "—" else "—"
    
    # 2. TS% (Porcentaje real de tiro)
    ts = calc_safe(lambda: (pts / (2 * (fga + 0.44 * fta)) * 100) if (fga + 0.44 * fta) > 0 else None)
    ts_texto = f"{ts:.1f}%" if ts != "—" else "—"
    
    # 3. 3PAr (Tres puntos intentados / tiros campo)
    three_par = calc_safe(lambda: (fg3a / fga) if fga > 0 else None)
    three_par_texto = f"{three_par:.2f}" if three_par != "—" else "—"
    
    # 4. FTr (Tiros libres por tiro de campo)
    ftr = calc_safe(lambda: (fta / fga) if fga > 0 else None)
    ftr_texto = f"{ftr:.2f}" if ftr != "—" else "—"
    
    # 5. TOV% (Porcentaje de posesiones perdidas)
    tov_pct = calc_safe(lambda: (tov / (fga + 0.44 * fta + tov) * 100) if (fga + 0.44 * fta + tov) > 0 else None)
    tov_pct_texto = f"{tov_pct:.1f}%" if tov_pct != "—" else "—"
    
    # 6. AST/TOV (Asistencias por pérdida) - CORREGIDO
    ast_tov = calc_safe(lambda: (ast / tov) if tov > 0 else None)
    ast_tov_texto = f"{ast_tov:.2f}" if ast_tov != "—" else "—"
    
    # 7. ORB% (Porcentaje de rebote ofensivo)
    orb_pct = calc_safe(lambda: (orb / (orb + opp_drb) * 100) if (orb + opp_drb) > 0 else None)
    orb_pct_texto = f"{orb_pct:.1f}%" if orb_pct != "—" else "—"
    
    # 8. DRB% (Porcentaje de rebote defensivo)
    drb_pct = calc_safe(lambda: (drb / (drb + opp_orb) * 100) if (drb + opp_orb) > 0 else None)
    drb_pct_texto = f"{drb_pct:.1f}%" if drb_pct != "—" else "—"
    
    # 9. PPP (Puntos por posesión)
    posesiones = calc_safe(lambda: (fga + 0.44 * fta + tov - orb))
    ppp = calc_safe(lambda: (pts / posesiones) if posesiones != "—" and posesiones > 0 else None)
    ppp_texto = f"{ppp:.2f}" if ppp != "—" else "—"
    
    # 10. Net Rating
    net_rating = calc_safe(lambda: (ortg - drtg) if ortg and drtg else None)
    if net_rating != "—":
        signo = "+" if net_rating > 0 else ""
        net_rating_texto = f"{signo}{net_rating:.1f}"
    else:
        net_rating_texto = "—"
    
    # 11. AST% (Tasa de asistencias - colectividad ofensiva)
    ast_pct = calc_safe(lambda: (ast / fgm * 100) if fgm > 0 else None)
    ast_pct_texto = f"{ast_pct:.1f}%" if ast_pct != "—" else "—"
    
    # 12. FT Efficiency (Eficiencia de tiros libres)
    ft_efficiency = calc_safe(lambda: (ftm / fga) if fga > 0 else None)
    ft_efficiency_texto = f"{ft_efficiency:.2f}" if ft_efficiency != "—" else "—"
    
    # === FILA 1: EFICIENCIA OFENSIVA ===
    story.append(Paragraph("EFICIENCIA OFENSIVA (AVANZADA)", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))
    fila1_avanzadas = [
        crear_caja_estadistica(efg_texto, "eFG%<br/>Tiro efectivo", posiciones_avanzadas.get('eFG%'), total_equipos),
        crear_caja_estadistica(ts_texto, "TS%<br/>Eficiencia total", posiciones_avanzadas.get('TS%'), total_equipos),
        crear_caja_estadistica(three_par_texto, "3PAr<br/>% volumen de 3", posiciones_avanzadas.get('3PAr'), total_equipos),
        crear_caja_estadistica(ftr_texto, "FTr<br/>Agresividad", posiciones_avanzadas.get('FTr'), total_equipos)
    ]
    
    tabla_fila1_avanzadas = Table([fila1_avanzadas], colWidths=[2.2*inch]*4)
    tabla_fila1_avanzadas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_fila1_avanzadas.hAlign = 'CENTER'
    story.append(tabla_fila1_avanzadas)
    story.append(Spacer(1, 0.2*inch))
    
    # === FILA 2: CONTROL Y REBOTE ===
    story.append(Paragraph("CONTROL Y REBOTE (AVANZADO)", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))
    fila2_avanzadas = [
        crear_caja_estadistica(tov_pct_texto, "TOV%<br/>Pérdidas/posesión", posiciones_avanzadas.get('TOV%'), total_equipos),
        crear_caja_estadistica(ast_tov_texto, "AST/TOV<br/>Fluidez ofensiva", posiciones_avanzadas.get('AST/TOV'), total_equipos),
        crear_caja_estadistica(orb_pct_texto, "ORB%<br/>2ª oportunidades", posiciones_avanzadas.get('ORB%'), total_equipos),
        crear_caja_estadistica(drb_pct_texto, "DRB%<br/>Cerrar el aro", posiciones_avanzadas.get('DRB%'), total_equipos)
    ]
    
    tabla_fila2_avanzadas = Table([fila2_avanzadas], colWidths=[2.2*inch]*4)
    tabla_fila2_avanzadas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_fila2_avanzadas.hAlign = 'CENTER'
    story.append(tabla_fila2_avanzadas)
    story.append(Spacer(1, 0.2*inch))
    
    # === FILA 3: EFECTIVIDAD GLOBAL ===
    story.append(Paragraph("EFECTIVIDAD GLOBAL (AVANZADA)", titulo_ofensivo_style))
    story.append(Spacer(1, 0.15*inch))
    fila3_avanzadas = [
        crear_caja_estadistica(ppp_texto, "PPP<br/>Eficiencia real", posiciones_avanzadas.get('PPP'), total_equipos),
        crear_caja_estadistica(net_rating_texto, "NET RATING<br/>Balance atq/def", posiciones_avanzadas.get('NetRtg'), total_equipos),
        crear_caja_estadistica(ast_pct_texto, "AST%", posiciones_avanzadas.get('AST%'), total_equipos),
        crear_caja_estadistica(ft_efficiency_texto, "FT EFFICIENCY", posiciones_avanzadas.get('FT_Eff'), total_equipos)
    ]
    
    tabla_fila3_avanzadas = Table([fila3_avanzadas], colWidths=[2.2*inch]*4)
    tabla_fila3_avanzadas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0.05*inch),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0.05*inch),
    ]))
    tabla_fila3_avanzadas.hAlign = 'CENTER'
    story.append(tabla_fila3_avanzadas)
    
    # Nota explicativa al final
    story.append(Spacer(1, 0.2*inch))
    nota_avanzadas = Paragraph(
        "* Métricas calculadas a partir de datos de boxscore de la temporada actual. "
        "eFG% y TS% miden eficiencia de tiro considerando el valor de los triples. "
        "3PAr (tasa de triples) indica dependencia del triple. "
        "FTr (tasa TL) refleja agresividad en penetración. "
        "TOV% mide pérdidas por posesión (menor es mejor). "
        "AST/TOV evalúa fluidez ofensiva. "
        "ORB% y DRB% miden control del rebote. "
        "PPP (puntos por posesión) evalúa eficiencia real. "
        "Net Rating compara ataque vs defensa. "
        "AST% mide colectividad ofensiva. "
        "FT Efficiency refleja puntos generados por contacto.",
        explicacion_style
    )
    story.append(nota_avanzadas)
    
    # ============== REORDENAR PÁGINAS SEGÚN NUEVA ESTRUCTURA ==============
    
    # El orden correcto es:
    # 1. Portada ✓
    # 2. Resumen General ✓  
    # 3. Comparativa ✓
    # Ahora necesitamos:
    # 4. Posicionamiento competitivo
    # 5. Estadísticas individuales
    # 6. Shot charts (análisis de tiros) - MOVIDO AQUÍ
    # 7. Análisis y resumen del equipo
    # 8. Rankings de equipos - MOVIDO AQUÍ
    # 9. Rankings de jugadores

    # ============== PÁGINA: POSICIONAMIENTO COMPETITIVO ==============
    if df_grupo is not None and len(df_grupo) > 1:
        crear_pagina_posicionamiento_competitivo(story, df_grupo, nombre_equipo, styles)
    
    # ============== PÁGINA: ESTADÍSTICAS INDIVIDUALES ==============
    crear_pagina_estadisticas_individuales(story, df_principales, titulo_style, styles, equipo_url, df_resultados, df_jugadores_norm)
    
    # ============== PÁGINA: INSIGHTS DE JUGADORES ==============
    crear_pagina_insights_jugadores(story, df_principales, titulo_style, styles, equipo_url, df_resultados)
    
    # ============== PÁGINAS: GRÁFICAS DE TIRO (SHOT CHARTS) ==============
    # Nota: Los shot charts se generan en generar_pdf_final y se insertan aquí automáticamente
    # Esta sección es un marcador para el orden correcto de las páginas
    
    # ============== PÁGINAS: HISTORIAL DE JUGADORES ==============
    if JSON_PATH and "datos_historicos" in str(JSON_PATH):
        print("\n📚 Recopilando historial de jugadores principales...")
        jugadores_con_historial = []
        
        for idx, jugador_row in df_principales.iterrows():
            jugador_id = str(jugador_row.get('ID', '')).strip()
            
            if jugador_id and jugador_id != 'nan':
                # Buscar historial del jugador
                historial = cargar_historial_jugador(
                    jugador_id=jugador_id,
                    JSON_PATH=JSON_PATH,
                    temporada_actual=temporada
                )
                
                if historial:
                    jugadores_con_historial.append((jugador_row.to_dict(), historial))
                    print(f"   ✅ Historial encontrado: {jugador_row.get('Jugador', 'Desconocido')}")
        
        # Generar páginas compactas con todos los jugadores (6-8 por página)
        if jugadores_con_historial:
            crear_pagina_historial_jugador(
                story=story,
                jugadores_list=jugadores_con_historial,
                titulo_style=titulo_style,
                styles=styles
            )
            print(f"✅ Páginas de historial generadas para {len(jugadores_con_historial)} jugadores")
        else:
            print("ℹ️  No se encontró historial para ningún jugador principal")
    
    # ============== PÁGINA: ANÁLISIS Y RESUMEN DEL EQUIPO ==============
    crear_pagina_analisis_equipo(story, df_principales, titulo_style, styles)
    
    # ============== PÁGINA: RANKINGS INDIVIDUALES ==============
    crear_pagina_rankings(story, rankings, styles, equipo_url, df_resultados)
    
    # ============== PÁGINA: RANKINGS DE EQUIPOS - MOVIDO DESPUÉS DE RANKINGS INDIVIDUALES ==============
    if rankings_equipos and df_grupo is not None:
        crear_pagina_rankings_equipos(story, rankings_equipos, df_grupo, nombre_equipo, styles)
        # Añadir segunda página de rankings con estadísticas adicionales (eFG% y FTr)
        crear_pagina_rankings_equipos_continuacion(story, rankings_equipos, df_grupo, nombre_equipo, styles)
        # Añadir tercera página con tablas anchas de TIROS LIBRES y TRIPLES
        crear_pagina_rankings_tiros(story, rankings_equipos, df_grupo, nombre_equipo, styles)
    
    return story

import pandas as pd
import json

def df_to_player_json(df: pd.DataFrame):
    # Copia para no modificar el original
    df = df.copy()

    # Columnas que quieres exportar (todas por partido excepto porcentajes)
    cols_base = [
        'MIN','PTS/PJ','REB/PJ','AST/PJ','STL/PJ','TO/PJ','VAL/PJ',
        'FG2A','FG2%','FG3A','FG3%','FTA','FT%','FG%','TS%','USG%',
        'OREB/PJ','DREB','PF', 'BLK', 'PJ'  # Añadir PJ para calcular promedios
    ]
    cols_export = [c for c in cols_base if c in df.columns]

    # Estadísticas que deben convertirse a "por partido" (las que NO son porcentajes ni ya están por partido)
    stats_to_convert = ['FG2A', 'FG3A', 'FTA', 'DREB', 'PF', 'BLK', 'MIN']
    
    # Crear el diccionario {Jugador: {estadísticas}}
    player_dict = {}
    for _, row in df.iterrows():
        nombre = str(row['Jugador']).strip()
        stats = {}
        pj = row.get('PJ', 1)  # Partidos jugados, default 1 para evitar división por 0
        
        for col in cols_export:
            if col == 'PJ':  # No incluir PJ en el output final
                continue
            elif col in stats_to_convert and pj > 0:
                # Convertir a por partido
                if col == 'MIN':
                    # MIN está en segundos, convertir a minutos por partido
                    # Dividir por 60 (segundos a minutos) y luego por PJ
                    stats[col] = round((row[col] / 60) / pj, 1) if pd.notnull(row[col]) else 0.0
                else:
                    # Otras estadísticas añaden /PJ al nombre
                    stats[f"{col}/PJ"] = round(row[col] / pj, 1) if pd.notnull(row[col]) else 0.0
            else:
                # Mantener tal como está (ya por partido o porcentajes)
                stats[col] = round(row[col], 1) if pd.notnull(row[col]) else 0.0
        
        player_dict[nombre] = stats

    # Exporta el JSON con formato legible y sin escapado de caracteres
    df_resumen = json.dumps(player_dict, ensure_ascii=False, indent=2)
    return df_resumen


def generar_resumen_jugadores_con_openai(df_jugadores):
    """
    Genera un resumen de los jugadores usando OpenAI GPT-4 mini
    Analiza las estadísticas y proporciona insights sobre fortalezas, debilidades y jugadores destacados
    """
    try:
        # Configurar OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        
        # 🔍 DIAGNÓSTICO DETALLADO
        print("=" * 60)
        print("🔍 DIAGNÓSTICO OPENAI API:")
        print(f"📋 API Key encontrada: {'SÍ' if api_key else 'NO'}")
        if api_key:
            print(f"📋 Longitud API Key: {len(api_key)} caracteres")
            print(f"📋 Empieza por 'sk-': {'SÍ' if api_key.startswith('sk-') else 'NO'}")
            print(f"📋 Primeros 10 chars: {api_key[:10]}...")
            print(f"📋 Últimos 4 chars: ...{api_key[-4:]}")
        else:
            print("📋 API Key es None o vacía")
        
        if not api_key or api_key == 'your_openai_api_key_here':
            print("❌ API Key no válida - devolviendo mensaje de error")
            print("=" * 60)
            return "Análisis no disponible: Configure su API key de OpenAI en el archivo .env"
        
        print("✅ API Key parece válida - intentando crear cliente...")
        client = openai.OpenAI(api_key=api_key)
        print("✅ Cliente OpenAI creado exitosamente")
        print("=" * 60)
        
        # Preparar datos de los jugadores para el análisis
        # Seleccionar las columnas más relevantes para el análisis
        columnas_relevantes = [
            'Jugador', 'PJ', 'MIN', 'PTS/PJ', 'REB/PJ', 'AST/PJ', 'STL/PJ', 'TO/PJ', 
            'VAL/PJ', 'FG%', 'FG3%', 'FT%', 'USG%'
        ]
        
        # Filtrar solo las columnas que existen en el DataFrame
        columnas_existentes = [col for col in columnas_relevantes if col in df_jugadores.columns]
        df_resumen = df_jugadores[columnas_existentes].copy()
        
        # Convertir a string para enviarlo a OpenAI (tomar solo los primeros 10 jugadores)
        #df_top_jugadores = df_resumen.head(10)
        #tabla_jugadores = df_top_jugadores.to_string(index=False, float_format=lambda x: f'{x:.1f}' if pd.notnull(x) else 'N/A')
        print("=== DEBUG df_to_player_json ===")
        print(f"Columnas del DataFrame: {df_jugadores.columns.tolist()}")
        print(f"Ejemplo de MIN y PJ del primer jugador:")
        if not df_jugadores.empty:
            primera_fila = df_jugadores.iloc[0]
            print(f"  Jugador: {primera_fila.get('Jugador', 'N/A')}")
            print(f"  MIN (segundos): {primera_fila.get('MIN', 'N/A')}")
            print(f"  PJ: {primera_fila.get('PJ', 'N/A')}")
            if pd.notnull(primera_fila.get('MIN')) and pd.notnull(primera_fila.get('PJ')) and primera_fila.get('PJ', 0) > 0:
                min_segundos = primera_fila.get('MIN')
                pj = primera_fila.get('PJ')
                min_por_partido = (min_segundos / 60) / pj
                print(f"  MIN en minutos: {min_segundos / 60:.1f}")
                print(f"  MIN/PJ calculado: {min_por_partido:.1f} min/partido")

        json_prompt = df_to_player_json(df_jugadores)
        # Crear el prompt para OpenAI
        
        # Obtener la ruta del archivo prompt_scouting.txt en el mismo directorio que este módulo
        prompt_path = Path(__file__).parent / "prompt_scouting.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        # Combinar el template del prompt con los datos reales de los jugadores
        prompt = f"{prompt_template}\n\nDATOS DE LOS JUGADORES:\n{json_prompt}"

        # Realizar la llamada a OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista experto de baloncesto especializado en scouting. Proporciona análisis profesionales y concisos basados en estadísticas."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10000,
            temperature=0.5
        )
        
        # Debug info (sin mostrar todo el contenido)
        print(f"✅ Respuesta OpenAI recibida - Tokens usados: {response.usage.total_tokens}")
        print(f"📝 Reason: {response.choices[0].finish_reason}")
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_details = {
            'tipo': type(e).__name__,
            'mensaje': str(e),
            'modulo': getattr(e, '__module__', 'desconocido')
        }
        
        print("=" * 60)
        print("🚨 ERROR EN LLAMADA OPENAI:")
        print(f"📋 Tipo de error: {error_details['tipo']}")
        print(f"📋 Mensaje completo: {error_details['mensaje']}")
        print(f"📋 Módulo: {error_details['modulo']}")
        
        # Diagnósticos específicos según el tipo de error
        if 'authentication' in str(e).lower() or 'api_key' in str(e).lower():
            print("💡 POSIBLE CAUSA: Problema con la API Key")
            print("   - Verifica que la API key sea válida")
            print("   - Comprueba que tengas créditos en OpenAI")
        elif 'connection' in str(e).lower() or 'network' in str(e).lower():
            print("💡 POSIBLE CAUSA: Problema de conexión")
            print("   - Verifica tu conexión a internet")
            print("   - OpenAI puede estar temporalmente inaccesible")
        elif 'rate' in str(e).lower() or 'limit' in str(e).lower():
            print("💡 POSIBLE CAUSA: Límite de rate excedido")
            print("   - Has hecho demasiadas peticiones muy rápido")
            print("   - Espera unos minutos antes de intentar de nuevo")
        elif 'quota' in str(e).lower() or 'billing' in str(e).lower():
            print("💡 POSIBLE CAUSA: Problema de facturación")
            print("   - Sin créditos en la cuenta de OpenAI")
            print("   - Verifica tu método de pago")
        else:
            print("💡 Error no específico - revisar mensaje completo arriba")
        
        print("=" * 60)
        
        # Retornar JSON de fallback para que el PDF siga funcionando
        return f'''{{
  "jugadores": [
    {{
      "nombre": "ERROR DE CONEXIÓN OPENAI",
      "descripcion": "No se pudo obtener análisis automático. Error: {error_details['tipo']} - {str(e)[:50]}...",
      "fortalezas": [
        "Sistema de análisis disponible",
        "Error específico: {error_details['tipo']}",
        "Revisar configuración de API",
        "Comprobar créditos en OpenAI"
      ],
      "debilidades": [
        "Conexión con OpenAI fallida",
        "API key puede estar incorrecta",
        "Sin créditos disponibles",
        "Problemas de red temporales",
        "Verificar cuenta de OpenAI"
      ]
    }},
    {{
      "nombre": "DIAGNÓSTICO TÉCNICO",
      "descripcion": "Error técnico: {error_details['mensaje'][:80]}",
      "fortalezas": [
        "Sistema preparado para diagnóstico",
        "Información de error disponible",
        "Fallback funcionando correctamente",
        "Layout visual implementado"
      ],
      "debilidades": [
        "Configuración API incompleta",
        "Revisar variables de entorno",
        "Contactar soporte si persiste",
        "Temporal hasta resolver conexión"
      ]
    }},
    {{
      "nombre": "DATOS DE RESPALDO",
      "descripcion": "Mientras se resuelve el problema, el sistema muestra este layout de ejemplo",
      "fortalezas": [
        "Diseño visual funcionando",
        "Estructura correcta implementada",
        "Colores y formato aplicados",
        "Listo para datos reales"
      ],
      "debilidades": [
        "No son datos de jugadores reales",
        "Requiere solución del problema API",
        "Solo para demostración temporal",
        "Configurar OpenAI correctamente"
      ]
    }}
  ]
}}'''


def crear_fila_historial_jugador(jugador_data, historial):
    """
    Crea una fila ultra-compacta con el historial de un jugador.
    Retorna una tupla: (lista de datos, color de fondo según evolución de valoración, evol_val)
    """
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    
    nombre_jugador = jugador_data.get('Jugador', 'Jugador')
    
    if not historial:
        return None, colors.white, 0.0
    
    # Obtener la temporada más reciente
    year = sorted(historial.keys(), reverse=True)[0]
    datos_year = historial[year]
    jugador_hist = datos_year["jugador"]
    
    # Extraer enlace del jugador desde el JSON
    enlace_jugador = jugador_hist.get("enlace", "")
    
    # Calcular estadísticas por partido
    pj = jugador_hist.get("partidos", 0)
    if pj == 0:
        return None, colors.white, 0.0
    
    pts_pj = round(jugador_hist.get("puntos", 0) / pj, 1)
    reb_pj = round(jugador_hist.get("rebotes_totales", 0) / pj, 1)
    ast_pj = round(jugador_hist.get("asistencias", 0) / pj, 1)
    val_pj = round(jugador_hist.get("valoracion", 0) / pj, 1)
    
    # Estadísticas actuales para comparación
    pts_actual = jugador_data.get('PTS/PJ', 0)
    reb_actual = jugador_data.get('REB/PJ', 0)
    ast_actual = jugador_data.get('AST/PJ', 0)
    val_actual = jugador_data.get('VAL/PJ', 0)
    
    # Calcular evolución total (suma de todas las mejoras individuales)
    evol_pts = round(pts_actual - pts_pj, 1)
    evol_reb = round(reb_actual - reb_pj, 1)
    evol_ast = round(ast_actual - ast_pj, 1)
    evol_val = round(val_actual - val_pj, 1)
    
    # Mejora total = suma de todas las evoluciones
    mejora_total = round(evol_pts + evol_reb + evol_ast + evol_val, 1)
    
    # Determinar color de fondo según evolución de VALORACIÓN únicamente
    if evol_val >= 3:
        # Mejora de valoración de 3 o más → VERDE
        bg_color = colors.HexColor('#d1fae5')  # Verde claro
    elif evol_val <= -3:
        # Empeora valoración de 3 o más → ROJO
        bg_color = colors.HexColor('#fee2e2')  # Rojo claro
    else:
        # Sin cambio significativo en valoración → Blanco
        bg_color = colors.white
    
    # Formatear datos aprovechando TODO el espacio disponible
    equipo_anterior = datos_year['equipo']
    # Acortar nombre del equipo SOLO si es extremadamente largo (más de 35 caracteres)
    if len(equipo_anterior) > 35:
        equipo_anterior = equipo_anterior[:33] + "..."
    
    # Obtener competición desde la clave 'categoria' (1º FEB, 2º FEB, T3A, etc.)
    competicion = datos_year.get('categoria', 'N/A')
    
    # Crear nombre clickeable si hay enlace
    nombre_style = ParagraphStyle(
        'NombreJugadorHistorial',
        fontSize=9,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    if enlace_jugador:
        # Acortar nombre si es muy largo
        nombre_mostrar = nombre_jugador[:35] + "..." if len(nombre_jugador) > 35 else nombre_jugador
        nombre_clickeable = Paragraph(
            f'<a href="{enlace_jugador}" color="#3182ce"><u>{nombre_mostrar}</u></a>',
            nombre_style
        )
    else:
        # Sin enlace, solo texto normal
        nombre_mostrar = nombre_jugador[:35] + "..." if len(nombre_jugador) > 35 else nombre_jugador
        nombre_clickeable = Paragraph(nombre_mostrar, nombre_style)
    
    # Crear celdas compactas con valor anterior y cambio (formato HTML para colores)
    def crear_celda_estadistica(valor_anterior, cambio):
        if cambio > 0:
            cambio_html = f'<font color="#38a169"><b>+{cambio:.1f}</b></font>'
        elif cambio < 0:
            cambio_html = f'<font color="#e53e3e"><b>{cambio:.1f}</b></font>'
        else:
            cambio_html = '<b>0</b>'
        return f"{valor_anterior}<br/>{cambio_html}"
    
    # Crear celdas usando Paragraph para soportar HTML
    celda_style = ParagraphStyle(
        'CeldaEstadistica',
        fontSize=9,
        textColor=colors.black,
        alignment=TA_CENTER,
        fontName='Helvetica',
        leading=11
    )
    
    pts_celda = Paragraph(crear_celda_estadistica(pts_pj, evol_pts), celda_style)
    reb_celda = Paragraph(crear_celda_estadistica(reb_pj, evol_reb), celda_style)
    ast_celda = Paragraph(crear_celda_estadistica(ast_pj, evol_ast), celda_style)
    val_celda = Paragraph(crear_celda_estadistica(val_pj, evol_val), celda_style)

    return [
        nombre_clickeable,  # Nombre clickeable como Paragraph
        f"{competicion}\n{equipo_anterior}",  # Mostrar competición en vez del año
        pts_celda,          # PTS: anterior + cambio con colores
        reb_celda,          # REB: anterior + cambio con colores
        ast_celda,          # AST: anterior + cambio con colores
        val_celda           # VAL: anterior + cambio con colores
    ], bg_color, evol_val  # Retornamos evol_val para ordenamiento


def crear_pagina_historial_jugador(story, jugadores_list, titulo_style, styles):
    """
    Crea UNA SOLA página con historial de TODOS los jugadores.
    Formato ultra-compacto con colores: VERDE (mejora ≥3) y ROJO (empeora ≤-3).
    
    Args:
        story: Lista de elementos del PDF
        jugadores_list: Lista de tuplas (jugador_data, historial)
        titulo_style: Estilo para títulos
        styles: Estilos del documento
    """
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle, NextPageTemplate
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm, inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    
    if not jugadores_list:
        return
    
    # Cambiar a página landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Título con el mismo estilo que otras páginas
    titulo_temporada_style = ParagraphStyle(
        'TituloTemporada',
        parent=titulo_style,
        fontSize=20,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=15,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("ESTADÍSTICAS INDIVIDUALES TEMPORADA PASADA", titulo_temporada_style)
    story.append(titulo)
    story.append(Spacer(1, 0.2*inch))
    
    # Crear tabla de datos ultra-compacta - SIN MEJORA TOTAL
    header = ['JUGADOR', 'COMPETICIÓN\nEQUIPO', 'PTS/PJ', 'REB/PJ', 'AST/PJ', 'VAL/PJ']
    table_data = [header]
    row_colors = []  # Para almacenar colores de fondo por fila
    
    # Crear lista temporal para ordenar por cambio total
    jugadores_con_cambio = []
    
    for jugador_data, historial in jugadores_list:
        resultado = crear_fila_historial_jugador(jugador_data, historial)
        if resultado[0]:  # Si hay datos válidos
            fila_data, bg_color, evol_val = resultado
            jugadores_con_cambio.append((abs(evol_val), evol_val, fila_data, bg_color))
    
    # Ordenar por valor absoluto del cambio (de mayor a menor)
    jugadores_con_cambio.sort(key=lambda x: x[0], reverse=True)
    
    # Tomar solo los primeros 9 jugadores
    jugadores_top = jugadores_con_cambio[:9]
    
    # Añadir las filas ordenadas a la tabla
    for _, _, fila_data, bg_color in jugadores_top:
        table_data.append(fila_data)
        row_colors.append(bg_color)
    
    if len(table_data) == 1:  # Solo header
        story.append(Paragraph("No hay datos históricos disponibles", styles['Normal']))
        return
    
    # Calcular anchos de columna para usar TODO el ancho disponible
    # Total disponible en landscape A4: ~280mm (con márgenes de 10mm a cada lado)
    # 6 columnas: Jugador, Equipo (MUCHO MÁS ANCHO), métricas más estrechas
    col_widths = [60*mm, 70*mm, 25*mm, 25*mm, 25*mm, 30*mm]  # Total: 230mm
    
    hist_table = Table(table_data, colWidths=col_widths)
    
    # Estilos base de la tabla
    table_style = [
        # Header - Mismo estilo que otras páginas
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),  # Gris consistente
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),  # Tamaño más grande
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Datos - Estilo mejorado
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),  # Tamaño más grande
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Todo centrado como otras páginas
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Todo centrado
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        
        # Bordes - Estilo consistente
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),  # Mismo color que otras tablas
        
        # Padding mejorado
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    
    # Añadir colores de fondo por fila según evolución de valoración
    for idx, bg_color in enumerate(row_colors, start=1):
        table_style.append(('BACKGROUND', (0, idx), (-1, idx), bg_color))
        
        # Si es verde o rojo, destacar la columna VAL/PJ (columna 5)
        if bg_color != colors.white:
            table_style.append(('FONTNAME', (5, idx), (5, idx), 'Helvetica-Bold'))
    
    hist_table.setStyle(TableStyle(table_style))
    
    story.append(hist_table)
    story.append(Spacer(1, 3*mm))
    
    # Leyenda explicativa con los colores
    leyenda_style = ParagraphStyle(
        'LeyendaHistorial',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    leyenda_text = (
        '<b>LEYENDA:</b> '
        'Los valores en negro corresponden a las estadísticas de la temporada 24/25. '
        'Los valores con +/- indican las mejoras o declives respecto a la temporada actual.'
    )
    story.append(Paragraph(leyenda_text, leyenda_style))


def crear_tablita_insight_jugador(jugador_data, numeros_jugadores=None):
    """
    Crea una tablita individual para insights del jugador con foto, nombre, número y espacio para anotaciones.
    Usa la misma lógica de foto que estadísticas individuales.
    AJUSTADO: Foto más pequeña y cabecera más fina.
    
    Args:
        jugador_data: Serie con datos del jugador
        numeros_jugadores: Dict con números de jugadores
        
    Returns:
        Table: Tablita con el layout solicitado (más ancha y menos alta)
    """
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import mm, inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    
    # Obtener información básica del jugador
    nombre_jugador = jugador_data.get('Jugador', 'N/A')
    numero_jugador = buscar_numero_jugador(jugador_data, numeros_jugadores) if numeros_jugadores else None
    jugador_id = str(jugador_data.get('ID', '')).strip()
    
    # Mostrar número si está disponible
    if numero_jugador and numero_jugador.strip():
        texto_nombre_numero = f"#{numero_jugador} - {nombre_jugador}"
    else:
        texto_nombre_numero = nombre_jugador
    
    # USAR LA MISMA LÓGICA DE FOTO QUE ESTADÍSTICAS INDIVIDUALES
    foto_jugador = None
    try:
        # Método 1: Intentar usar get_player_photo_buffer si tenemos jugador_id
        if jugador_id and jugador_id != 'nan':
            try:
                photo_buffer = get_player_photo_buffer(str(jugador_id))
                if photo_buffer:
                    # FOTO AÚN MÁS PEQUEÑA para formato ultra-compacto - Reducido de 18x22mm a 16x20mm
                    foto_jugador = pil_buffer_to_reportlab_image(photo_buffer, width=16*mm, height=20*mm)
                    print(f"   ✅ Foto cargada para insights: {nombre_jugador}")
                else:
                    print(f"   ⚠️ Buffer vacío para jugador_id: {jugador_id}")
            except Exception as e:
                print(f"   ❌ Error con get_player_photo_buffer para insights: {e}")
        
        # Método 2: Si no funciona el buffer, intentar cargar desde directorio de fotos
        if foto_jugador is None:
            from pathlib import Path
            data_dir = Path(__file__).parent.parent / "data"
            cache_dir = data_dir / "player_photos_cache"
            
            # Buscar foto por ID
            if jugador_id and jugador_id != 'nan':
                photo_path = cache_dir / f"{jugador_id}.jpg"
                if photo_path.exists():
                    # FOTO AÚN MÁS PEQUEÑA para formato ultra-compacto - Reducido de 18x22mm a 16x20mm
                    foto_jugador = ReportLabImage(str(photo_path), width=16*mm, height=20*mm)
                    print(f"   ✅ Foto cargada desde cache para insights: {nombre_jugador}")
    
    except Exception as e:
        print(f"⚠️  Error al cargar foto de {nombre_jugador} para insights: {e}")
    
    # Si no hay foto, crear placeholder más pequeño
    if foto_jugador is None:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle
        placeholder_style = ParagraphStyle(
            'PlaceholderFoto',
            fontSize=7,  # Reducido de 8 a 7
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER,
            fontName='Helvetica',
        )
        foto_jugador = Paragraph("Sin<br/>foto", placeholder_style)
    
    # Crear contenido de la tablita - FORMATO MÁS ANCHO Y MENOS ALTO
    # Estructura: [nombre_numero (span 2 columnas)]
    #            [foto | espacio_anotaciones]
    
    # Fila 1: Encabezado con nombre y número
    fila_nombre = [texto_nombre_numero, ""]
    
    # Fila 2: Foto y espacio para anotaciones
    fila_contenido = [foto_jugador, ""]
    
    # Crear tabla con el contenido - DIMENSIONES MÁS ANCHAS Y MENOS ALTAS
    contenido_tablita = [fila_nombre, fila_contenido]
    
    # Aumentar ancho total y reducir altura AÚN MÁS para que quepan 4 filas
    tablita = Table(contenido_tablita, 
                   colWidths=[28*mm, 102*mm],  # Ajustado de [30mm, 100mm] a [28mm, 102mm] = 130mm total
                   rowHeights=[7*mm, 25*mm])   # ALTURA TOTAL REDUCIDA: [7mm, 25mm] = 32mm total (vs 35mm anterior)
    
    # Estilo de la tablita
    tablita.setStyle(TableStyle([
        # Combinar columnas para el nombre en la primera fila
        ('SPAN', (0, 0), (1, 0)),
        
        # Alineación
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),  # Nombre centrado
        ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),  # Nombre centrado verticalmente
        ('ALIGN', (0, 1), (0, 1), 'CENTER'),   # Foto centrada
        ('VALIGN', (0, 1), (0, 1), 'MIDDLE'),  # Foto centrada verticalmente
        ('ALIGN', (1, 1), (1, 1), 'LEFT'),     # Espacio anotaciones alineado a la izquierda
        ('VALIGN', (1, 1), (1, 1), 'TOP'),     # Espacio anotaciones alineado arriba
        
        # Fuentes y colores - TEXTO MÁS GRANDE PARA MEJOR LEGIBILIDAD
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (1, 0), 9),  # Aumentado de 7 a 9 para mejor legibilidad del nombre y número
        ('TEXTCOLOR', (0, 0), (1, 0), colors.white),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#4a5568')),  # Fondo gris oscuro para el nombre
        
        # Bordes NEGROS como en estadísticas individuales
        ('GRID', (0, 0), (1, 1), 1, colors.black),  # Cambiado de gris claro a negro
        ('LINEWIDTH', (0, 0), (1, 1), 1),
        
        # Padding ultra-reducido para máxima compacidad
        ('TOPPADDING', (0, 0), (1, 1), 1),     # Reducido de 2 a 1
        ('BOTTOMPADDING', (0, 0), (1, 1), 1),  # Reducido de 2 a 1
        ('LEFTPADDING', (0, 0), (1, 1), 3),    # Reducido de 4 a 3
        ('RIGHTPADDING', (0, 0), (1, 1), 3),   # Reducido de 4 a 3
        
        # Fondo blanco para el área de anotaciones
        ('BACKGROUND', (1, 1), (1, 1), colors.white),
    ]))
    
    return tablita


def crear_pagina_insights_jugadores(story, df_principales, titulo_style, styles, equipo_url=None, df_resultados=None):
    """
    Crea página de "Comentarios Jugadores" en formato landscape con 8 tablitas (2 columnas x 4 filas).
    Cada tablita contiene foto del jugador, nombre, número y espacio para anotaciones del entrenador.
    
    Args:
        story: Lista de elementos del PDF
        df_principales: DataFrame con jugadores principales
        titulo_style: Estilo para el título
        styles: Estilos de ReportLab
        equipo_url: URL del equipo para obtener números de jugadores
        df_resultados: DataFrame con resultados
    """
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle, NextPageTemplate
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    
    # Obtener números de jugadores si está disponible
    numeros_jugadores = {}
    if equipo_url:
        try:
            numeros_jugadores = obtener_numeros_jugadores_equipo(equipo_url, df_resultados)
            print(f"✅ Números de jugadores obtenidos para insights: {len(numeros_jugadores.get('por_id', {}))}")
        except Exception as e:
            print(f"⚠️  Error al obtener números de jugadores para insights: {e}")
            numeros_jugadores = {}
    
    # Cambiar a plantilla landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # USAR EL MISMO ESTILO DE TÍTULO QUE ESTADÍSTICAS INDIVIDUALES
    titulo_insights_style = ParagraphStyle(
        'TituloInsights',
        parent=titulo_style,
        fontSize=20,  # Mismo tamaño que estadísticas individuales
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=15,  # Mismo espacio que estadísticas individuales
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("COMENTARIOS JUGADORES", titulo_insights_style)
    story.append(titulo)
    
    # REDUCIR ESPACIADOR - Usar mismo que estadísticas individuales
    story.append(Spacer(1, 0.2*inch))  # Reducido de 20 a 0.2*inch = mismo que estadísticas individuales
    
    # Seleccionar los 8 jugadores con mejor valoración por partido
    if 'VAL/PJ' in df_principales.columns:
        jugadores_insights = df_principales.sort_values('VAL/PJ', ascending=False).head(8).copy()
    else:
        # Fallback a los primeros 8 si no hay VAL/PJ
        jugadores_insights = df_principales.head(8).copy()
    
    print(f"🏀 Seleccionados {len(jugadores_insights)} jugadores para insights (ordenados por valoración)")
    
    # Crear tablitas
    tablitas = []
    for idx, jugador_row in jugadores_insights.iterrows():
        tablita = crear_tablita_insight_jugador(jugador_row, numeros_jugadores)
        tablitas.append(tablita)
    
    # Rellenar con tablitas vacías si hay menos de 8 jugadores
    while len(tablitas) < 8:
        # Crear tablita vacía
        jugador_vacio = {
            'Jugador': '---',
            'ID': ''
        }
        tablita_vacia = crear_tablita_insight_jugador(jugador_vacio, numeros_jugadores)
        tablitas.append(tablita_vacia)
    
    # Organizar en grid 2x4 (2 columnas, 4 filas)
    # HACER LAS TABLITAS MÁS ANCHAS Y MENOS ALTAS
    grid_data = []
    for i in range(0, 8, 2):  # De 2 en 2 para crear filas
        fila = [tablitas[i], tablitas[i+1] if i+1 < len(tablitas) else ""]
        grid_data.append(fila)
    
    # Crear tabla principal con el grid - REDUCIR MÁS LA ALTURA PARA QUE QUEPAN 4 FILAS
    tabla_principal = Table(grid_data, 
                           colWidths=[135*mm, 135*mm],  # Mantener ancho
                           rowHeights=[35*mm, 35*mm, 35*mm, 35*mm])  # REDUCIDO de 40mm a 35mm por fila
    
    # Estilo para la tabla principal
    tabla_principal.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),   # Reducido padding
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    # Añadir la tabla al story
    story.append(tabla_principal)
    
    # Espaciador final más pequeño
    story.append(Spacer(1, 0.2*inch))
    
    print(f"✅ Página de Comentarios Jugadores creada con {len(jugadores_insights)} jugadores")


def crear_pagina_estadisticas_individuales(story, df_principales, titulo_style, styles, equipo_url=None, df_resultados=None, df_jugadores_norm=None):
    """
    Crea página de estadísticas individuales en formato landscape compacto
    similar al mostrado en la imagen con 6 jugadores por página (3 filas x 2 columnas)
    """
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle, Image, NextPageTemplate
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import pandas as pd
    import os

    # Obtener números de jugadores si tenemos información del equipo
    numeros_jugadores = {}
    if equipo_url:
        try:
            numeros_jugadores = obtener_numeros_jugadores_equipo(equipo_url, df_resultados)
        except Exception as e:
            pass

    # Asegurar que estamos en landscape y forzar el cambio de template con PageBreak
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Volver al sistema original: solo jugadores principales (>25% partidos)
    # Usar solo jugadores principales (comportamiento original)
    df_jugadores_principales = df_principales.copy()
    
    # Obtener números de jugadores del equipo
    numeros_jugadores = {}
    if equipo_url:
        try:
            numeros_jugadores = obtener_numeros_jugadores_equipo(equipo_url, df_resultados)
        except Exception as e:
            pass
    
    # Título
    titulo_individuales_style = ParagraphStyle(
        'TituloIndividuales',
        parent=titulo_style,
        fontSize=20,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=15,
        fontName='Helvetica-Bold',
    )
    
    titulo_individuales = Paragraph("ESTADÍSTICAS INDIVIDUALES", titulo_individuales_style)
    story.append(titulo_individuales)
    story.append(Spacer(1, 0.2*inch))
    
    # Función para crear ficha compacta de jugador simplificada
    def crear_ficha_jugador_compacta(jugador_data):
        """Crea una ficha compacta simplificada: nombre arriba, foto izquierda, stats derecha"""
        
        # Obtener datos del jugador
        nombre = jugador_data['Jugador']
        foto_path = jugador_data.get('foto_path', '')
        partidos_jugados = int(jugador_data.get('PJ', 0))
        
        # Buscar número de camiseta usando la nueva función
        numero = buscar_numero_jugador(jugador_data, numeros_jugadores)
        if numero:
            nombre = f"<b>#{numero}</b> {nombre}"
        
        # Calcular estadísticas por partido
        minutos_totales = jugador_data['MIN'] / jugador_data['PJ'] / 60  # Minutos por partido
        minutos_enteros = int(minutos_totales)
        segundos = int((minutos_totales - minutos_enteros) * 60)
        min_formato = f"{minutos_enteros}:{segundos:02d}"
        
        pts_pp = round(jugador_data['PTS/PJ'], 1)
        fg_pct = round(jugador_data.get('FG%', 0), 1)
        fg2_pct = round(jugador_data.get('FG2%', 0), 1) 
        fg3_pct = round(jugador_data.get('FG3%', 0), 1)
        ft_pct = round(jugador_data.get('FT%', 0), 1)
        ast_pp = round(jugador_data['AST/PJ'], 1)
        reb_pp = round(jugador_data['REB/PJ'], 1)
        stl_pp = round(jugador_data['STL/PJ'], 1)
        to_pp = round(jugador_data['TO/PJ'], 1)
        fg3a_pp = round(jugador_data['FG3A/PJ'], 1)
        val_pp = round(jugador_data['VAL/PJ'], 1)
        fg3m_pp = round(jugador_data.get('FG3M', 0) / jugador_data.get('PJ', 1), 1)
        
        # Estilos
        nombre_style = ParagraphStyle('NombreJugador', fontSize=10, fontName='Helvetica-Bold',
                                    textColor=colors.white, alignment=TA_CENTER, leading=12)  # Texto blanco para consistencia
        
        stat_number_style = ParagraphStyle('StatNumber', fontSize=9, fontName='Helvetica-Bold',
                                         textColor=colors.HexColor('#2b6cb0'), alignment=TA_CENTER, leading=10)
        
        stat_label_style = ParagraphStyle('StatLabel', fontSize=7, fontName='Helvetica',
                                        textColor=colors.HexColor('#666666'), alignment=TA_CENTER, leading=8)
        
        # Crear foto o placeholder (ligeramente más grande)
        foto_jugador = None
        
        # Obtener el ID del jugador para intentar cargar la foto
        jugador_id = jugador_data.get('ID', '')
        
        # Método 1: Intentar usar get_player_photo_buffer si tenemos jugador_id
        if jugador_id:
            try:
                print(f"   🔄 Intentando get_player_photo_buffer con ID: {jugador_id}")
                photo_buffer = get_player_photo_buffer(str(jugador_id))
                if photo_buffer:
                    foto_jugador = pil_buffer_to_reportlab_image(photo_buffer, width=19*mm, height=19*mm)
                    print(f"   ✅ Imagen cargada desde buffer correctamente")
                else:
                    print(f"   ⚠️ Buffer vacío para jugador_id: {jugador_id}")
            except Exception as e:
                print(f"   ❌ Error con get_player_photo_buffer: {e}")
        
        # Método 2: Si no funciona el buffer, intentar foto_path
        if foto_jugador is None and foto_path and os.path.exists(foto_path):
            try:
                foto_jugador = Image(foto_path, width=19*mm, height=19*mm, kind='proportional')
                print(f"   ✅ Imagen cargada desde foto_path correctamente")
            except Exception as e:
                print(f"   ❌ Error cargando imagen desde foto_path: {e}")
        
        # Método 3: Si nada funciona, usar placeholder
        if foto_jugador is None:
            print(f"   ⚠️ Usando placeholder para jugador individual")
            foto_jugador = Paragraph("👤", ParagraphStyle('', fontSize=12, alignment=TA_CENTER))
        
        # Calcular rebotes ofensivos y defensivos por partido
        oreb_pp = round(jugador_data.get('OREB', 0) / jugador_data.get('PJ', 1), 1)
        dreb_pp = round(jugador_data.get('DREB', 0) / jugador_data.get('PJ', 1), 1)
        
        # Calcular porcentaje de uso
        usg_pct = round(jugador_data.get('USG%', 0), 1)
        
        # Crear grid de estadísticas compacto (5 columnas x 4 filas)
        stats_data = [
            # Primera fila
            [Paragraph("MIN", stat_label_style), Paragraph("PTS", stat_label_style),
             Paragraph("AST", stat_label_style), Paragraph("REB", stat_label_style),
             Paragraph("VAL", stat_label_style)],
            [Paragraph(min_formato, stat_number_style), Paragraph(str(pts_pp), stat_number_style),
             Paragraph(str(ast_pp), stat_number_style), Paragraph(str(reb_pp), stat_number_style),
             Paragraph(str(val_pp), stat_number_style)],
            
            # Segunda fila
            [Paragraph("TC%", stat_label_style), Paragraph("2P%", stat_label_style),
             Paragraph("3P%", stat_label_style), Paragraph("TL%", stat_label_style),
             Paragraph("ROB", stat_label_style)],
            [Paragraph(f"{fg_pct}%", stat_number_style), Paragraph(f"{fg2_pct}%", stat_number_style),
             Paragraph(f"{fg3_pct}%", stat_number_style), Paragraph(f"{ft_pct}%", stat_number_style),
             Paragraph(str(stl_pp), stat_number_style)],
             
            # Tercera fila
            [Paragraph("OREB", stat_label_style), Paragraph("DREB", stat_label_style),
             Paragraph("T3I", stat_label_style), Paragraph("PER", stat_label_style),
             Paragraph("USG%", stat_label_style)],
            [Paragraph(str(oreb_pp), stat_number_style), Paragraph(str(dreb_pp), stat_number_style),
             Paragraph(str(fg3a_pp), stat_number_style), Paragraph(str(to_pp), stat_number_style),
             Paragraph(f"{usg_pct}%", stat_number_style)]
        ]
        
        # Anchos de columna para las estadísticas (más amplios)
        col_widths = [12*mm, 12*mm, 12*mm, 12*mm, 12*mm]
        row_heights = [4*mm, 6*mm, 4*mm, 6*mm, 4*mm, 6*mm]
        
        stats_table = Table(stats_data, colWidths=col_widths, rowHeights=row_heights)
        stats_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e9ecef')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#e9ecef')),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
        ]))
        
        # Crear texto de partidos jugados con formato más adecuado
        partidos_text = f"{partidos_jugados} partidos" if partidos_jugados != 1 else "1 partido"
        partidos_style = ParagraphStyle('PartidosJugados', fontSize=7, fontName='Helvetica-Bold',
                                      textColor=colors.HexColor('#666666'), alignment=TA_CENTER, leading=8)
        partidos_paragraph = Paragraph(partidos_text, partidos_style)
        
        # Crear una mini-tabla para la columna izquierda (foto + partidos)
        foto_y_partidos_data = [
            [foto_jugador],
            [partidos_paragraph]
        ]
        
        foto_y_partidos_table = Table(foto_y_partidos_data, 
                                    colWidths=[20*mm],
                                    rowHeights=[14*mm, 6*mm])  # Más espacio para el texto debajo
        
        foto_y_partidos_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),  # Foto centrada
            ('VALIGN', (0, 1), (0, 1), 'BOTTOM'),  # Partidos abajo
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1)
        ]))
        
        # Estructura de la ficha: mantenemos EXACTAMENTE la misma estructura anterior
        ficha_data = [
            # Fila 1: Nombre del jugador (span completo)
            [Paragraph(nombre, nombre_style), ""],
            # Fila 2: Foto+partidos a la izquierda, estadísticas a la derecha
            [foto_y_partidos_table, stats_table]
        ]
        
        ficha_table = Table(ficha_data, 
                           colWidths=[20*mm, 62*mm],  # MISMAS dimensiones que antes
                           rowHeights=[8*mm, 32*mm])  # MISMAS alturas que antes
        
        ficha_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),  # Nombre ocupa ambas columnas
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Todo centrado como antes
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#000000')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),  # Fondo del nombre - mismo gris que comparativa
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
        ]))
        
        return ficha_table
    
    # Procesar jugadores en grupos de 9 (3 filas x 3 columnas por página)
    jugadores_por_pagina = 9
    total_jugadores = len(df_jugadores_principales)
    
    for i in range(0, total_jugadores, jugadores_por_pagina):
        if i > 0:  # Nueva página para grupos adicionales
            story.append(NextPageTemplate('landscape'))
            story.append(PageBreak())
            story.append(Paragraph("ESTADÍSTICAS INDIVIDUALES (cont.)", titulo_individuales_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Obtener jugadores para esta página
        jugadores_pagina = df_jugadores_principales.iloc[i:i+jugadores_por_pagina]
        
        # Crear fichas
        fichas = []
        for _, jugador in jugadores_pagina.iterrows():
            ficha = crear_ficha_jugador_compacta(jugador)
            fichas.append(ficha)
        
        # Organizar en filas de 3 columnas
        for j in range(0, len(fichas), 3):
            # Obtener hasta 3 jugadores para esta fila
            fila_jugadores = fichas[j:j+3]
            
            # Rellenar con espacios vacíos si es necesario
            while len(fila_jugadores) < 3:
                espacio_vacio = Table([[""]], colWidths=[3.3*inch], rowHeights=[1.5*inch])
                espacio_vacio.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.white)]))
                fila_jugadores.append(espacio_vacio)
            
            # Crear fila con 3 jugadores
            fila_table = Table([fila_jugadores], colWidths=[3.3*inch, 3.3*inch, 3.3*inch])
            fila_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0.1*inch),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0.1*inch),
                ('TOPPADDING', (0, 0), (-1, -1), 0.1*inch),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.1*inch)
            ]))
            
            story.append(fila_table)
            story.append(Spacer(1, 0.15*inch))
    
    # Agregar resumen generado por OpenAI al final de todas las páginas de estadísticas
    # Fin de la función de estadísticas individuales
    # El análisis se ha movido a una página separada


def crear_pagina_analisis_equipo(story, df_principales, titulo_style, styles):
    """
    Crea página de análisis y resumen del equipo en formato landscape con 3 cajitas
    """
    from reportlab.platypus import PageBreak, Paragraph, Spacer, NextPageTemplate, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    import json

    # Cambiar a plantilla landscape
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Generar resumen con OpenAI - ACTIVADO (ahora devuelve JSON)
    resumen_json = generar_resumen_jugadores_con_openai(df_principales)
    
    # Título principal de la página
    titulo_style = ParagraphStyle(
        'TituloJugadores',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=15,
        fontName='Helvetica-Bold',
    )
    
    titulo = Paragraph("JUGADORES DESTACADOS", titulo_style)
    story.append(titulo)
    story.append(Spacer(1, 0.3*inch))
    
    # Estilos para la información de los jugadores
    nombre_jugador_style = ParagraphStyle(
        'NombreJugador',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
        spaceAfter=8,
        fontName='Helvetica-Bold',
    )
    
    descripcion_style = ParagraphStyle(
        'DescripcionJugador',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        fontName='Helvetica',
        leading=12,
    )
    
    titulo_seccion_style = ParagraphStyle(
        'TituloSeccion',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_LEFT,
        spaceAfter=4,
        fontName='Helvetica-Bold',
    )
    
    lista_style = ParagraphStyle(
        'ListaJugador',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_LEFT,
        spaceAfter=3,
        fontName='Helvetica',
        leading=11,
        leftIndent=10,
    )
    
    try:
        # Limpiar la respuesta de OpenAI (eliminar bloques de markdown si existen)
        resumen_limpio = resumen_json.strip()
        
        # Si la respuesta está envuelta en ```json ... ```, extraer solo el JSON
        if resumen_limpio.startswith('```'):
            # Buscar el inicio y fin del bloque
            lines = resumen_limpio.split('\n')
            # Eliminar la primera línea (```json o ```)
            if lines[0].startswith('```'):
                lines = lines[1:]
            # Eliminar la última línea si es ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            resumen_limpio = '\n'.join(lines)
        
        # Intentar parsear el JSON de OpenAI
        data = json.loads(resumen_limpio)
        jugadores_data = data.get('jugadores', [])
        
        # Si no hay 3 jugadores, usar datos de ejemplo
        if len(jugadores_data) < 3:
            raise ValueError("No se obtuvieron 3 jugadores de OpenAI")
            
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"Error parseando JSON de OpenAI: {e}")
        print(f"Respuesta recibida: {resumen_json[:200]}...")
        
        # Datos de fallback en caso de error
        jugadores_data = [
            {
                'nombre': 'ANÁLISIS NO DISPONIBLE',
                'descripcion': 'Error al generar análisis automático. Configure correctamente la API de OpenAI.',
                'fortalezas': [
                    'Error en la generación automática',
                    'Revise la configuración de OpenAI',
                    'Verifique la API key',
                    'Consulte los logs para más detalles'
                ],
                'debilidades': [
                    'No se pudo conectar con el servicio',
                    'Respuesta no válida del LLM',
                    'Configuración incorrecta',
                    'Datos insuficientes'
                ]
            },
            {
                'nombre': 'REVISAR CONFIGURACIÓN',
                'descripcion': 'Para obtener el análisis automático, asegúrese de tener configurada correctamente la API de OpenAI.',
                'fortalezas': [
                    'Sistema de análisis disponible',
                    'Integración con OpenAI implementada',
                    'Formato JSON estructurado',
                    'Fallback funcionando'
                ],
                'debilidades': [
                    'API key no configurada',
                    'Error de conectividad',
                    'Respuesta malformada',
                    'Necesita configuración manual'
                ]
            },
            {
                'nombre': 'DATOS DE PRUEBA',
                'descripcion': 'Estos son datos de ejemplo para mostrar el formato. Configure OpenAI para obtener análisis reales.',
                'fortalezas': [
                    'Layout funcionando correctamente',
                    'Formato visual implementado',
                    'Estructura de datos correcta',
                    'Sistema preparado para datos reales'
                ],
                'debilidades': [
                    'Datos no reales',
                    'Requiere configuración',
                    'Solo para demostración',
                    'No refleja jugadores actuales'
                ]
            }
        ]
    
    # Función para crear la sección de un jugador
    def crear_seccion_jugador(datos_jugador):
        seccion_elements = []
        
        # Nombre del jugador
        nombre = Paragraph(datos_jugador['nombre'], nombre_jugador_style)
        seccion_elements.append(nombre)
        
        # Descripción general
        descripcion = Paragraph(datos_jugador['descripcion'], descripcion_style)
        seccion_elements.append(descripcion)
        seccion_elements.append(Spacer(1, 0.1*inch))
        
        # Fortalezas
        titulo_fortalezas = Paragraph("FORTALEZAS:", titulo_seccion_style)
        seccion_elements.append(titulo_fortalezas)
        
        for fortaleza in datos_jugador['fortalezas']:
            item = Paragraph(f"• {fortaleza}", lista_style)
            seccion_elements.append(item)
        
        seccion_elements.append(Spacer(1, 0.1*inch))
        
        # Debilidades
        titulo_debilidades = Paragraph("DEBILIDADES:", titulo_seccion_style)
        seccion_elements.append(titulo_debilidades)
        
        for debilidad in datos_jugador['debilidades']:
            item = Paragraph(f"• {debilidad}", lista_style)
            seccion_elements.append(item)
        
        return seccion_elements
    
    # Crear las tres secciones de jugadores
    seccion1 = crear_seccion_jugador(jugadores_data[0])
    seccion2 = crear_seccion_jugador(jugadores_data[1])
    seccion3 = crear_seccion_jugador(jugadores_data[2])
    
    # Convertir cada sección en una tabla de una columna para manejar mejor el espaciado
    def seccion_a_tabla(elementos):
        datos_tabla = [[elemento] for elemento in elementos]
        tabla = Table(datos_tabla, colWidths=[3.5*inch])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return tabla
    
    tabla_jugador1 = seccion_a_tabla(seccion1)
    tabla_jugador2 = seccion_a_tabla(seccion2)
    tabla_jugador3 = seccion_a_tabla(seccion3)
    
    # Crear la tabla principal con las tres columnas (jugadores)
    tabla_principal_data = [[tabla_jugador1, tabla_jugador2, tabla_jugador3]]
    
    tabla_principal = Table(tabla_principal_data, 
                           colWidths=[3.7*inch, 3.7*inch, 3.7*inch],  # Ajustado para landscape
                           rowHeights=[6.0*inch])  # Altura aumentada ligeramente para más espacio
    
    tabla_principal.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),  # Bordes suaves
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f7fafc')),  # Fondo jugador 1
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f7fafc')),  # Fondo jugador 2
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#f7fafc')),  # Fondo jugador 3
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),    # Reducido de 15 a 8 para menor altura
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8), # Reducido de 15 a 8 para menor altura
    ]))
    
    story.append(tabla_principal)


def crear_pagina_posicionamiento_competitivo(story, df_grupo, equipo_seleccionado, styles):
    """
    Crea página de posicionamiento competitivo con gráfico ORtg vs DRtg
    """
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    import numpy as np
    import io
    from pathlib import Path
    from reportlab.platypus import Image, PageBreak, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import pandas as pd

    def nombres_similares(nombre1, nombre2):
        """Función auxiliar para comparar nombres de equipos"""
        n1 = nombre1.upper().strip()
        n2 = nombre2.upper().strip()
        return n1 == n2 or n1 in n2 or n2 in n1

    def crear_grafico_ratings(df_equipos, equipo_seleccionado):
        """Crea gráfico de ORtg vs DRtg con logos de equipos"""
        
        # Crear figura con tamaño más pequeño
        fig, ax = plt.subplots(figsize=(12, 8))  # Tamaño reducido
        
        # Obtener datos para los ejes
        x_data = df_equipos['DRtg']  # Defensive Rating (invertido)
        y_data = df_equipos['ORtg']  # Offensive Rating
        
        # Invertir eje X para que mejor DRtg esté a la derecha
        ax.invert_xaxis()
        
        # Configurar márgenes más amplios para evitar solapamientos
        x_margin = (x_data.max() - x_data.min()) * 0.20  # Aumentado de 0.05 a 0.20
        y_margin = (y_data.max() - y_data.min()) * 0.20  # Aumentado de 0.05 a 0.20

        ax.set_xlim(x_data.max() + x_margin, x_data.min() - x_margin)
        ax.set_ylim(y_data.min() - y_margin, y_data.max() + y_margin)
        
        # Añadir líneas de promedio (media de liga)
        avg_ortg = y_data.mean()
        avg_drtg = x_data.mean()
        ax.axhline(y=avg_ortg, color='gray', linestyle='--', alpha=0.7, linewidth=2, 
                   label=f'Media Liga ORtg: {avg_ortg:.1f}')
        ax.axvline(x=avg_drtg, color='gray', linestyle='--', alpha=0.7, linewidth=2,
                   label=f'Media Liga DRtg: {avg_drtg:.1f}')
        
        # Añadir líneas diagonales de iso-Net Rating
        x_range_vals = np.linspace(x_data.min() - x_margin, x_data.max() + x_margin, 100)
        
        # Net Rating = ORtg - DRtg, por lo que ORtg = DRtg + Net Rating
        for net_rating in [-10, 0, 10]:
            y_iso = x_range_vals + net_rating
            ax.plot(x_range_vals, y_iso, '--', alpha=0.4, linewidth=1.5, 
                   color='purple', label=f'Net Rating {net_rating:+d}' if net_rating in [-10, 10] else None)
            
            # Etiqueta de la línea iso
            if avg_drtg - 5 <= x_range_vals.mean() <= avg_drtg + 5:  # Solo si está cerca del centro
                mid_idx = len(x_range_vals) // 2
                ax.text(x_range_vals[mid_idx], y_iso[mid_idx], f'Net {net_rating:+d}', 
                       fontsize=8, alpha=0.6, rotation=-45, ha='center')
        
        # CAJITAS EN LAS ESQUINAS EXTERNAS - FUERA DEL ÁREA DE LA GRÁFICA
        # Obtener los límites reales del área de la gráfica
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Calcular posiciones FUERA del área de datos
        # Usar transform para posicionar en coordenadas de la figura
        
        # Crear fondos suaves semitransparentes para los cuadrantes
        from matplotlib.patches import Rectangle
        
        # Obtener límites de los datos para crear los rectángulos de fondo
        x_range = ax.get_xlim()
        y_range = ax.get_ylim()
        
        # Cuadrante superior derecho: ÉLITE (buen ataque y defensa) - AMARILLO (visualmente arriba izquierda por inversión X)
        rect_elite = Rectangle((avg_drtg, avg_ortg), x_range[0] - avg_drtg, y_range[1] - avg_ortg,
                              facecolor='lightyellow', alpha=0.15, zorder=1)
        ax.add_patch(rect_elite)
        ax.text(0.98, 0.98, 'ÉLITE\n(Buen ataque y defensa)', 
               ha='right', va='top', fontsize=11, fontweight='bold',
               transform=ax.transAxes,
               bbox=dict(boxstyle="round,pad=0.4", facecolor='lightgreen', alpha=0.9, 
                        edgecolor='darkgreen', linewidth=2))
        
        # Cuadrante superior izquierdo: OFENSIVO (buen ataque, mala defensa) - VERDE (visualmente arriba derecha por inversión X)
        rect_ofensivo = Rectangle((x_range[1], avg_ortg), avg_drtg - x_range[1], y_range[1] - avg_ortg,
                                 facecolor='lightgreen', alpha=0.15, zorder=1)
        ax.add_patch(rect_ofensivo)
        ax.text(0.02, 0.98, 'OFENSIVO\n(Buen ataque, mala defensa)', 
               ha='left', va='top', fontsize=11, fontweight='bold',
               transform=ax.transAxes,
               bbox=dict(boxstyle="round,pad=0.4", facecolor='lightyellow', alpha=0.9, 
                        edgecolor='goldenrod', linewidth=2))
        
        # Cuadrante inferior derecho: DEFENSIVO (mal ataque, buena defensa) - AZUL (visualmente abajo izquierda por inversión X)
        rect_defensivo = Rectangle((avg_drtg, y_range[0]), x_range[0] - avg_drtg, avg_ortg - y_range[0],
                                  facecolor='lightcoral', alpha=0.15, zorder=1)
        ax.add_patch(rect_defensivo)
        ax.text(0.98, 0.02, 'DEFENSIVO\n(Mal ataque, buena defensa)', 
               ha='right', va='bottom', fontsize=11, fontweight='bold',
               transform=ax.transAxes,
               bbox=dict(boxstyle="round,pad=0.4", facecolor='lightblue', alpha=0.9, 
                        edgecolor='darkblue', linewidth=2))
        
        # Cuadrante inferior izquierdo: NECESITA MEJORAR (mal ataque y defensa) - ROJO (visualmente abajo derecha por inversión X)
        rect_mejorar = Rectangle((x_range[1], y_range[0]), avg_drtg - x_range[1], avg_ortg - y_range[0],
                                facecolor='lightblue', alpha=0.15, zorder=1)
        ax.add_patch(rect_mejorar)
        ax.text(0.02, 0.02, 'NECESITA MEJORAR\n(Mal ataque y defensa)', 
               ha='left', va='bottom', fontsize=11, fontweight='bold',
               transform=ax.transAxes,
               bbox=dict(boxstyle="round,pad=0.4", facecolor='lightcoral', alpha=0.9, 
                        edgecolor='darkred', linewidth=2))
        
        # Colocar fotos de equipos con tamaño estandarizado y anti-solapamiento
        zoom_estandar = 0.11  # Tamaño uniforme más pequeño para evitar solapamientos
        
        # Función para detectar y resolver solapamientos
        def resolver_solapamientos(df_equipos, zoom):
            """Ajusta posiciones para evitar solapamientos de logos"""
            posiciones = []
            x_extent = zoom * (x_data.max() - x_data.min())
            y_extent = zoom * (y_data.max() - y_data.min())
            
            for _, row in df_equipos.iterrows():
                x_orig = row['DRtg']
                y_orig = row['ORtg']
                x_adj = x_orig
                y_adj = y_orig
                
                # Comprobar solapamientos significativos con equipos ya posicionados
                for i, (x_prev, y_prev, _, _) in enumerate(posiciones):
                    dist_x = abs(x_adj - x_prev)
                    dist_y = abs(y_adj - y_prev)
                    
                    # Calcular el porcentaje de solapamiento
                    # Si la distancia es menor que 0.6 del tamaño, hay solapamiento significativo (>60%)
                    overlap_threshold_x = x_extent * 0.6  # 60% de solapamiento en X
                    overlap_threshold_y = y_extent * 0.6  # 60% de solapamiento en Y
                    
                    # Solo separar si hay solapamiento significativo en AMBAS dimensiones
                    if dist_x < overlap_threshold_x and dist_y < overlap_threshold_y:
                        # Mover el equipo actual solo un poquito para desenredar
                        if x_adj >= x_prev:  # Mover ligeramente a la derecha
                            x_adj = x_prev + x_extent * 1.1
                        else:  # Mover ligeramente a la izquierda
                            x_adj = x_prev - x_extent * 1.1
                            
                        if y_adj >= y_prev:  # Mover ligeramente arriba
                            y_adj = y_prev + y_extent * 1.1
                        else:  # Mover ligeramente abajo
                            y_adj = y_prev - y_extent * 1.1
                
                posiciones.append((x_adj, y_adj, x_orig, y_orig))
            
            return posiciones
        
        # Resolver solapamientos
        posiciones_ajustadas = resolver_solapamientos(df_equipos, zoom_estandar)
        
        for i, (_, row) in enumerate(df_equipos.iterrows()):
            nombre_equipo = row['Equipo']
            x_pos, y_pos, x_orig, y_orig = posiciones_ajustadas[i]
            es_equipo_seleccionado = nombres_similares(nombre_equipo, equipo_seleccionado)
            
            # Obtener la ruta del logo desde la columna logo_path del dataframe
            imagen_path = None
            if 'logo_path' in row and pd.notna(row['logo_path']) and row['logo_path']:
                logo_path = Path(row['logo_path'])
                if logo_path.exists():
                    imagen_path = logo_path
            
            if imagen_path:
                try:
                    # Cargar y redimensionar imagen
                    img = mpimg.imread(imagen_path)
                    # Corregir el espejo invirtiendo horizontalmente
                    img = np.fliplr(img)
                    
                    # Usar tamaño más grande para el equipo seleccionado
                    if es_equipo_seleccionado:
                        zoom = zoom_estandar * 1.3  # 30% más grande
                    else:
                        zoom = zoom_estandar
                    
                    # Calcular extensión de la imagen
                    x_extent = zoom * (x_data.max() - x_data.min())
                    y_extent = zoom * (y_data.max() - y_data.min())
                    
                    extent = [x_pos - x_extent/2, x_pos + x_extent/2, 
                             y_pos - y_extent/2, y_pos + y_extent/2]
                    
                    # Mostrar la imagen primero (fondo)
                    ax.imshow(img, extent=extent, aspect='auto', zorder=10)
                    
                    # Solo destacado para el equipo seleccionado - únicamente borde rojo
                    if es_equipo_seleccionado:
                        # Borde rojo simple alrededor del logo
                        from matplotlib.patches import FancyBboxPatch
                        fancy_box = FancyBboxPatch((x_pos - x_extent/2, y_pos - y_extent/2), 
                                                  x_extent, y_extent,
                                                  boxstyle="round,pad=0.02", 
                                                  facecolor='none', edgecolor='red', 
                                                  linewidth=3, alpha=0.9, zorder=11)
                        ax.add_patch(fancy_box)
                    
                except Exception as e:
                    # Si hay error cargando la imagen, usar punto coloreado
                    if es_equipo_seleccionado:
                        ax.scatter(x_pos, y_pos, s=400, c='blue', alpha=0.9, zorder=15, 
                                 marker='o', edgecolors='red', linewidth=3)  # Más grande
                    else:
                        ax.scatter(x_pos, y_pos, s=120, c='blue', alpha=0.7, zorder=10)
            else:
                # Si no hay imagen, usar punto coloreado
                if es_equipo_seleccionado:
                    ax.scatter(x_pos, y_pos, s=400, c='blue', alpha=0.9, zorder=15, 
                             marker='o', edgecolors='red', linewidth=3)  # Más grande
                else:
                    ax.scatter(x_pos, y_pos, s=120, c='blue', alpha=0.7, zorder=10)
        
        # Configurar etiquetas y título corregidos
        ax.set_xlabel('Defensive Rating (mejor defensa →)', fontsize=12, weight='bold')
        ax.set_ylabel('Offensive Rating (mejor hacia arriba)', fontsize=12, weight='bold')
        ax.set_title('POSICIONAMIENTO COMPETITIVO', fontsize=24, weight='bold', pad=25)
        
        # Añadir grid sutil
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        
        # Ajustar diseño
        plt.tight_layout()
        
        # Guardar en memoria como imagen
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        img_buffer.seek(0)
        plt.close()  # Cerrar para liberar memoria
        
        return img_buffer

    # Cambiar a landscape para esta página
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate('landscape'))
    story.append(PageBreak())
    
    # Sin título de página - el título irá en el gráfico más grande
    
    # Crear el gráfico
    grafico_buffer = crear_grafico_ratings(df_grupo, equipo_seleccionado)
    
    # Convertir buffer a Image para ReportLab - Tamaño más pequeño
    imagen_grafico = Image(grafico_buffer, width=8*inch, height=6*inch)  # Tamaño reducido
    imagen_grafico.hAlign = 'CENTER'
    story.append(imagen_grafico)
    
    # Añadir explicación mejorada con contexto
    explicacion_style = ParagraphStyle(
        'Explicacion',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#555555')
    )
    
    # Calcular algunos estadísticos para el contexto
    num_equipos = len(df_grupo)
    avg_ortg = df_grupo['ORtg'].mean()
    avg_drtg = df_grupo['DRtg'].mean()
    
    explicacion_principal = Paragraph(
        f"<b>Análisis de {num_equipos} equipos</b> según rendimiento ofensivo (eje vertical) y defensivo (eje horizontal, mejor hacia la derecha).<br/>"
        f"Las líneas divisorias representan la media de liga: ORtg {avg_ortg:.1f} | DRtg {avg_drtg:.1f}.<br/>"
        "Las líneas diagonales muestran equipos con igual Net Rating (ORtg - DRtg).", 
        explicacion_style
    )
    
    contexto_style = ParagraphStyle(
        'Contexto',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#777777')
    )
    
    import datetime
    temporada_actual = datetime.datetime.now().year
    # pie_contexto = Paragraph(
    #     f"Temporada {temporada_actual} | Posesiones ajustadas por 100 posesiones | Logos estandarizados", 
    #     contexto_style
    # )
    
    story.append(Spacer(1, 15))
    story.append(explicacion_principal)
    story.append(Spacer(1, 8))
    #story.append(pie_contexto)
    
    # Forzar salto de página para que la siguiente página use el template landscape
    story.append(PageBreak())


def generar_shot_charts_elements(liga, grupo, equipo, datos_json_path=DEFAULT_DATOS_JSON, 
                                results_csv_path=DEFAULT_RESULTS_CSV, court_image_path=DEFAULT_COURT_IMAGE,
                                jugadores=None, max_matches=None, temporada="2025"):
    """
    Genera los elementos de shot charts para añadir al PDF final
    """
    print("🏀 Generando shot charts...")
    
    # Obtener datos del equipo y shots usando la función existente
    ensure_dir(DEFAULT_OUTPUT_DIR)
    eq = select_team_from_datos(datos_json_path, liga=liga, grupo=grupo, equipo=equipo, temporada=temporada)
    url_equipo = coerce_str(eq.get('url_equipo'))
    
    plantilla = eq.get('jugadores') or []
    plantilla_ids: Dict[str, str] = {}
    for p in plantilla:
        pid = parse_qs_param(coerce_str(p.get('enlace')), 'c')
        if pid:
            plantilla_ids[pid] = coerce_str(p.get('nombre'))
    
    # Selección de jugadores
    if jugadores:
        target_ids = set()
        by_name = {coerce_str(n).lower(): pid for pid, n in plantilla_ids.items()}
        for j in jugadores:
            j_raw = coerce_str(j)
            if re.fullmatch(r"\d+", j_raw):
                if j_raw in plantilla_ids:
                    target_ids.add(j_raw)
            else:
                pid = by_name.get(j_raw.lower())
                if pid:
                    target_ids.add(pid)
        if not target_ids:
            raise RuntimeError("Ningún elemento de 'jugadores' coincide con la plantilla del equipo.")
    else:
        target_ids = set(plantilla_ids.keys())
    
    # Obtener partidos
    df = load_results_csv(results_csv_path)
    subset = filter_matches_by_team_url(df, url_equipo)
    if subset.empty:
        raise RuntimeError("No se encontraron partidos para ese equipo.")
    if max_matches and max_matches > 0:
        subset = subset.tail(max_matches)
    
    print(f"Equipo: {eq.get('nombre')} | Partidos: {len(subset)}")
    
    # Acumular tiros por jugador
    scraper = ShotChartScraper()
    acumulado_por_player: Dict[str, List[Dict]] = {}
    nombre_por_player: Dict[str, str] = {}
    numero_por_player: Dict[str, str] = {}
    
    for _, row in subset.iterrows():
        pid = coerce_str(row['partido_id'])
        team_idx = int(row['team_idx'])
        try:
            full_data = scraper.get_shot_chart_data(pid)
            shots_data = scraper.extract_shots_data(full_data)
            if not shots_data:
                continue
                
            # Obtener mapa de jugadores con números de camiseta
            dorsal_map = build_player_maps_for_team(shots_data, team_idx)
            
            acc = accumulate_player_shots_from_match(pid, shots_data, team_idx, target_player_ids=target_ids)
            union_shotlists(acumulado_por_player, acc)
            
            # Actualizar nombres y números de camiseta
            for pl_id in acc.keys():
                if pl_id in plantilla_ids:
                    nombre_por_player[pl_id] = plantilla_ids[pl_id]
                
                # Buscar número de camiseta en el mapa dorsal
                for dorsal, info in dorsal_map.items():
                    if info['player_id'] == pl_id:
                        numero_por_player[pl_id] = dorsal
                        break
            
            print(f"[{pid}] ✓ Tiros procesados")
        except Exception as e:
            print(f"[{pid}] ❌ Error: {e}")
    
    if not acumulado_por_player:
        print("⚠️ No se encontraron datos de tiros, saltando shot charts")
        return []
    
    print(f"📊 Procesando {len(acumulado_por_player)} jugadores...")
    
    # Generar elementos para el PDF
    elements = []
    
    # Asegurar que se use la plantilla con watermark para shot charts (sin PageBreak para evitar página en blanco)
    from reportlab.platypus import NextPageTemplate
    elements.append(NextPageTemplate('landscape'))
    
    # Título de shot charts
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=10,
        alignment=1,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#2d3748')
    )
    
    title = Paragraph("SHOT CHARTS - ANÁLISIS DE TIROS", title_style)
    elements.append(title)
    elements.append(Spacer(1, 5*mm))
    
    # Procesar jugadores y generar celdas
    player_cells = []
    for pl_id, shots_list in acumulado_por_player.items():
        pl_name = nombre_por_player.get(pl_id, f"player_{pl_id}")
        pl_number = numero_por_player.get(pl_id, "")
        print(f"📸 Procesando {pl_name} (#{pl_number}) - ID: {pl_id}...")
        
        try:
            # Generar gráfica de tiros en buffer
            chart_buffer = plot_player_shots_to_buffer(
                court_image_path=court_image_path,
                shots_list=shots_list,
                player_id=pl_id,
                rotate_ccw90=False,  # Nueva versión usa False por defecto
                point_size=120  # Puntos más grandes para mejor visibilidad
            )
            
            # Obtener foto del jugador en buffer
            photo_buffer = get_player_photo_buffer(pl_id)
            
            # Crear celda usando buffers con nombre y número
            player_cell = create_player_cell_from_buffers(pl_name, pl_number, photo_buffer, chart_buffer)
            player_cells.append(player_cell)
            
            # Limitar a 12 jugadores para que quepa en el PDF
            if len(player_cells) >= 12:
                break
        except Exception as e:
            print(f"❌ Error procesando {pl_name}: {e}")
            continue
    
    if not player_cells:
        print("⚠️ No se pudieron generar shot charts")
        return elements
    
    # Crear tabla principal (4 columnas para formato landscape)
    table_data = []
    for i in range(0, len(player_cells), 4):
        row = []
        for j in range(4):
            if i + j < len(player_cells):
                row.append(player_cells[i + j])
            else:
                row.append("")  # Celda vacía
        table_data.append(row)
    
    main_table = Table(
        table_data,
        colWidths=[63*mm, 63*mm, 63*mm, 63*mm],  # Mantenemos el mismo tamaño: 4 columnas de 63mm
        rowHeights=[50*mm] * len(table_data)  # Aumentamos altura para acomodar imagen de pista más grande
    )
    
    main_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    elements.append(main_table)
    
    return elements


def seleccionar_mejores_jugadores_para_shotcharts(df_jugadores_norm, top_n=12):
    """
    Selecciona los mejores jugadores para shot charts usando criterio consistente con estadísticas individuales.
    
    1. Primero filtra jugadores que han jugado >= 25% de los partidos del equipo
    2. Si hay más de 12, selecciona los mejores por score combinado (60% puntos + 40% valoración)
    
    Args:
        df_jugadores_norm: DataFrame con jugadores normalizados
        top_n: Número máximo de jugadores a seleccionar (default: 12)
        
    Returns:
        List[str]: Lista de IDs de los mejores jugadores
    """
    if df_jugadores_norm.empty:
        return []
    
    # Filtrar jugadores con datos válidos
    df_validos = df_jugadores_norm.dropna(subset=['PTS/PJ', 'VAL/PJ', 'ID', 'PJ']).copy()
    
    if df_validos.empty:
        return []
    
    # 1. FILTRO POR UMBRAL DE PARTIDOS (>=25% como en estadísticas individuales)
    # Calcular el número total de partidos del equipo (máximo de partidos jugados por cualquier jugador)
    partidos_equipo = df_validos['PJ'].max()
    umbral_partidos = partidos_equipo * 0.25  # 25% de los partidos
    
    # Filtrar jugadores principales (>=25% partidos)
    df_principales = df_validos[df_validos['PJ'] >= umbral_partidos].copy()
    
    if df_principales.empty:
        print(f"⚠️ No hay jugadores con >= {umbral_partidos:.1f} partidos (25% de {partidos_equipo})")
        return []
    
    print(f"📊 Jugadores principales para shot charts: {len(df_principales)} (>= {umbral_partidos:.1f} partidos)")
    
    # 2. SI HAY MÁS DE 12, APLICAR CRITERIO DE SELECCIÓN
    if len(df_principales) <= top_n:
        # Si hay 12 o menos, tomar todos los principales
        mejores_ids = df_principales['ID'].astype(str).tolist()
        print(f"✅ Seleccionados todos los {len(mejores_ids)} jugadores principales")
    else:
        # Si hay más de 12, aplicar criterio de puntos + valoración
        print(f"🎯 Aplicando criterio de selección (60% PTS + 40% VAL) para reducir de {len(df_principales)} a {top_n}")
        
        # Crear score combinado: 60% puntos + 40% valoración (ambos por partido)
        # Normalizar las estadísticas para que tengan el mismo peso
        pts_max = df_principales['PTS/PJ'].max() if df_principales['PTS/PJ'].max() > 0 else 1
        val_max = df_principales['VAL/PJ'].max() if df_principales['VAL/PJ'].max() > 0 else 1
        
        df_principales['PTS_norm'] = df_principales['PTS/PJ'] / pts_max
        df_principales['VAL_norm'] = df_principales['VAL/PJ'] / val_max
        
        # Score combinado: 60% puntos + 40% valoración
        df_principales['Score_Shotchart'] = (df_principales['PTS_norm'] * 0.6) + (df_principales['VAL_norm'] * 0.4)
        
        # Ordenar por score descendente y tomar los mejores
        df_ordenado = df_principales.sort_values('Score_Shotchart', ascending=False)
        
        # Obtener los IDs de los mejores jugadores
        mejores_ids = df_ordenado['ID'].astype(str).head(top_n).tolist()
        print(f"✅ Seleccionados top {len(mejores_ids)} jugadores por criterio combinado")
    
    return mejores_ids


def cargar_datos_temporada(JSON_PATH, temporada="2025"):
    """
    Carga datos desde archivo histórico multi-temporada o archivo simple.
    
    Args:
        JSON_PATH: Ruta al archivo JSON (puede ser datos_historicos.json o datos2.json)
        temporada: Temporada a extraer (default: "2025")
    
    Returns:
        Diccionario con datos de la temporada especificada
    """
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Detectar si es archivo histórico multi-temporada
    if "temporadas" in data:
        print(f"📚 Archivo histórico detectado. Extrayendo temporada {temporada}...")
        if temporada not in data["temporadas"]:
            raise ValueError(f"Temporada {temporada} no encontrada. Disponibles: {list(data['temporadas'].keys())}")
        return data["temporadas"][temporada]
    else:
        # Archivo simple (formato antiguo)
        print(f"📄 Archivo simple detectado (formato antiguo)")
        return data


def cargar_historial_jugador(jugador_id, JSON_PATH, temporada_actual="2025"):
    """
    Busca el historial de un jugador en temporadas anteriores.
    
    Args:
        jugador_id: ID del jugador (código FEB)
        JSON_PATH: Ruta al archivo JSON histórico
        temporada_actual: Temporada actual (para excluirla de búsqueda)
    
    Returns:
        Dict con información de temporadas anteriores o None si no hay historial
    """
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            datos_completos = json.load(f)
        
        # Solo funciona con archivo histórico
        if "temporadas" not in datos_completos:
            return None
        
        historial = {}
        
        # Buscar en todas las temporadas excepto la actual
        for year, datos_year in datos_completos["temporadas"].items():
            if year == temporada_actual:
                continue
            
            # Buscar jugador en esta temporada
            for categoria_nombre, categoria_data in datos_year.get("categorias", {}).items():
                for grupo_nombre, grupo_data in categoria_data.get("grupos", {}).items():
                    for equipo in grupo_data.get("equipos", []):
                        for jugador in equipo.get("jugadores", []):
                            # Comparar por ID extraído del enlace
                            jugador_enlace = jugador.get("enlace", "")
                            if f"c={jugador_id}" in jugador_enlace:
                                historial[year] = {
                                    "jugador": jugador,
                                    "equipo": equipo.get("nombre"),
                                    "categoria": categoria_nombre,
                                    "grupo": grupo_nombre
                                }
                                break
        
        return historial if historial else None
        
    except Exception as e:
        print(f"⚠️ Error buscando historial de jugador {jugador_id}: {e}")
        return None


def generar_pdf_final(JSON_PATH, liga, grupo, equipo, datos_json_path=None, results_csv_path=None, 
                     court_image_path=None, jugadores=None, max_matches=None, temporada="2025"):
    """
    Función principal que genera el PDF final combinando informe estadístico y shot charts.
    Soporta archivos históricos multi-temporada.
    
    Args:
        JSON_PATH: Ruta al archivo JSON con datos estadísticos (puede ser datos_historicos.json)
        liga: Nombre de la liga
        grupo: Nombre del grupo
        equipo: Nombre del equipo
        datos_json_path: Ruta al archivo datos.json (para shot charts)
        results_csv_path: Ruta al archivo CSV de resultados (para shot charts)
        court_image_path: Ruta a la imagen de la pista (para shot charts)
        jugadores: Lista de jugadores específicos (opcional)
        max_matches: Límite de partidos (opcional)
        temporada: Temporada a procesar (default: "2025")
        
    Returns:
        Ruta del archivo PDF generado
    """
    print("🏀 Iniciando generación de PDF final combinado...")
    print(f"📅 Temporada: {temporada}")
    
    # Configurar rutas por defecto para shot charts si no se proporcionan
    if datos_json_path is None:
        datos_json_path = JSON_PATH
    if results_csv_path is None:
        results_csv_path = DEFAULT_RESULTS_CSV
    if court_image_path is None:
        court_image_path = DEFAULT_COURT_IMAGE
    
    # 1) Cargar JSON y procesar datos estadísticos
    # Usar función helper que detecta formato automáticamente
    data = cargar_datos_temporada(JSON_PATH, temporada=temporada)

    # Navegar por las claves EXACTAS
    nodo_categoria = data["categorias"][liga]
    nodo_grupo = nodo_categoria["grupos"][grupo]
    equipos = nodo_grupo["equipos"]

    df_all = pd.json_normalize(equipos, sep=".")
    df_grupo = normalizar_dataframe(df_all)

    # Aplicar funciones de procesamiento al dataframe de grupo
    df_grupo = cargar_logos_equipos(df_grupo)
    df_grupo = calcular_estadisticas_avanzadas(df_grupo)

    # Extraer estadísticas individuales de los jugadores del equipo seleccionado
    equipo_data = df_grupo[df_grupo['Equipo'] == equipo].iloc[0]
    jugadores_raw = equipo_data['Jugadores']

    # Convertir lista de jugadores a DataFrame
    df_jugadores = pd.json_normalize(jugadores_raw)

    # Aplicar normalización a las estadísticas de jugadores
    df_jugadores_norm = normalizar_estadisticas_jugadores(df_jugadores)

    # Descargar fotos de jugadores
    df_jugadores_norm = descargar_fotos_jugadores(df_jugadores_norm, equipo)

    # Filtrar jugadores según porcentaje de partidos jugados
    partidos_equipo = equipo_data['PJ']
    umbral_partidos = partidos_equipo * 0.25  # 25% de los partidos
    
    # Dividir jugadores en principales y apoyo
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    # Recalcular estadísticas con USG% corregido
    df_jugadores_norm_corrigido = calcular_usg_correcto(df_jugadores_norm)
    df_jugadores_norm = df_jugadores_norm_corrigido.copy()
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] > umbral_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] <= umbral_partidos].copy()

    # No es necesario volver a descargar fotos, ya se descargaron antes
    # La columna 'foto_path' ya está en df_jugadores_norm

    # Crear rankings de jugadores y equipos
    rankings = crear_rankings_jugadores(df_principales)
    rankings_equipos = crear_rankings_equipos(df_grupo)

    # 2) Configurar documento PDF final
    output_filename = f"reportes/informe_final_{equipo}.pdf"
    
    # Asegurar que existe el directorio de reportes
    os.makedirs("reportes", exist_ok=True)
    
    # Importar lo necesario para las plantillas de páginas
    from reportlab.platypus.doctemplate import PageTemplate, Frame
    from reportlab.platypus.flowables import Image as ReportLabImage
    
    # Función para crear el watermark
    def crear_watermark_pi_scouting(canvas, doc):
        """Dibuja el watermark del logo PI Scouting en la parte inferior de la página"""
        # Detectar si estamos ejecutando desde notebooks o desde raíz
        from pathlib import Path
        current_dir = Path.cwd()
        if current_dir.name == 'notebooks':
            logo_pi_path = current_dir.parent / "data" / "logo_PI_scouting_resize.jpeg"
        else:
            logo_pi_path = Path("data") / "logo_PI_scouting_resize.jpeg"
        
        if logo_pi_path.exists():
            try:
                # Guardar el estado actual del canvas
                canvas.saveState()
                
                # Hacer el logo semi-transparente
                canvas.setFillAlpha(0.3)  # 30% de opacidad
                
                # Tamaño del watermark (aumentado para mayor visibilidad)
                watermark_size = 25*mm  # Aumentado de 15mm a 25mm para mayor presencia
                
                # Posición: centrado horizontalmente, en la parte inferior
                page_width = A4[1]  # Landscape width
                x = (page_width - watermark_size) / 2
                y = 5*mm  # 5mm desde el borde inferior
                
                # Dibujar el logo
                canvas.drawImage(
                    str(logo_pi_path), 
                    x, y, 
                    width=watermark_size, 
                    height=watermark_size,
                    preserveAspectRatio=True
                )
                
                # Restaurar el estado del canvas
                canvas.restoreState()
            except Exception as e:
                # Si hay error, no dibujar nada
                pass
    
    # Crear el documento base EN LANDSCAPE FORZADO - TODAS LAS PÁGINAS LANDSCAPE
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=(A4[1], A4[0]),  # FORZAR LANDSCAPE: intercambiar ancho y alto
        leftMargin=10*mm,
        rightMargin=10*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Crear frames para ambas plantillas
    frame_landscape = Frame(
        doc.leftMargin, 
        doc.bottomMargin, 
        (A4[1] - (doc.leftMargin + doc.rightMargin)),  # Ancho landscape
        (A4[0] - (doc.topMargin + doc.bottomMargin)),  # Alto landscape
        id='landscape_frame'
    )
    
    # Plantilla para la primera página (sin watermark)
    primera_pagina_template = PageTemplate(
        id='primera_pagina', 
        frames=[frame_landscape], 
        pagesize=(A4[1], A4[0])
    )
    
    # Plantilla para el resto de páginas (con watermark)
    landscape_template = PageTemplate(
        id='landscape', 
        frames=[frame_landscape], 
        pagesize=(A4[1], A4[0]),
        onPage=crear_watermark_pi_scouting
    )
    
    # Registrar ambas plantillas
    doc.addPageTemplates([primera_pagina_template, landscape_template])
    
    # Obtener URL del equipo y datos para números de jugadores
    equipo_url = None
    df_resultados = None
    try:
        eq = select_team_from_datos(datos_json_path or DEFAULT_DATOS_JSON, liga=liga, grupo=grupo, equipo=equipo, temporada=temporada)
        equipo_url = coerce_str(eq.get('url_equipo'))
        df_resultados = load_results_csv(results_csv_path or DEFAULT_RESULTS_CSV)
        print(f"📋 URL del equipo obtenido: {equipo_url}")
    except Exception as e:
        print(f"⚠️ No se pudo obtener URL del equipo: {e}")
    
    # 3) Generar elementos del informe estadístico
    print("📊 Generando informe estadístico...")
    elementos_informe = generar_pdf_informe(
        equipo_data=equipo_data,
        df_jugadores_norm=df_jugadores_norm,
        df_principales=df_principales,
        df_apoyo=df_apoyo,
        rankings=rankings,
        df_grupo=df_grupo,
        rankings_equipos=rankings_equipos,
        filename=None,  # No generar archivo, solo retornar elementos
        equipo_url=equipo_url,  # Nuevo parámetro
        df_resultados=df_resultados,  # Nuevo parámetro
        JSON_PATH=JSON_PATH,  # Nuevo parámetro para historial
        temporada=temporada,  # Nuevo parámetro para temporada actual
        liga=liga  # Nuevo parámetro para filtrar partidos por liga
    )
    
    # 4) Generar elementos de shot charts
    print("🎯 Generando shot charts...")
    elementos_shot_charts = []
    try:
        # Si no se especificaron jugadores, seleccionar automáticamente los mejores
        jugadores_shotcharts = jugadores
        if jugadores_shotcharts is None:
            print("🤖 Seleccionando automáticamente los mejores jugadores para shot charts...")
            mejores_ids = seleccionar_mejores_jugadores_para_shotcharts(df_jugadores_norm, top_n=12)
            jugadores_shotcharts = mejores_ids
            print(f"✅ Seleccionados {len(mejores_ids)} jugadores para shot charts")
        
        elementos_shot_charts = generar_shot_charts_elements(
            liga=liga,
            grupo=grupo,
            equipo=equipo,
            datos_json_path=datos_json_path,
            results_csv_path=results_csv_path,
            court_image_path=court_image_path,
            jugadores=jugadores_shotcharts,  # ← Usar la selección inteligente
            max_matches=max_matches,
            temporada=temporada  # ← Pasar temporada para archivos históricos
        )
    except Exception as e:
        print(f"⚠️ Error generando shot charts: {e}")
        print("Continuando solo con el informe estadístico...")
    
    # 5) Combinar todos los elementos EN EL ORDEN CORRECTO
    story = []
    
    # Añadir elementos del informe estadístico
    if isinstance(elementos_informe, list):
        # Los shot charts van después de "estadísticas individuales" y "estadísticas individuales (cont.)" y antes de "análisis y resumen"
        
        story_temp = []
        shot_charts_insertados = False
        
        for i, elemento in enumerate(elementos_informe):
            story_temp.append(elemento)
            
            # Buscar si el elemento actual es un título que indica análisis/resumen del equipo
            # Esto asegura que los shot charts se inserten después de todas las estadísticas individuales
            if hasattr(elemento, 'text') and 'ANÁLISIS' in str(elemento.text).upper():
                # Insertar shot charts justo antes del análisis del equipo
                if elementos_shot_charts and not shot_charts_insertados:
                    story_temp.extend(elementos_shot_charts)
                    shot_charts_insertados = True
        
        # Si no se encontró el lugar específico, añadir shot charts al final del informe
        if elementos_shot_charts and not shot_charts_insertados:
            story_temp.extend(elementos_shot_charts)
        
        story.extend(story_temp)
    else:
        # Fallback: añadir en orden simple
        if isinstance(elementos_informe, list):
            story.extend(elementos_informe)
        if elementos_shot_charts:
            story.extend(elementos_shot_charts)
    
    # 6) Generar PDF final
    try:
        doc.build(story)
        print(f"✅ PDF final generado: {output_filename}")
        
        # Post-procesado: eliminar páginas en blanco
        pdf_limpio = eliminar_paginas_en_blanco_pdf(output_filename)
        
        return pdf_limpio
    except Exception as e:
        print(f"❌ Error generando PDF final: {e}")
        raise


def main():
    """Función principal para pruebas"""
    from pathlib import Path

    # Configuración (ajusta estos valores según tus datos)
    # Usar archivo histórico por defecto, fallback a datos2.json si no existe
    JSON_PATH_HISTORICO = Path("data") / "datos_historicos.json"
    JSON_PATH_ANTIGUO = Path("data") / "datos2.json"
    
    if JSON_PATH_HISTORICO.exists():
        JSON_PATH = JSON_PATH_HISTORICO
        temporada = "2025"  # Usar datos de temporada 2025
        print(f"📚 Usando archivo histórico: {JSON_PATH}")
    else:
        JSON_PATH = JSON_PATH_ANTIGUO
        temporada = None  # Archivo antiguo no tiene temporadas
        print(f"📄 Usando archivo antiguo: {JSON_PATH}")
    
    liga = "3ª FEB"
    grupo = "Liga Regular \"E-A\""
    equipo = "CB MORVEDRE"
    
    # Configuración adicional para shot charts (opcional)
    datos_json_path = JSON_PATH  # Usar el mismo JSON
    results_csv_path = Path("data") / "datos_completos.csv"
    court_image_path = Path("data") / "basket_court_edited.png"
    
    print(f"Ruta del JSON: {JSON_PATH.absolute()}")
    
    try:
        pdf_path = generar_pdf_final(
            JSON_PATH=JSON_PATH,
            liga=liga,
            grupo=grupo,
            equipo=equipo,
            datos_json_path=datos_json_path,
            results_csv_path=results_csv_path,
            court_image_path=court_image_path,
            jugadores=None,  # Todos los jugadores
            max_matches=None,  # Todos los partidos
            temporada=temporada if temporada else "2025"
        )
        print(f"🎉 PDF final generado exitosamente: {pdf_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()