# -*- coding: utf-8 -*-
"""
SCOUTING por equipo (ruta liga->grupo->equipo) + acumulado de tiros por jugador
- Selección exacta en datos.json: categorias[liga]['grupos'][grupo]['equipos'] (por nombre)
- Filtrado vectorizado en results_YYYYMMDD.csv por URL de equipo (local/visitante) SIN NORMALIZAR
- Descarga shotchart (sin Selenium), acumula tiros por jugador y pinta media pista única por jugador

Requisitos: requests, beautifulsoup4, pillow, matplotlib, pandas, numpy
"""

import os
import re
import json
import io
from typing import List, Dict, Optional, Iterable, Tuple, Any

import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.platypus.flowables import Image as ReportLabImage

# =============== Import de función PDF (ahora en módulo separado) ===============
# NOTA: No importamos generate_team_scouting_pdf aquí para evitar importaciones circulares
# La función está disponible desde pdf_generator.shotchart_pdf

# =============== Utilidades genéricas ===============
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def coerce_str(x: Any) -> str:
    return "" if x is None else str(x)

def parse_qs_param(url: str, key: str) -> Optional[str]:
    if not isinstance(url, str):
        return None
    m = re.search(rf"[?&]{re.escape(key)}=([^&#]+)", url)
    return m.group(1) if m else None

def parse_partido_id_from_str(s: str) -> Optional[str]:
    """
    Extrae el partido_id de diferentes formatos de enlace, sin normalizar:
      - /partido/2413239
      - ?p=2413239
      - ?id=2413239
      - ?cod=2413239
    """
    if not isinstance(s, str):
        return None
    for pat in (r"/partido/(\d+)", r"[?&]p=(\d+)", r"[?&]id=(\d+)", r"[?&]cod=(\d+)"):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None

def safe_team_stem(name: str) -> str:
    """
    Nombre de carpeta "ligero": solo sustituye espacios y separadores por '_'.
    (sin normalizar ni tocar acentos/mayúsculas).
    """
    s = coerce_str(name)
    for ch in [" ", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        s = s.replace(ch, "_")
    return s


# =============== SCRAPER (sin Selenium) ===============
class ShotChartScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://baloncestoenvivo.feb.es/',
            'Origin': 'https://baloncestoenvivo.feb.es'
        }
        self.token = None

    def get_token(self, partido_id: str) -> bool:
        url = f"https://baloncestoenvivo.feb.es/partido/{partido_id}"
        self.headers['Referer'] = url
        r = requests.get(url, headers=self.headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        token_input = soup.find('input', {'name': '_ctl0:token'})
        if token_input:
            self.token = token_input.get('value')
            self.headers['Authorization'] = f'Bearer {self.token}'
            return True
        return False

    def get_shot_chart_data(self, partido_id: str) -> dict:
        if not self.get_token(partido_id):
            raise Exception("No se pudo obtener el token de autenticación")
        api_url = f"https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/{partido_id}"
        r = requests.get(api_url, headers=self.headers)
        if r.status_code != 200:
            raise Exception(f"Error API: {r.status_code} - {r.text}")
        return r.json()

    def extract_shots_data(self, data: dict) -> dict | None:
        if not isinstance(data, dict):
            return None
        sc = data.get('SHOTCHART') or data
        return {
            'quarters': sc.get('quarters'),
            'duration': sc.get('duration'),
            'teams': sc.get('TEAM') or sc.get('teams') or [],
            'shots': sc.get('SHOTS') or sc.get('shots') or []
        }


# =============== Plot helpers ===============
def load_local_court_image(local_path: str) -> Image.Image:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"No se encontró la imagen de pista: '{local_path}'")
    return Image.open(local_path)

def _percent_to_pixel(value_pct: float, total_px: int) -> float:
    return (float(value_pct) * float(total_px)) / 100.0

def _to_halfcourt_pixels(shots_pct: Iterable[Dict], full_W: int, full_H: int, trim_left_px: int = 1) -> Tuple[List[Dict], int, int, int]:
    left = int(full_W // 2) + int(trim_left_px)
    half_W = int(full_W - left)
    half_H = int(full_H)
    shots_px = []
    for s in shots_pct:
        x_full = _percent_to_pixel(float(s.get("x")), full_W)
        y_full = _percent_to_pixel(float(s.get("y")), full_H)
        if x_full < (full_W / 2):
            x_full = full_W - x_full
        x_adj = x_full - left
        shot_px = dict(s); shot_px.update({"x": x_adj, "y": y_full})
        shots_px.append(shot_px)
    return shots_px, left, half_W, half_H

def plot_halfcourt_shots_clean(court_img: Image.Image, shots_pct: List[Dict], save_path: str,
                               trim_left_px: int = 1, mask_px: int = 3, rotate_ccw90: bool = True,
                               show_frame: bool = True, point_size: int = 80, edge_lw: float = 0.5) -> str:
    full_W, full_H = court_img.size
    shots_px, left, half_W, half_H = _to_halfcourt_pixels(shots_pct, full_W, full_H, trim_left_px=trim_left_px)
    halfcourt_img = court_img.crop((left, 0, full_W, full_H))
    fig, ax = plt.subplots(figsize=(half_W / 100, half_H / 100), dpi=100)
    ax.imshow(halfcourt_img, extent=[0, half_W, half_H, 0], interpolation="nearest")
    ax.set_xlim(0, half_W); ax.set_ylim(half_H, 0)
    ax.set_aspect("equal", adjustable="box"); ax.axis("off")
    if mask_px and mask_px > 0:
        ax.add_patch(Rectangle((0, 0), mask_px, half_H, facecolor="white", edgecolor="none", zorder=1.5))
    for s in shots_px:
        made = str(s.get("m", "0")) == "1"
        ax.scatter(s["x"], s["y"], c=("green" if made else "red"), s=point_size, edgecolors="black", linewidths=edge_lw, zorder=2)
    if show_frame:
        ax.add_patch(Rectangle((0, 0), half_W, half_H, fill=False, edgecolor="black", linewidth=2, zorder=3))
    tmp_path = save_path.replace(".png", "_temp.png")
    plt.savefig(tmp_path, bbox_inches="tight", pad_inches=0); plt.close(fig)
    final_path = save_path
    if rotate_ccw90:
        Image.open(tmp_path).rotate(-90, expand=True).save(final_path); os.remove(tmp_path)
    else:
        os.replace(tmp_path, final_path)
    return final_path


# =============== Selección exacta en datos.json (liga->grupo->equipo) ===============
def select_team_from_datos(datos_path: str, liga: str, grupo: str, equipo: str, temporada: str = "2025") -> dict:
    """
    datos['categorias'][liga]['grupos'][grupo]['equipos'] (lista) -> equipo por 'nombre'
    SIN normalizaciones ni de nombres ni de URLs.
    Soporta archivos históricos multi-temporada.
    """
    with open(datos_path, 'r', encoding='utf-8') as f:
        datos = json.load(f)

    # Detectar si es archivo histórico y extraer temporada
    if "temporadas" in datos:
        if temporada not in datos["temporadas"]:
            raise KeyError(f"Temporada '{temporada}' no encontrada. Disponibles: {list(datos['temporadas'].keys())}")
        datos = datos["temporadas"][temporada]

    categorias = datos.get('categorias') or {}
    if liga not in categorias:
        raise KeyError(f"Liga '{liga}' no encontrada. Disponibles: {', '.join(categorias.keys())}")

    cat = categorias[liga]
    grupos = (cat.get('grupos') or {})
    if grupo not in grupos:
        raise KeyError(f"Grupo '{grupo}' no encontrado en liga '{liga}'. Disponibles: {', '.join(grupos.keys())}")

    grp = grupos[grupo]
    equipos = grp.get('equipos') or []
    if not isinstance(equipos, list) or not equipos:
        raise KeyError(f"No hay 'equipos' en liga='{liga}', grupo='{grupo}'")

    # Búsqueda exacta por nombre; si no, contiene (sensitivo a mayúsculas/minúsculas)
    eq = None
    for e in equipos:
        if coerce_str(e.get('nombre')) == equipo:
            eq = e; break
    if eq is None:
        for e in equipos:
            if equipo in coerce_str(e.get('nombre')):
                eq = e; break
    if eq is None:
        raise KeyError(f"Equipo '{equipo}' no encontrado en liga='{liga}', grupo='{grupo}'")

    eq = dict(eq)  # copia tal cual (no tocar url_equipo)
    eq['_context'] = {'liga': liga, 'grupo': grupo}
    return eq


# =============== CSV jornadas: filtro vectorizado por URL de equipo (sin normalizar) ===============
def load_results_csv(results_csv_path: str) -> pd.DataFrame:
    """
    Carga el CSV tal cual y NO toca ninguna URL.
    Debe contener columnas: 'local_url', 'visitante_url' y 'partido_url' y/o 'partido_id'
    """
    try:
        df = pd.read_csv(results_csv_path, sep=None, engine='python', dtype=str, keep_default_na=False)
    except Exception:
        df = pd.read_csv(results_csv_path, dtype=str, keep_default_na=False)
    return df

def require_columns(df: pd.DataFrame, cols: List[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas en CSV: {missing}. Están: {list(df.columns)}")

def filter_matches_by_team_url(df: pd.DataFrame, team_url: str) -> pd.DataFrame:
    """
    Igualdad EXACTA contra 'local_url' o 'visitante_url' (sin normalizar)
    Devuelve: partido_id, team_idx (0 local / 1 visitante), partido_url (si existe)
    """
    # Requisitos mínimos de columnas de equipo
    for c in ['local_url', 'visitante_url']:
        if c not in df.columns:
            raise KeyError(f"Falta columna '{c}' en CSV. Columnas: {list(df.columns)}")
    if ('partido_url' not in df.columns) and ('partido_id' not in df.columns):
        raise KeyError("CSV debe tener 'partido_url' o 'partido_id' (alguna de las dos).")

    print("— Debug filter_matches_by_team_url —")
    print("URL equipo (tal cual):", team_url)

    # 1) Coincidencia exacta por URL
    mask = (df['local_url'] == team_url) | (df['visitante_url'] == team_url)

    cols_keep = ['local_url', 'visitante_url']
    if 'partido_url' in df.columns: cols_keep.append('partido_url')
    if 'partido_id'  in df.columns: cols_keep.append('partido_id')

    sub = df.loc[mask, cols_keep].copy()
    print("Coincidencias exactas:", len(sub))
    if sub.empty:
        return sub

    # 2) team_idx según lado
    sub['team_idx'] = np.where(sub['local_url'] == team_url, 0, 1)

    # 3) partido_id: usar columna directa si existe; si no, parsear partido_url
    if 'partido_id' in sub.columns:
        sub['partido_id'] = sub['partido_id'].astype(str)
        sub = sub[sub['partido_id'].str.len() > 0]
    else:
        sub['partido_id'] = sub['partido_url'].apply(parse_partido_id_from_str)
        sub = sub[sub['partido_id'].notna()]

    # 4) quitar duplicados por partido
    sub = sub.drop_duplicates(subset=['partido_id'])

    # 5) salida final
    out_cols = ['partido_id', 'team_idx']
    if 'partido_url' in sub.columns:
        out_cols.append('partido_url')
    return sub[out_cols].reset_index(drop=True)


# =============== Acumulación de tiros por jugador ===============
def shots_from_json_dict(data: Dict) -> List[Dict]:
    if "SHOTCHART" in data:
        data = data["SHOTCHART"]
    return data.get("SHOTS") or data.get("shots") or []

def build_player_maps_for_team(shots_data: dict, team_idx: int) -> Dict[str, dict]:
    out = {}
    teams = shots_data.get('teams') or []
    if 0 <= team_idx < len(teams):
        for p in (teams[team_idx].get('PLAYER') or []):
            dorsal = coerce_str(p.get('no'))
            if dorsal:
                out[dorsal] = {
                    'player_id': coerce_str(p.get('id')), 
                    'player_name': p.get('name'),
                    'player_number': dorsal  # Guardamos también el número de camiseta
                }
    return out

def accumulate_player_shots_from_match(partido_id: str, shots_data: dict, team_idx: int, target_player_ids: set[str]) -> Dict[str, List[Dict]]:
    acc: Dict[str, List[Dict]] = {}
    dorsal_map = build_player_maps_for_team(shots_data, team_idx)
    for s in shots_from_json_dict(shots_data):
        if coerce_str(s.get('team')) != coerce_str(team_idx):
            continue
        dorsal = coerce_str(s.get('player'))
        meta = dorsal_map.get(dorsal)
        if not meta:
            continue
        pid = meta['player_id']
        if target_player_ids and pid not in target_player_ids:
            continue
        x, y = s.get("x"), s.get("y")
        if x in (None, "") or y in (None, ""):
            continue
        acc.setdefault(pid, []).append({
            "x": float(x),
            "y": float(y),
            "m": "1" if coerce_str(s.get("m")) == "1" else "0",
            "quarter": coerce_str(s.get("quarter")),
            "partido_id": partido_id
        })
    return acc

def union_shotlists(dest: Dict[str, List[Dict]], src: Dict[str, List[Dict]]) -> None:
    for k, v in src.items():
        dest.setdefault(k, []).extend(v)


# =============== Plot jugador (acumulado) ===============
def plot_player_accumulated_shots(court_image_path: str = None,
                                player_id: str = "", 
                                shots_list: List[Dict] = None,
                                output_dir: str = "",
                                trim_left_px: int = 1, 
                                mask_px: int = 3, 
                                rotate_ccw90: bool = True,
                                point_size: int = 80) -> str:
    # Usar ruta por defecto si no se proporciona
    if court_image_path is None:
        court_image_path = DEFAULT_COURT_IMAGE
    ensure_dir(output_dir)
    court_img = load_local_court_image(court_image_path)
    # ✅ nombre solicitado: shotchart_<player_id>.png
    png_path = os.path.join(output_dir, f"shotchart_{player_id}.png")
    final = plot_halfcourt_shots_clean(
        court_img=court_img, shots_pct=shots_list, save_path=png_path,
        trim_left_px=trim_left_px, mask_px=mask_px, rotate_ccw90=rotate_ccw90, point_size=point_size
    )
    return final


# =============== Configuración de rutas por defecto ===============
# Obtener la ruta base del proyecto (un nivel arriba de scrapping_folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Rutas por defecto
DEFAULT_DATOS_JSON = os.path.join(DATA_DIR, "datos.json")
DEFAULT_RESULTS_CSV = os.path.join(DATA_DIR, "datos_completos.csv")
DEFAULT_COURT_IMAGE = os.path.join(DATA_DIR, "basket_court_edited.png")
DEFAULT_OUTPUT_DIR = os.path.join(DATA_DIR, "scouting_output")

# =============== Pipeline principal ===============
def generate_team_scouting_shotcharts(
    liga: str,
    grupo: str,
    equipo: str,
    datos_json_path: str = DEFAULT_DATOS_JSON,
    results_csv_path: str = DEFAULT_RESULTS_CSV,
    court_image_path: str = DEFAULT_COURT_IMAGE,
    # jugadores: None = todos; lista por nombre (datos.json) o por player_id 'c'
    jugadores: Optional[List[str]] = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    max_matches: Optional[int] = None
) -> Dict[str, Any]:
    """
    - Selecciona equipo por ruta liga->grupo->equipo en datos.json
    - Filtra CSV por URL de equipo (local/visitante) EXACTA (sin normalizar)
    - Para cada partido: shotchart -> acumula tiros por jugador seleccionado
    - Exporta CSV por jugador y PNG por jugador en carpeta <output_dir>/<TEAM_STEM>_player_shots
    - NO guarda JSON por partido
    """
    ensure_dir(output_dir)

    # 1) Equipo desde datos.json (ruta exacta, sin normalizar URL)
    eq = select_team_from_datos(datos_json_path, liga=liga, grupo=grupo, equipo=equipo)
    url_equipo = coerce_str(eq.get('url_equipo'))
    print(f"🔗 URL del equipo seleccionado (tal cual): {url_equipo}")

    # Carpeta específica del equipo para los outputs de jugadores
    team_stem = safe_team_stem(eq.get('nombre', 'equipo'))
    shots_out_dir = os.path.join(output_dir, f"{team_stem}_player_shots")
    ensure_dir(shots_out_dir)

    plantilla = eq.get('jugadores') or []

    # Mapa player_id ('c' del enlace) -> nombre
    plantilla_ids: Dict[str, str] = {}
    for p in plantilla:
        pid = parse_qs_param(coerce_str(p.get('enlace')), 'c')
        if pid:
            plantilla_ids[pid] = coerce_str(p.get('nombre'))

    # 2) Selección de jugadores
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

    # 3) CSV jornadas → subset por URL de equipo (igualdad exacta)
    df = load_results_csv(results_csv_path)
    # Debug si faltan columnas esperadas
    if not {'local_url','visitante_url'}.issubset(df.columns) or (('partido_url' not in df.columns) and ('partido_id' not in df.columns)):
        print("Columnas CSV:", list(df.columns))
    subset = filter_matches_by_team_url(df, url_equipo)
    if subset.empty:
        raise RuntimeError("No se encontraron partidos para ese equipo (por URL exacta) en el CSV.")
    if max_matches and max_matches > 0:
        subset = subset.tail(max_matches)

    print(f"Equipo: {eq.get('nombre')} | {liga} / {grupo} | Partidos encontrados: {len(subset)}")

    # 4) Iterar partidos: descargar shotchart y acumular (NO guardar JSON por partido)
    scraper = ShotChartScraper()
    acumulado_por_player: Dict[str, List[Dict]] = {}
    nombre_por_player: Dict[str, str] = {}

    for _, row in subset.iterrows():
        pid = coerce_str(row['partido_id'])
        team_idx = int(row['team_idx'])
        try:
            full_data = scraper.get_shot_chart_data(pid)
            shots_data = scraper.extract_shots_data(full_data)
            if not shots_data:
                print(f"[{pid}] sin datos de shotchart.")
                continue

            acc = accumulate_player_shots_from_match(pid, shots_data, team_idx, target_player_ids=target_ids)
            union_shotlists(acumulado_por_player, acc)
            for pl_id in acc.keys():
                if pl_id in plantilla_ids:
                    nombre_por_player[pl_id] = plantilla_ids[pl_id]

            print(f"[{pid}] OK - tiros agregados para {len(acc)} jugadores (team_idx={team_idx}).")
        except Exception as e:
            print(f"[{pid}] ERROR: {e}")

    if not acumulado_por_player:
        raise RuntimeError("No se acumularon tiros para los jugadores seleccionados.")

    # 5) Exportar por jugador (CSV y PNG) en la carpeta del equipo
    players_out: Dict[str, dict] = {}

    for pl_id, shots_list in acumulado_por_player.items():
        pl_name = nombre_por_player.get(pl_id, f"player_{pl_id}")
        # CSV por jugador (se mantiene el nombre que te gusta)
        df_player = pd.DataFrame(shots_list)
        csv_path = os.path.join(shots_out_dir, f"shots_player_{pl_id}.csv")
        df_player.to_csv(csv_path, index=False, encoding='utf-8')
        # PNG acumulado (nombre solicitado)
        png_path = plot_player_accumulated_shots(
            court_image_path=court_image_path,
            player_id=pl_id,
            shots_list=shots_list,
            output_dir=shots_out_dir,
            trim_left_px=1, mask_px=3, rotate_ccw90=True, point_size=80
        )
        players_out[pl_id] = {'name': pl_name, 'png': png_path, 'csv': csv_path, 'num_shots': len(shots_list)}

    return {
        'equipo': {
            'nombre': eq.get('nombre'),
            'url_equipo': url_equipo,
            'liga': liga,
            'grupo': grupo,
            'output_dir': shots_out_dir
        },
        'num_partidos': int(len(subset)),
        'players': players_out
    }


# =============== Funciones auxiliares para PDF ===============
def plot_player_shots_to_buffer(court_image_path: str, shots_list: List[Dict], player_id: str,
                               trim_left_px: int = 1, mask_px: int = 3, rotate_ccw90: bool = True,
                               point_size: int = 80) -> io.BytesIO:
    """Genera gráfica de tiros y la retorna como buffer en memoria"""
    court_img = load_local_court_image(court_image_path)
    
    # Generar gráfica en memoria
    full_W, full_H = court_img.size
    shots_px, left, half_W, half_H = _to_halfcourt_pixels(shots_list, full_W, full_H, trim_left_px=trim_left_px)
    halfcourt_img = court_img.crop((left, 0, full_W, full_H))
    
    fig, ax = plt.subplots(figsize=(half_W / 100, half_H / 100), dpi=100)
    ax.imshow(halfcourt_img, extent=[0, half_W, half_H, 0], interpolation="nearest")
    ax.set_xlim(0, half_W); ax.set_ylim(half_H, 0)
    ax.set_aspect("equal", adjustable="box"); ax.axis("off")
    
    if mask_px and mask_px > 0:
        ax.add_patch(Rectangle((0, 0), mask_px, half_H, facecolor="white", edgecolor="none", zorder=1.5))
    
    for s in shots_px:
        made = str(s.get("m", "0")) == "1"
        ax.scatter(s["x"], s["y"], c=("green" if made else "red"), s=point_size, 
                  edgecolors="black", linewidths=0.5, zorder=2)
    
    ax.add_patch(Rectangle((0, 0), half_W, half_H, fill=False, edgecolor="black", linewidth=2, zorder=3))
    
    # Guardar en buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='PNG', bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    
    # Rotar si es necesario
    if rotate_ccw90:
        img_buffer.seek(0)
        img = Image.open(img_buffer)
        rotated_img = img.rotate(-90, expand=True)
        final_buffer = io.BytesIO()
        rotated_img.save(final_buffer, format='PNG')
        final_buffer.seek(0)
        return final_buffer
    else:
        img_buffer.seek(0)
        return img_buffer

def get_player_photo_buffer(code: str) -> io.BytesIO:
    """Obtiene foto del jugador y la retorna como buffer, usando caché si existe"""
    print(f" 🔍 Intentando obtener foto para código: {code}")
    
    # PRIMERO: Buscar en caché local por código de jugador
    cache_dir = os.path.join(DATA_DIR, "player_photos_cache")
    ensure_dir(cache_dir)
    cached_photo_path = os.path.join(cache_dir, f"{code}.jpg")
    
    # Si existe la foto cacheada, cargarla directamente
    if os.path.exists(cached_photo_path):
        try:
            print(f" 📦 Foto encontrada en caché: {cached_photo_path}")
            img = Image.open(cached_photo_path)
            img_rgb = img.convert("RGB")
            buffer = io.BytesIO()
            img_rgb.save(buffer, format='PNG')
            buffer.seek(0)
            print(f" ✅ Foto cargada desde caché ({img.size[0]}x{img.size[1]})")
            return buffer
        except Exception as e:
            print(f" ⚠️ Error cargando caché, se intentará descargar: {e}")
    
    # SEGUNDO: Definir la ruta del avatar por defecto
    avatar_path = os.path.join(DATA_DIR, "player_whitebg.jpg")
    print(f" 📁 Ruta del avatar: {avatar_path}")
    print(f" 📋 ¿Existe el avatar? {os.path.exists(avatar_path)}")
    
    # TERCERO: INTENTAR DESCARGAR LA FOTO
    url = f"https://imagenes.feb.es/Foto.aspx?c={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f" 🌐 Descargando desde: {url}")
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        print(f" 📊 Tamaño respuesta: {len(r.content)} bytes")
        
        # Verificar que la respuesta tiene contenido válido
        if len(r.content) < 1000:
            raise ValueError(f"Respuesta muy pequeña ({len(r.content)} bytes)")
        
        # Verificar que es una imagen válida
        img = Image.open(io.BytesIO(r.content))
        print(f" 🖼️ Dimensiones imagen: {img.size}")
        
        if img.size[0] < 50 or img.size[1] < 50:
            raise ValueError(f"Dimensiones muy pequeñas: {img.size}")
        
        if img.size[0] == 1 and img.size[1] == 1:
            raise ValueError("Imagen de error (1x1 pixel)")
        
        # Si llegamos aquí, la imagen es válida - GUARDAR EN CACHÉ
        img_rgb = img.convert("RGB")
        
        # Guardar en caché para futuras ejecuciones
        try:
            img_rgb.save(cached_photo_path, format='JPEG', quality=90)
            print(f" 💾 Foto guardada en caché: {cached_photo_path}")
        except Exception as cache_error:
            print(f" ⚠️ No se pudo guardar en caché: {cache_error}")
        
        # Retornar buffer
        buffer = io.BytesIO()
        img_rgb.save(buffer, format='PNG')
        buffer.seek(0)
        print(f" ✅ Foto descargada exitosamente ({img.size[0]}x{img.size[1]})")
        return buffer
        
    except Exception as e:
        print(f" ❌ Error descargando foto: {e}")
        print(f" 🔄 Intentando usar avatar por defecto...")
    
    # SI FALLA LA DESCARGA: USAR AVATAR
    if not os.path.exists(avatar_path):
        print(f" 💥 FATAL: No existe el archivo avatar en {avatar_path}")
        # Listar archivos en la carpeta data para debug
        try:
            files_in_data = os.listdir(DATA_DIR)
            print(f" 📂 Archivos en {DATA_DIR}: {files_in_data}")
        except:
            print(f" 💥 No se puede acceder a {DATA_DIR}")
        
        # Crear placeholder como último recurso
        print(f" 🔧 Creando placeholder gris como último recurso")
        placeholder = Image.new('RGB', (150, 150), color='lightgray')
        buffer = io.BytesIO()
        placeholder.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    
    # CARGAR EL AVATAR - INTENTAR MÚLTIPLES FORMATOS
    print(f" 📂 Cargando avatar desde: {avatar_path}")
    
    # Intentar diferentes enfoques para cargar el avatar
    avatar_loaded = False
    avatar_img = None
    
    # Método 1: Carga directa
    try:
        avatar_img = Image.open(avatar_path)
        print(f" ✅ Avatar cargado con método directo, dimensiones: {avatar_img.size}")
        avatar_loaded = True
    except Exception as e1:
        print(f" ❌ Método 1 falló: {e1}")
    
    # Método 2: Forzar RGB desde el inicio
    if not avatar_loaded:
        try:
            with open(avatar_path, 'rb') as f:
                avatar_img = Image.open(f)
                avatar_img = avatar_img.convert('RGB')
                print(f" ✅ Avatar cargado con método RGB, dimensiones: {avatar_img.size}")
                avatar_loaded = True
        except Exception as e2:
            print(f" ❌ Método 2 falló: {e2}")
    
    # Método 3: Intentar como bytes
    if not avatar_loaded:
        try:
            with open(avatar_path, 'rb') as f:
                img_bytes = f.read()
                avatar_img = Image.open(io.BytesIO(img_bytes))
                print(f" ✅ Avatar cargado con método bytes, dimensiones: {avatar_img.size}")
                avatar_loaded = True
        except Exception as e3:
            print(f" ❌ Método 3 falló: {e3}")
    
    if avatar_loaded and avatar_img:
        try:
            # Convertir a RGB y crear buffer
            avatar_rgb = avatar_img.convert("RGB")
            buffer = io.BytesIO()
            avatar_rgb.save(buffer, format='PNG')
            buffer.seek(0)
            print(f" ✅ Avatar convertido a buffer exitosamente")
            return buffer
        except Exception as save_error:
            print(f" ❌ Error guardando avatar: {save_error}")
    
    # Si llegamos aquí, el avatar está corrupto o no es válido
    print(f" 💥 AVATAR CORRUPTO O INVÁLIDO")
    
    # Crear un avatar placeholder más bonito
    print(f" 🎨 Creando avatar placeholder personalizado")
    placeholder = Image.new('RGB', (200, 200), color='lightblue')
    
    try:
        # Dibujar una silueta simple
        draw = ImageDraw.Draw(placeholder)
        
        # Cabeza (círculo)
        head_center = (100, 70)
        head_radius = 30
        draw.ellipse([head_center[0]-head_radius, head_center[1]-head_radius, 
                     head_center[0]+head_radius, head_center[1]+head_radius], 
                     fill='darkgray')
        
        # Cuerpo (rectángulo redondeado)
        body_top = head_center[1] + head_radius + 5
        draw.ellipse([60, body_top, 140, body_top + 80], fill='darkgray')
        
        print(f" ✅ Avatar placeholder dibujado")
    except Exception as draw_error:
        print(f" ⚠️ Error dibujando avatar: {draw_error}")
    
    buffer = io.BytesIO()
    placeholder.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer





# =============== Función principal unificada (versión simplificada) ===============
def generate_team_scouting_report(
    liga: str,
    grupo: str,
    equipo: str,
    datos_json_path: str = DEFAULT_DATOS_JSON,
    results_csv_path: str = DEFAULT_RESULTS_CSV,
    court_image_path: str = DEFAULT_COURT_IMAGE,
    jugadores: Optional[List[str]] = None,
    max_matches: Optional[int] = None,
    save_individual_images: bool = True
) -> Dict[str, Any]:
    """
    Función unificada que genera el reporte de scouting con las imágenes en memoria.
    
    Args:
        liga: Nombre de la liga
        grupo: Nombre del grupo
        equipo: Nombre del equipo
        datos_json_path: Ruta al archivo datos.json
        results_csv_path: Ruta al archivo CSV de resultados
        court_image_path: Ruta a la imagen de la pista
        jugadores: Lista de jugadores específicos (opcional)
        max_matches: Límite de partidos (opcional)
        save_individual_images: Si guardar las imágenes individuales (opcional)
        
    Returns:
        Dict con información del equipo, jugadores y sus imágenes en memoria
    """
    print("🏀 Iniciando generación de reporte de scouting...")
    
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
    
    # Acumular tiros por jugador (igual que antes)
    scraper = ShotChartScraper()
    acumulado_por_player: Dict[str, List[Dict]] = {}
    nombre_por_player: Dict[str, str] = {}
    
    for _, row in subset.iterrows():
        pid = coerce_str(row['partido_id'])
        team_idx = int(row['team_idx'])
        try:
            full_data = scraper.get_shot_chart_data(pid)
            shots_data = scraper.extract_shots_data(full_data)
            if not shots_data:
                continue
                
            acc = accumulate_player_shots_from_match(pid, shots_data, team_idx, target_player_ids=target_ids)
            union_shotlists(acumulado_por_player, acc)
            for pl_id in acc.keys():
                if pl_id in plantilla_ids:
                    nombre_por_player[pl_id] = plantilla_ids[pl_id]
            
            print(f"[{pid}] ✓ Tiros procesados")
        except Exception as e:
            print(f"[{pid}] ❌ Error: {e}")
    
    if not acumulado_por_player:
        raise RuntimeError("No se encontraron datos de tiros.")
    
    print(f"📊 Procesando {len(acumulado_por_player)} jugadores...")
    
    # 2) Procesar jugadores y generar imágenes en memoria
    players_data = {}
    team_safe = safe_team_stem(eq.get('nombre', 'equipo'))
    
    # Crear directorio de salida si se van a guardar imágenes
    if save_individual_images:
        output_dir = os.path.join(DEFAULT_OUTPUT_DIR, f"scouting_{team_safe}")
        ensure_dir(output_dir)
    
    for pl_id, shots_list in acumulado_por_player.items():
        pl_name = nombre_por_player.get(pl_id, f"player_{pl_id}")
        print(f"📸 Procesando {pl_name} ({pl_id})...")
        
        # Generar gráfica de tiros en buffer
        chart_buffer = plot_player_shots_to_buffer(
            court_image_path=court_image_path,
            shots_list=shots_list,
            player_id=pl_id
        )
        
        # Obtener foto del jugador en buffer
        photo_buffer = get_player_photo_buffer(pl_id)
        
        # Calcular estadísticas
        total_shots = len(shots_list)
        made_shots = sum(1 for s in shots_list if str(s.get("m", "0")) == "1")
        percentage = (made_shots / total_shots * 100) if total_shots > 0 else 0
        
        player_info = {
            'id': pl_id,
            'nombre': pl_name,
            'total_tiros': total_shots,
            'tiros_anotados': made_shots,
            'porcentaje': percentage,
            'chart_buffer': chart_buffer,
            'photo_buffer': photo_buffer
        }
        
        # Guardar imágenes individuales si se solicita
        if save_individual_images:
            # Guardar gráfica de tiros
            chart_path = os.path.join(output_dir, f"{pl_id}_{pl_name}_shots.png")
            chart_buffer.seek(0)
            with open(chart_path, 'wb') as f:
                f.write(chart_buffer.read())
            player_info['chart_path'] = chart_path
            
            # Guardar foto
            photo_path = os.path.join(output_dir, f"{pl_id}_{pl_name}_photo.png")
            photo_buffer.seek(0)
            with open(photo_path, 'wb') as f:
                f.write(photo_buffer.read())
            player_info['photo_path'] = photo_path
            
            print(f"  → Imágenes guardadas para {pl_name}")
        
        players_data[pl_id] = player_info
    
    # 3) Crear resumen del equipo
    team_info = {
        'nombre': eq.get('nombre'),
        'liga': liga,
        'grupo': grupo,
        'num_partidos': len(subset),
        'num_jugadores': len(players_data),
        'output_dir': output_dir if save_individual_images else None,
        'players': players_data
    }
    
    print(f"✅ Reporte generado para {team_info['nombre']}")
    print(f"   - {team_info['num_jugadores']} jugadores procesados")
    print(f"   - {team_info['num_partidos']} partidos analizados")
    if save_individual_images:
        print(f"   - Imágenes guardadas en: {output_dir}")
    
    return team_info
