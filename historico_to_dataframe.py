# -*- coding: utf-8 -*-
"""
Herramienta para convertir datos históricos JSON a DataFrame con estadísticas avanzadas
Extrae y procesa datos de archivos datos_historicos.json para generar DataFrames listos para análisis
"""

import json
import pandas as pd
import numpy as np
import os
import re
import unicodedata
import requests
from pathlib import Path


# =============== FUNCIONES DE ESTADÍSTICAS AVANZADAS ===============

def normalizar_dataframe(df):
    """
    Normaliza el dataframe renombrando columnas a nombres cortos y calculando estadísticas derivadas.
    
    Args:
        df: DataFrame con datos de equipos desde el JSON
        
    Returns:
        DataFrame normalizado con columnas renombradas y estadísticas calculadas
    """
    # Mapeo de nombres largos a nombres cortos
    column_mapping = {
        'nombre': 'Equipo',
        'url_equipo': 'URL_Equipo',
        'url_estadisticas': 'URL_Stats',
        'jugadores': 'Jugadores',
        'liga': 'Liga',
        'categoria': 'Categoria',
        'informacion_general.puntos_favor': 'PTS_Favor',
        'informacion_general.puntos_contra': 'PTS_Contra',
        'informacion_general.partidos_jugados': 'PJ',
        'informacion_general.partidos_ganados': 'PG',
        'informacion_general.partidos_perdidos': 'PP',
        'informacion_general.diferencia_puntos': 'Diff_PTS',
        'resumen_equipo.total_jugadores': 'Total_Jugadores',
        'resumen_equipo.puntos_totales': 'PTS_Total',
        'resumen_equipo.minutos_totales': 'MIN_Total',
        'resumen_equipo.rebotes_totales': 'REB_Total',
        'resumen_equipo.rebotes_ofensivos_totales': 'OREB_Total',
        'resumen_equipo.rebotes_defensivos_totales': 'DREB_Total',
        'resumen_equipo.asistencias_totales': 'AST_Total',
        'resumen_equipo.valoracion_total': 'VAL_Total',
        'resumen_equipo.fg2a_total': 'FG2A',
        'resumen_equipo.fg2m_total': 'FG2M',
        'resumen_equipo.fga_total': 'FGA',
        'resumen_equipo.fgm_total': 'FGM',
        'resumen_equipo.fg3a_total': 'FG3A',
        'resumen_equipo.fg3m_total': 'FG3M',
        'resumen_equipo.fta_total': 'FTA',
        'resumen_equipo.ftm_total': 'FTM',
        'resumen_equipo.perdidas_totales': 'TO',
        'resumen_equipo.recuperaciones_totales': 'STL',
        'resumen_equipo.promedio_puntos_por_jugador': 'PTS_Avg',
        'resumen_equipo.promedio_minutos_por_jugador': 'MIN_Avg',
        'resumen_equipo.promedio_valoracion_por_jugador': 'VAL_Avg'
    }
    
    # Renombrar columnas
    df = df.rename(columns=column_mapping)
    
    # Calcular porcentajes de tiro
    df['FG%'] = (df['FGM'] / df['FGA'] * 100).round(1)
    df['FG2%'] = (df['FG2M'] / df['FG2A'] * 100).round(1)
    df['FG3%'] = (df['FG3M'] / df['FG3A'] * 100).round(1)
    df['FT%'] = (df['FTM'] / df['FTA'] * 100).round(1)
    df['Win%'] = (df['PG'] / df['PJ'] * 100).round(1)
    
    # Calcular estadísticas por partido
    df['PTS/PJ'] = (df['PTS_Favor'] / df['PJ']).round(1)
    df['REB/PJ'] = (df['REB_Total'] / df['PJ']).round(1)
    df['OREB/PJ'] = (df['OREB_Total'] / df['PJ']).round(1)
    df['DREB/PJ'] = (df['DREB_Total'] / df['PJ']).round(1)
    df['AST/PJ'] = (df['AST_Total'] / df['PJ']).round(1)
    df['TO/PJ'] = (df['TO'] / df['PJ']).round(1)
    df['STL/PJ'] = (df['STL'] / df['PJ']).round(1)
    
    # Porcentajes de rebotes
    df['OREB%'] = ((df['OREB_Total'] / df['REB_Total']) * 100).round(1)
    df['DREB%'] = ((df['DREB_Total'] / df['REB_Total']) * 100).round(1)
    
    return df


def cargar_logos_equipos(df):
    """
    Carga los logos de los equipos y añade las columnas 'logo_path' y 'logo_url' al dataframe.
    
    Args:
        df: DataFrame con columnas 'Equipo' y 'URL_Equipo'
        
    Returns:
        DataFrame con las nuevas columnas logo_path y logo_url añadidas
    """
    # Configuración
    IMAGES_DIR = Path("imagenes")
    IMAGES_DIR.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def safe_filename(name):
        """Convierte nombre de equipo a nombre de archivo seguro"""
        n = unicodedata.normalize("NFKD", name)
        n = "".join(c for c in n if not unicodedata.combining(c))
        return re.sub(r"[^A-Za-z0-9._ -]", "", n).strip().replace(" ", "_") or "equipo"
    
    def extraer_team_id(url):
        """Extrae el ID del equipo de la URL"""
        m = re.search(r"[?&]i=(\d+)", url)
        return m.group(1) if m else None
    
    def obtener_logo(equipo, url_equipo):
        """Descarga el logo del equipo si no existe y retorna la ruta local y URL"""
        fn = IMAGES_DIR / f"{safe_filename(equipo)}.jpg"
        
        # Si ya existe el archivo, retornar ruta local y URL
        if fn.exists(): 
            tid = extraer_team_id(url_equipo)
            logo_url = f"https://imagenes.feb.es/Imagen.aspx?i={tid}&ti=1" if tid else None
            return str(fn), logo_url
        
        # Descargar logo si no existe
        tid = extraer_team_id(url_equipo)
        if not tid: 
            return None, None
            
        logo_url = f"https://imagenes.feb.es/Imagen.aspx?i={tid}&ti=1"
        try:
            r = session.get(logo_url, timeout=15)
            r.raise_for_status()
            fn.write_bytes(r.content)
            return str(fn), logo_url
        except Exception as e:
            print(f"Error descargando logo para {equipo}: {e}")
            return None, None
    
    # Crear una copia del dataframe para no modificar el original
    df_copy = df.copy()
    
    # Añadir columnas de logos
    logos_data = [obtener_logo(row.Equipo, row.URL_Equipo) for _, row in df_copy.iterrows()]
    df_copy["logo_path"], df_copy["logo_url"] = zip(*logos_data)
    
    return df_copy


def calcular_estadisticas_avanzadas(df):
    """
    Calcula estadísticas avanzadas de baloncesto: Ritmo, Offensive Rating y Defensive Rating.
    
    Args:
        df: DataFrame con estadísticas básicas de equipos
        
    Returns:
        DataFrame con las nuevas columnas de estadísticas avanzadas añadidas
    """
    # Crear una copia del dataframe para no modificar el original
    df_copy = df.copy()
    
    # Calcular posesiones utilizando rebotes ofensivos reales
    df_copy['Posesiones'] = (df_copy['FGA'] - df_copy['OREB_Total'] + df_copy['TO'] + 0.4 * df_copy['FTA']).round(1)
    
    # Ritmo (Pace) - Posesiones por partido
    df_copy['Ritmo'] = (df_copy['Posesiones'] / df_copy['PJ']).round(1)
    
    # Offensive Rating - Puntos anotados por cada 100 posesiones
    df_copy['ORtg'] = ((df_copy['PTS_Favor'] / df_copy['Posesiones']) * 100).round(1)
    
    # Defensive Rating - Puntos permitidos por cada 100 posesiones
    df_copy['DRtg'] = ((df_copy['PTS_Contra'] / df_copy['Posesiones']) * 100).round(1)
    
    # Net Rating - Diferencia entre ORtg y DRtg
    df_copy['NetRtg'] = (df_copy['ORtg'] - df_copy['DRtg']).round(1)
    
    # True Shooting Percentage
    df_copy['TS%'] = ((df_copy['PTS_Favor'] / (2 * (df_copy['FGA'] + 0.44 * df_copy['FTA']))) * 100).round(1)
    
    # Ratio Asistencias/Pérdidas
    df_copy['AST/TO'] = (df_copy['AST_Total'] / df_copy['TO']).round(2)
    
    # Efectividad en rebotes ofensivos (% de rebotes ofensivos sobre tiros fallados)
    total_misses = df_copy['FGA'] - df_copy['FGM']
    df_copy['OREB_Rate'] = ((df_copy['OREB_Total'] / total_misses) * 100).round(1)
    
    return df_copy


def normalizar_estadisticas_jugadores(df_jugadores):
    """
    Normaliza las estadísticas de jugadores individuales con nombres cortos y estadísticas calculadas.
    
    Args:
        df_jugadores: DataFrame con estadísticas de jugadores
        
    Returns:
        DataFrame normalizado con estadísticas calculadas
    """
    df = df_jugadores.copy()
    
    # Renombrar columnas principales
    column_mapping = {
        'nombre': 'Jugador',
        'enlace': 'Enlace',
        'fase': 'Fase',
        'partidos': 'PJ',
        'minutos_segundos': 'MIN',
        'puntos': 'PTS',
        'tiros_dos_made': 'FG2M',
        'tiros_dos_attempted': 'FG2A',
        'tiros_tres_made': 'FG3M',
        'tiros_tres_attempted': 'FG3A',
        'tiros_campo_made': 'FGM',
        'tiros_campo_attempted': 'FGA',
        'tiros_libres_made': 'FTM',
        'tiros_libres_attempted': 'FTA',
        'rebotes_defensivos': 'DREB',
        'rebotes_ofensivos': 'OREB',
        'rebotes_totales': 'REB',
        'asistencias': 'AST',
        'perdidas': 'TO',
        'recuperaciones': 'STL',
        'tapones_favor': 'BLK',
        'tapones_contra': 'BLKA',
        'faltas_cometidas': 'PF',
        'faltas_recibidas': 'PFD',
        'valoracion': 'VAL'
    }
    
    # Aplicar renombrado solo a columnas que existen
    existing_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_mapping)
    
    # Extraer ID único del jugador desde el enlace
    df['ID'] = df['Enlace'].str.extract(r'c=(\d+)$')[0]
    
    # Calcular estadísticas básicas por partido
    df['PTS/PJ'] = (df['PTS'] / df['PJ']).round(1)
    df['REB/PJ'] = (df['REB'] / df['PJ']).round(1)
    df['AST/PJ'] = (df['AST'] / df['PJ']).round(1)
    df['TO/PJ'] = (df['TO'] / df['PJ']).round(1)
    df['STL/PJ'] = (df['STL'] / df['PJ']).round(1)
    df['VAL/PJ'] = (df['VAL'] / df['PJ']).round(1)
    df['OREB/PJ'] = (df['OREB'] / df['PJ']).round(1)
    df['FG3A/PJ'] = (df['FG3A'] / df['PJ']).round(1)
    df['FTA/PJ'] = (df['FTA'] / df['PJ']).round(1)
    
    # Calcular porcentajes de tiro
    if 'FG2M' in df.columns and 'FG2A' in df.columns:
        df['FG2%'] = ((df['FG2M'] / df['FG2A']) * 100).round(1)
    if 'FG3M' in df.columns and 'FG3A' in df.columns:
        df['FG3%'] = ((df['FG3M'] / df['FG3A']) * 100).round(1)
    if 'FTM' in df.columns and 'FTA' in df.columns:
        df['FT%'] = ((df['FTM'] / df['FTA']) * 100).round(1)
    # FG total
    if 'FGM' in df.columns and 'FGA' in df.columns:
        df['FG%'] = ((df['FGM'] / df['FGA']) * 100).round(1)

    # True Shooting Percentage
    if 'PTS' in df.columns and 'FGA' in df.columns and 'FTA' in df.columns:
        df['TS%'] = ((df['PTS'] / (2 * (df['FGA'] + 0.44 * df['FTA']))) * 100).round(1)
    
    # Usage Percentage - cálculo correcto y simplificado
    if 'FGA' in df.columns and 'FTA' in df.columns and 'TO' in df.columns and 'MIN' in df.columns and 'PJ' in df.columns:
        df['USG%'] = 0.0  # Inicializar columna
        
        for i in df.index:
            pj = df.loc[i, 'PJ']
            if pj > 0:  # Solo calcular si el jugador ha jugado partidos
                # Estadísticas por partido
                fga_pg = df.loc[i, 'FGA'] / pj
                fta_pg = df.loc[i, 'FTA'] / pj
                to_pg = df.loc[i, 'TO'] / pj
                min_pg = df.loc[i, 'MIN'] / 60.0 / pj  # Convertir segundos a minutos por partido
                
                if min_pg > 0:  # Evitar división por cero
                    # Posesiones por partido
                    posesiones_pg = fga_pg + 0.44 * fta_pg + to_pg
                    
                    # USG% = (posesiones por minuto) * 40 minutos * factor de escala
                    usg_rate = (posesiones_pg / min_pg) * 40 * 0.5
                    df.loc[i, 'USG%'] = round(min(usg_rate, 99.9), 1)
                else:
                    df.loc[i, 'USG%'] = 0.0
            else:
                df.loc[i, 'USG%'] = 0.0
    
    return df


def calcular_usg_correcto(df):
    """
    Calcula USG% usando la fórmula que probamos manualmente
    """
    df_copy = df.copy()
    df_copy['USG%'] = 0.0
    
    for i in df_copy.index:
        pj = df_copy.loc[i, 'PJ']
        if pj > 0:
            fga = df_copy.loc[i, 'FGA']
            fta = df_copy.loc[i, 'FTA'] 
            to = df_copy.loc[i, 'TO']
            minutos = df_copy.loc[i, 'MIN']
            
            # Calcular por partido
            fga_pg = fga / pj
            fta_pg = fta / pj
            to_pg = to / pj
            min_pg = minutos / 60 / pj  # Convertir segundos a minutos por partido
            
            if min_pg > 0:
                # Posesiones por partido
                posesiones_pg = fga_pg + 0.44 * fta_pg + to_pg
                
                # USG% = (posesiones por minuto) * 40 min * factor de escala
                usg_rate = (posesiones_pg / min_pg) * 40 * 0.5
                df_copy.loc[i, 'USG%'] = round(min(usg_rate, 99.9), 1)
    
    return df_copy


def crear_rankings_jugadores(df_jugadores):
    """
    Crea rankings de los mejores jugadores en diferentes categorías estadísticas por partido jugado.
    Utiliza las columnas /PJ ya calculadas en el DataFrame.
    Incluye ID y Enlace para poder acceder al sistema de caché de fotos.
    
    Args:
        df_jugadores: DataFrame con estadísticas normalizadas de jugadores
        
    Returns:
        dict: Diccionario con rankings por categoría (por partido)
    """
    rankings = {}
    
    # Columnas comunes para todos los rankings (incluir ID y Enlace para el sistema de caché)
    columnas_base = ['Jugador', 'ID', 'Enlace', 'PJ']
    if 'foto_path' in df_jugadores.columns:
        columnas_base.append('foto_path')
    
    # Top 7 en Puntos por partido
    rankings['Puntos'] = df_jugadores.nlargest(7, 'PTS/PJ')[columnas_base + ['PTS/PJ']].copy()
    
    # Top 7 en Valoración por partido
    rankings['Valoracion'] = df_jugadores.nlargest(7, 'VAL/PJ')[columnas_base + ['VAL/PJ']].copy()
    
    # Top 7 en Rebotes por partido
    rankings['Rebotes'] = df_jugadores.nlargest(7, 'REB/PJ')[columnas_base + ['REB/PJ']].copy()
    
    # Top 7 en Rebotes ofensivos por partido
    rankings['Rebotes_Ofensivos'] = df_jugadores.nlargest(7, 'OREB/PJ')[columnas_base + ['OREB/PJ']].copy()
    
    # Top 7 en Robos por partido
    rankings['Robos'] = df_jugadores.nlargest(7, 'STL/PJ')[columnas_base + ['STL/PJ']].copy()
    
    # Top 7 en Tiros de 3 por partido (con su FG3%)
    rankings['Triples_Intentados'] = df_jugadores.nlargest(7, 'FG3A/PJ')[columnas_base + ['FG3A/PJ', 'FG3%']].copy()
    
    # Top 7 en Porcentaje de Uso (USG%)
    if 'USG%' in df_jugadores.columns:
        rankings['Uso'] = df_jugadores.nlargest(7, 'USG%')[columnas_base + ['USG%']].copy()
    
    # Top 7 en Asistencias por partido
    rankings['Asistencias'] = df_jugadores.nlargest(7, 'AST/PJ')[columnas_base + ['AST/PJ']].copy()
    
    # Top 7 en Porcentaje de Tiros Libres (FT%)
    # Filtrar jugadores que han tirado al menos 1 tiro libre por partido para evitar porcentajes engañosos
    df_ft_filter = df_jugadores[df_jugadores['FTA/PJ'] >= 1.0].copy()
    if not df_ft_filter.empty:
        rankings['Tiros_Libres'] = df_ft_filter.nlargest(7, 'FT%')[columnas_base + ['FT%', 'FTA/PJ']].copy()
    else:
        # Si nadie cumple el criterio, usar todos los jugadores
        rankings['Tiros_Libres'] = df_jugadores.nlargest(7, 'FT%')[columnas_base + ['FT%', 'FTA/PJ']].copy()
    
    # Top 7 en True Shooting Percentage (TS%) - Estadística avanzada
    # Filtrar jugadores con al menos 5 puntos por partido para mayor relevancia
    df_ts_filter = df_jugadores[df_jugadores['PTS/PJ'] >= 5.0].copy()
    if not df_ts_filter.empty:
        rankings['True_Shooting'] = df_ts_filter.nlargest(7, 'TS%')[columnas_base + ['TS%', 'PTS/PJ']].copy()
    else:
        # Si nadie cumple el criterio, usar todos los jugadores
        rankings['True_Shooting'] = df_jugadores.nlargest(7, 'TS%')[columnas_base + ['TS%', 'PTS/PJ']].copy()
    
    return rankings


# =============== FUNCIONES PRINCIPALES ===============


def cargar_datos_temporada(json_path: str, temporada: str = "2025"):
    """
    Carga datos de una temporada específica desde un archivo JSON histórico
    
    Args:
        json_path: Ruta al archivo datos_historicos.json
        temporada: Temporada a extraer (ej: "2025", "2024")
    
    Returns:
        dict: Datos de la temporada especificada
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Detectar si es archivo histórico multi-temporada
    if "temporadas" in data:
        print(f"📚 Archivo histórico detectado. Extrayendo temporada {temporada}...")
        if temporada not in data["temporadas"]:
            available = list(data["temporadas"].keys())
            raise ValueError(f"Temporada '{temporada}' no encontrada. Disponibles: {available}")
        return data["temporadas"][temporada]
    else:
        print(f"📄 Archivo de temporada única detectado")
        return data


def procesar_equipos_desde_json(json_path: str, liga: str, grupo: str, temporada: str = "2025"):
    """
    Procesa equipos desde JSON histórico y genera DataFrame con estadísticas avanzadas
    
    Args:
        json_path: Ruta al archivo datos_historicos.json
        liga: Liga a extraer (ej: "3", "2")
        grupo: Grupo a extraer (ej: "Liga Regular E-A")
        temporada: Temporada a procesar
    
    Returns:
        pd.DataFrame: DataFrame de equipos con estadísticas avanzadas
    """
    print(f"🔄 Procesando equipos: Liga {liga}, Grupo {grupo}, Temporada {temporada}")
    
    # 1. Cargar datos de la temporada
    data = cargar_datos_temporada(json_path, temporada)
    
    # 2. Navegar estructura JSON
    try:
        nodo_categoria = data["categorias"][liga]
        nodo_grupo = nodo_categoria["grupos"][grupo]
        equipos = nodo_grupo["equipos"]
        
        print(f"✅ Encontrados {len(equipos)} equipos en {liga} - {grupo}")
        
    except KeyError as e:
        print(f"❌ Error navegando JSON: {e}")
        print(f"   Categorias disponibles: {list(data.get('categorias', {}).keys())}")
        if liga in data.get("categorias", {}):
            print(f"   Grupos en liga {liga}: {list(data['categorias'][liga].get('grupos', {}).keys())}")
        raise
    
    # 3. Convertir JSON a DataFrame
    df_equipos = pd.json_normalize(equipos, sep=".")
    print(f"📊 DataFrame inicial creado: {df_equipos.shape}")
    
    # 4. Aplicar estadísticas avanzadas
    print("⚡ Calculando estadísticas avanzadas...")
    df_equipos = normalizar_dataframe(df_equipos)
    df_equipos = cargar_logos_equipos(df_equipos)
    df_equipos = calcular_estadisticas_avanzadas(df_equipos)
    
    print(f"✅ DataFrame procesado: {df_equipos.shape}")
    print(f"   Columnas finales: {list(df_equipos.columns)}")
    
    return df_equipos


def procesar_jugadores_desde_json(json_path: str, liga: str, grupo: str, equipo_nombre: str, temporada: str = "2025"):
    """
    Procesa jugadores de un equipo específico desde JSON histórico
    
    Args:
        json_path: Ruta al archivo datos_historicos.json
        liga: Liga a extraer
        grupo: Grupo a extraer  
        equipo_nombre: Nombre exacto del equipo
        temporada: Temporada a procesar
    
    Returns:
        tuple: (df_jugadores_norm, df_principales, df_apoyo, rankings)
    """
    print(f"🏀 Procesando jugadores del equipo: {equipo_nombre}")
    
    # 1. Cargar datos de la temporada
    data = cargar_datos_temporada(json_path, temporada)
    
    # 2. Navegar hasta el equipo específico
    try:
        nodo_categoria = data["categorias"][liga]
        nodo_grupo = nodo_categoria["grupos"][grupo]
        equipos = nodo_grupo["equipos"]
        
        # Buscar el equipo por nombre
        equipo_data = None
        for equipo in equipos:
            if equipo.get("Equipo") == equipo_nombre:
                equipo_data = equipo
                break
        
        if not equipo_data:
            equipos_disponibles = [e.get("Equipo", "Sin nombre") for e in equipos]
            raise ValueError(f"Equipo '{equipo_nombre}' no encontrado. Disponibles: {equipos_disponibles}")
        
        # Extraer jugadores
        jugadores_raw = []
        if "jugadores" in equipo_data:
            jugadores_raw = equipo_data["jugadores"]
        
        print(f"✅ Encontrados {len(jugadores_raw)} jugadores en {equipo_nombre}")
        
    except KeyError as e:
        print(f"❌ Error navegando JSON para jugadores: {e}")
        raise
    
    # 3. Procesar jugadores
    if not jugadores_raw:
        print("⚠️ No se encontraron jugadores")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}
    
    # Convertir a DataFrame
    df_jugadores = pd.json_normalize(jugadores_raw)
    print(f"📊 DataFrame jugadores inicial: {df_jugadores.shape}")
    
    # Aplicar estadísticas avanzadas
    print("⚡ Calculando estadísticas avanzadas para jugadores...")
    df_jugadores_norm = normalizar_estadisticas_jugadores(df_jugadores)
    df_jugadores_norm = calcular_usg_correcto(df_jugadores_norm)
    
    # Separar principales y apoyo (criterio: >25% de partidos)
    partidos_equipo = len(jugadores_raw)  # Aproximación
    min_partidos = max(1, partidos_equipo * 0.25)
    
    df_principales = df_jugadores_norm[df_jugadores_norm['PJ'] >= min_partidos].copy()
    df_apoyo = df_jugadores_norm[df_jugadores_norm['PJ'] < min_partidos].copy()
    
    # Crear rankings
    rankings = crear_rankings_jugadores(df_jugadores_norm)
    
    print(f"✅ Procesamiento completo:")
    print(f"   Jugadores totales: {len(df_jugadores_norm)}")
    print(f"   Principales: {len(df_principales)}")
    print(f"   Apoyo: {len(df_apoyo)}")
    
    return df_jugadores_norm, df_principales, df_apoyo, rankings


def extraer_todas_ligas_grupos(json_path: str, temporada: str = "2025"):
    """
    Extrae información de todas las ligas y grupos disponibles en el JSON
    
    Args:
        json_path: Ruta al archivo datos_historicos.json
        temporada: Temporada a analizar
    
    Returns:
        dict: Estructura con ligas, grupos y equipos disponibles
    """
    data = cargar_datos_temporada(json_path, temporada)
    
    estructura = {}
    
    for liga, liga_data in data.get("categorias", {}).items():
        estructura[liga] = {}
        
        for grupo, grupo_data in liga_data.get("grupos", {}).items():
            equipos = grupo_data.get("equipos", [])
            nombres_equipos = [e.get("Equipo", "Sin nombre") for e in equipos]
            
            estructura[liga][grupo] = {
                "num_equipos": len(equipos),
                "equipos": nombres_equipos
            }
    
    return estructura


def generar_dataframe_completo(json_path: str, liga: str, grupo: str, temporada: str = "2025", incluir_jugadores: bool = True):
    """
    Función principal para generar DataFrames completos desde JSON histórico
    
    Args:
        json_path: Ruta al archivo datos_historicos.json
        liga: Liga a procesar
        grupo: Grupo a procesar
        temporada: Temporada a procesar
        incluir_jugadores: Si incluir procesamiento de jugadores
    
    Returns:
        dict: Diccionario con todos los DataFrames generados
    """
    print(f"🚀 Generando DataFrames completos para Liga {liga} - {grupo} - Temporada {temporada}")
    
    resultado = {}
    
    # 1. Procesar equipos
    resultado['df_equipos'] = procesar_equipos_desde_json(json_path, liga, grupo, temporada)
    
    # 2. Procesar jugadores por equipo (opcional)
    if incluir_jugadores:
        resultado['jugadores_por_equipo'] = {}
        
        for _, equipo_row in resultado['df_equipos'].iterrows():
            equipo_nombre = equipo_row['Equipo']
            try:
                jugadores_data = procesar_jugadores_desde_json(json_path, liga, grupo, equipo_nombre, temporada)
                resultado['jugadores_por_equipo'][equipo_nombre] = {
                    'df_jugadores_norm': jugadores_data[0],
                    'df_principales': jugadores_data[1],
                    'df_apoyo': jugadores_data[2],
                    'rankings': jugadores_data[3]
                }
            except Exception as e:
                print(f"⚠️ Error procesando jugadores de {equipo_nombre}: {e}")
    
    print("✅ Generación completa!")
    return resultado


# =============== FUNCIONES DE UTILIDAD ===============

def guardar_dataframes_csv(resultado: dict, output_dir: str = "output_dataframes"):
    """
    Guarda todos los DataFrames generados en archivos CSV
    
    Args:
        resultado: Resultado de generar_dataframe_completo()
        output_dir: Directorio de salida
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Guardar equipos
    if 'df_equipos' in resultado:
        equipos_path = output_path / "equipos_estadisticas_avanzadas.csv"
        resultado['df_equipos'].to_csv(equipos_path, index=False, encoding='utf-8')
        print(f"💾 Guardado: {equipos_path}")
    
    # Guardar jugadores por equipo
    if 'jugadores_por_equipo' in resultado:
        for equipo, jugadores_data in resultado['jugadores_por_equipo'].items():
            equipo_safe = equipo.replace(" ", "_").replace("/", "_")
            
            # Jugadores normalizados
            jugadores_path = output_path / f"{equipo_safe}_jugadores_norm.csv"
            jugadores_data['df_jugadores_norm'].to_csv(jugadores_path, index=False, encoding='utf-8')
            
            # Principales
            principales_path = output_path / f"{equipo_safe}_principales.csv"
            jugadores_data['df_principales'].to_csv(principales_path, index=False, encoding='utf-8')
            
            print(f"💾 Guardado: {jugadores_path} y {principales_path}")


# =============== EJEMPLO DE USO ===============

if __name__ == "__main__":
    # Ejemplo de uso básico
    json_path = "data/datos_historicos.json"
    
    print("🔍 Explorando estructura del JSON...")
    try:
        estructura = extraer_todas_ligas_grupos(json_path)
        print("📋 Estructura disponible:")
        for liga, grupos in estructura.items():
            print(f"  Liga {liga}:")
            for grupo, info in grupos.items():
                print(f"    - {grupo}: {info['num_equipos']} equipos")
    except Exception as e:
        print(f"❌ Error explorando estructura: {e}")
        exit(1)
    
    # Ejemplo de procesamiento específico
    liga = "3"  # Cambiar según necesidad
    grupo = "Liga Regular E-A"  # Cambiar según necesidad
    
    print(f"\n🚀 Procesando Liga {liga} - {grupo}...")
    try:
        # Solo equipos
        df_equipos = procesar_equipos_desde_json(json_path, liga, grupo)
        print(f"📊 DataFrame equipos generado: {df_equipos.shape}")
        print(f"   Columnas: {list(df_equipos.columns)}")
        
        # Ejemplo con un equipo específico
        if len(df_equipos) > 0:
            primer_equipo = df_equipos.iloc[0]['Equipo']
            jugadores_data = procesar_jugadores_desde_json(json_path, liga, grupo, primer_equipo)
            print(f"🏀 Jugadores de {primer_equipo} procesados exitosamente")
        
    except Exception as e:
        print(f"❌ Error en procesamiento: {e}")