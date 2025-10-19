# -*- coding: utf-8 -*-
"""
Generación de PDFs de scouting de baloncesto
- Generación de reportes de equipo en formato PDF
- Manejo de imágenes y gráficas en memoria (buffers)
- Creación de celdas de jugadores con foto y shot chart

Este módulo se encarga exclusivamente de la generación de PDFs,
separado de la lógica de scraping y análisis de datos.
"""

import os
import io
import re
from typing import List, Dict, Optional, Any

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus.flowables import Image as ReportLabImage

# Importar funciones necesarias del módulo de scraping
from scrapping_folder.shortchart_class_anterior import (
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


def pil_buffer_to_reportlab_image(img_buffer: io.BytesIO, width, height):
    """Convierte buffer PIL a imagen ReportLab"""
    img_buffer.seek(0)
    return ReportLabImage(img_buffer, width=width, height=height)


def create_player_cell_from_buffers(player_name: str, player_number: str, photo_buffer: io.BytesIO, chart_buffer: io.BytesIO):
    """Crea celda de jugador usando buffers en memoria"""
    # Convertir buffers a imágenes ReportLab (foto más pequeña)
    photo_img = pil_buffer_to_reportlab_image(photo_buffer, width=20*mm, height=25*mm)
    chart_img = pil_buffer_to_reportlab_image(chart_buffer, width=35*mm, height=32*mm)
    
    # Crear texto con número y nombre
    if player_number and player_number.strip():
        display_text = f"#{player_number} - {player_name}"
    else:
        display_text = player_name
    
    # Crear tabla interna
    player_content = [
        [display_text, ""],  # Nombre del jugador (y número si disponible)
        [photo_img, chart_img]  # Foto | Gráfica
    ]
    
    player_table = Table(player_content, colWidths=[25*mm, 35*mm], rowHeights=[8*mm, 35*mm])
    player_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (1, 0), 8),  # Tamaño un poco más pequeño para que quepa
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    return player_table


def generate_team_scouting_pdf(
    liga: str,
    grupo: str,
    equipo: str,
    output_filename: str = None,
    datos_json_path: str = DEFAULT_DATOS_JSON,
    results_csv_path: str = DEFAULT_RESULTS_CSV,
    court_image_path: str = DEFAULT_COURT_IMAGE,
    jugadores: Optional[List[str]] = None,
    max_matches: Optional[int] = None
) -> str:
    """
    Función unificada que genera el PDF de scouting directamente sin archivos intermedios.
    
    Args:
        liga: Nombre de la liga
        grupo: Nombre del grupo
        equipo: Nombre del equipo
        output_filename: Nombre del archivo PDF (opcional)
        datos_json_path: Ruta al archivo datos.json
        results_csv_path: Ruta al archivo CSV de resultados
        court_image_path: Ruta a la imagen de la pista
        jugadores: Lista de jugadores específicos (opcional)
        max_matches: Límite de partidos (opcional)
        
    Returns:
        Ruta del archivo PDF generado
    """
    print("🏀 Iniciando generación de PDF de scouting...")
    
    # 1) Obtener datos del equipo y shots usando la función existente
    ensure_dir(DEFAULT_OUTPUT_DIR)
    eq = select_team_from_datos(datos_json_path, liga=liga, grupo=grupo, equipo=equipo)
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
    numero_por_player: Dict[str, str] = {}  # Para guardar números de camiseta
    
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
        raise RuntimeError("No se encontraron datos de tiros.")
    
    print(f"📊 Procesando {len(acumulado_por_player)} jugadores...")
    
    # 2) Generar PDF usando buffers en memoria
    if output_filename is None:
        team_name = eq.get('nombre', 'EQUIPO')
        output_filename = os.path.join(DEFAULT_OUTPUT_DIR, f"Scouting {team_name}.pdf")
    
    # Configurar documento PDF
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        leftMargin=10*mm,
        rightMargin=10*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    elements = []
    
    # Título
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=10,
        alignment=1,
        fontName='Helvetica-Bold'
    )
    
    title = Paragraph(f"{eq.get('nombre')} - SCOUTING JUGADORES", title_style)
    elements.append(title)
    elements.append(Spacer(1, 5*mm))
    
    # Procesar jugadores y generar celdas
    player_cells = []
    for pl_id, shots_list in acumulado_por_player.items():
        pl_name = nombre_por_player.get(pl_id, f"player_{pl_id}")
        pl_number = numero_por_player.get(pl_id, "")
        print(f"📸 Procesando {pl_name} (#{pl_number}) - ID: {pl_id}...")
        
        # Generar gráfica de tiros en buffer
        chart_buffer = plot_player_shots_to_buffer(
            court_image_path=court_image_path,
            shots_list=shots_list,
            player_id=pl_id
        )
        
        # Obtener foto del jugador en buffer
        photo_buffer = get_player_photo_buffer(pl_id)
        
        # Crear celda usando buffers con nombre y número
        player_cell = create_player_cell_from_buffers(pl_name, pl_number, photo_buffer, chart_buffer)
        player_cells.append(player_cell)
        
        # Limitar a 12 jugadores para que quepa en el PDF
        if len(player_cells) >= 12:
            break
    
    # Crear tabla principal (3 columnas)
    table_data = []
    for i in range(0, len(player_cells), 3):
        row = []
        for j in range(3):
            if i + j < len(player_cells):
                row.append(player_cells[i + j])
            else:
                row.append("")  # Celda vacía
        table_data.append(row)
    
    main_table = Table(
        table_data,
        colWidths=[63*mm, 63*mm, 63*mm],
        rowHeights=[48*mm] * len(table_data)
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
    
    # Generar PDF
    try:
        doc.build(elements)
        print(f"✅ PDF generado: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"❌ Error generando PDF: {e}")
        raise
