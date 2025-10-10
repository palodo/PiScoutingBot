# -*- coding: utf-8 -*-
"""
PDF Generator Module
Módulo para la generación de PDFs de scouting de baloncesto

Este módulo contiene todas las funciones relacionadas con la creación
de reportes PDF a partir de los datos de scouting.
"""

from .shotchart_pdf import generate_team_scouting_pdf, create_player_cell_from_buffers
from .generar import generar_pdf

__all__ = [
    'generate_team_scouting_pdf',
    'create_player_cell_from_buffers',
    'generar_pdf'
]
