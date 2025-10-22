import re
import csv
import time
import random
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime
from requests.exceptions import ReadTimeout, ConnectionError

# === CONFIGURACIÓN GLOBAL ===
LIGAS_A_SCRAPEAR = [2, 3]  # Lista de ligas: 2 = Segunda FEB, 3 = Tercera FEB
BASE_URL_TEMPLATE = "https://baloncestoenvivo.feb.es/calendario/tercerafeb/{}/2025"
BASE = "https://baloncestoenvivo.feb.es"

# Año de la temporada de INICIO: 2025 -> "2025/2026", 2024 -> "2024/2025", etc.
TARGET_SEASON_YEAR = 2025

# === MODO DEPURACIÓN ===
FULL_RUN = True         # ← pon True cuando veas que detecta bien select/grupos/jornadas
MAX_GRUPOS_PRUEBA = 3
MAX_JORNADAS_PRUEBA = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,/;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def log(x=""): 
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {x}")

def hr(t=""): 
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] " + "="*30 + (f" {t} " if t else "") + "="*30)

def save_debug_html(html, filename):
    """Guarda HTML de debug con mejor formato"""
    os.makedirs("debug_html", exist_ok=True)
    filepath = os.path.join("debug_html", f"{filename}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"   💾 HTML guardado: {filepath}")

# --------- utilidades webforms ----------
def serialize_form(soup, base_url):
    form = (soup.select_one("form#aspnetForm")
            or soup.select_one("form[name='aspnetForm']")
            or soup.select_one("form"))
    if not form:
        raise RuntimeError("No se encontró <form> (aspnetForm)")
    
    action = urljoin(base_url, form.get("action") or base_url)
    data = {}

    inputs = form.select("input[name]")
    textareas = form.select("textarea[name]")
    selects = form.select("select[name]")
    
    log(f"📋 Campos en el form: inputs={len(inputs)} textareas={len(textareas)} selects={len(selects)}")
    
    for inp in inputs:
        name = inp.get("name")
        typ = (inp.get("type") or "").lower()
        if typ in ("checkbox", "radio"):
            if inp.has_attr("checked"): 
                data[name] = inp.get("value", "on")
        else:
            data[name] = inp.get("value", "")
    
    for ta in textareas:
        data[ta.get("name")] = ta.text or ""
    
    for sel in selects:
        sel_name = sel.get("name")
        opt = sel.select_one("option[selected]") or sel.select_one("option")
        data[sel_name] = opt.get("value", "") if opt is not None else ""
    
    # Verificar campos críticos de ASP.NET
    critical_fields = ["__VIEWSTATE", "__EVENTVALIDATION", "__VIEWSTATEGENERATOR"]
    for k in critical_fields:
        status = "✅ OK" if data.get(k) else "❌ NO"
        log(f"   · {k}: {status}")
    
    return action, data, form

def derive_eventtarget_for_select(sel):
    onchange = sel.get("onchange") or ""
    m = re.search(r"__doPostBack\('([^']+)'", onchange)
    if m:
        et = m.group(1)
        log(f"   🎯 EVENTTARGET derivado de onchange: {et}")
        return et
    
    if sel.get("id"):
        et = sel.get("id").replace("_", "$")
        log(f"   🎯 EVENTTARGET desde id -> {et}")
        return et
    
    et = (sel.get("name") or "").replace(":", "$")
    log(f"   🎯 EVENTTARGET desde name -> {et}")
    return et

def maybe_extract_updatepanel(html):
    """Si la respuesta es un Delta de ASP.NET (UpdatePanel), extrae los fragmentos HTML."""
    if not html:
        return html
    # Heurística básica para detectar delta
    if html.count('|') > 5 and ('updatePanel' in html or 'hiddenField' in html):
        parts = html.split('|')
        fragments = []
        for i in range(len(parts) - 2):
            if parts[i] == 'updatePanel':
                fragments.append(parts[i+2])
        if fragments:
            joined = ''.join(fragments)
            return joined
    return html

def post_with_retries(session, action, data, headers, timeout=30, tries=2, backoff=0.75):
    last_exc = None
    for attempt in range(1, tries+1):
        try:
            resp = session.post(action, data=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            if not resp.encoding:
                resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp
        except (ReadTimeout, ConnectionError, requests.HTTPError) as e:
            last_exc = e
            log(f"   ⚠️  POST fallo intento {attempt}/{tries}: {e}")
            if attempt < tries:
                sleep_s = backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                time.sleep(sleep_s)
    raise last_exc if last_exc else RuntimeError("POST desconocido")

def postback(session, action, payload, eventtarget, field_name=None, field_value=None, referer=None, dbg_title=""):
    p = payload.copy()
    p["__EVENTTARGET"] = eventtarget
    p["__EVENTARGUMENT"] = ""
    p["__ASYNCPOST"] = "true"  # Forzar modo asíncrono (UpdatePanel)
    if field_name is not None and field_value is not None:
        p[field_name] = field_value
    
    log(f"   📤 POSTBACK → TARGET={eventtarget} | FIELD={field_name} | VALUE={field_value}")
    
    try:
        headers = {**HEADERS, "Referer": referer or "", "X-MicrosoftAjax": "Delta=true"}
        resp = post_with_retries(session, action, p, headers=headers, timeout=30, tries=2)
        html = resp.text
        
        # Extraer HTML de UpdatePanel si aplica
        html = maybe_extract_updatepanel(html)

        # Análisis de respuesta
        log(f"   📥 Respuesta: HTTP {resp.status_code} | Tamaño: {len(html):,} chars")
        
        if dbg_title:
            save_debug_html(html, f"debug_{dbg_title}")
        
        # Pequeña pausa aleatoria para no martillar
        time.sleep(random.uniform(0.4, 1.1))

        return html
        
    except Exception as e:
        log(f"   ❌ Error en postback: {e}")
        return ""

# --------- localizar selects ----------
def list_all_selects(form):
    log("🔍 Selects encontrados:")
    for i, sel in enumerate(form.select("select[name]"), 1):
        name = sel.get("name")
        sid = sel.get("id")
        opts = [o.get_text(strip=True) for o in sel.select("option")[:5]]
        total_opts = len(sel.select("option"))
        log(f"   [{i}] name={name}")
        log(f"       id={sid}")
        log(f"       opciones: {total_opts} total | primeras: {opts}")
        if total_opts > 5:
            log(f"       ...")

def find_group_select(form):
    log("🔍 Buscando select de grupos...")
    for sel in form.select("select[name]"):
        texts = " | ".join(o.get_text(strip=True) for o in sel.select("option")[:40]).lower()
        if any(k in texts for k in ["liga regular", "fase final", "eliminatoria", "grupo"]):
            log(f"   ✅ Encontrado por contenido: {sel.get('name')}")
            return sel
    
    # Búsqueda por nombre específico
    backup = form.select_one(
        "select#_ctl0_MainContentPlaceHolderMaster_gruposDropDownList, "
        "select[name='_ctl0:MainContentPlaceHolderMaster:gruposDropDownList']"
    )
    if backup:
        log(f"   ✅ Encontrado por nombre específico: {backup.get('name')}")
    return backup

def find_jornada_select(form):
    log("🔍 Buscando select de jornadas...")
    for sel in form.select("select[name]"):
        txts = [o.get_text(strip=True) for o in sel.select("option")]
        if any(re.search(r"\bjornada\b", t, re.I) for t in txts):
            log(f"   ✅ Encontrado select de jornadas: {sel.get('name')} ({len(txts)} opciones)")
            # DEBUG: Mostrar todas las opciones de jornada
            log("   📋 Opciones de jornada encontradas:")
            for i, opt in enumerate(sel.select("option"), 1):
                val = opt.get("value", "")
                txt = opt.get_text(strip=True)
                selected = "SELECTED" if opt.has_attr("selected") else ""
                log(f"      [{i:2d}] value='{val}' text='{txt}' {selected}")
            return sel
    log("   ❌ No se encontró select de jornadas")
    return None

def find_season_select(form):
    """Localiza el select de temporadas."""
    log("🔍 Buscando select de TEMPORADAS...")
    sel = form.select_one(
        "select#_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList, "
        "select[name='_ctl0:MainContentPlaceHolderMaster:temporadasDropDownList']"
    )
    if sel:
        log(f"   ✅ Select temporadas encontrado: name={sel.get('name')} id={sel.get('id')}")
        return sel
    for cand in form.select("select[name]"):
        texts = " | ".join(o.get_text(strip=True) for o in cand.select("option")[:40]).lower()
        if re.search(r"\b20\d{2}/20\d{2}\b", texts):
            log(f"   ✅ Select temporadas encontrado por contenido: {cand.get('name')}")
            return cand
    log("   ❌ No se encontró select de temporadas")
    return None

# --------- validación de contenido ----------
def is_valid_team_name(name):
    """Filtros para descartar texto que no son nombres de equipos"""
    if not name or len(name) < 3:
        return False
    
    forbidden_words = [
        'contacto', 'aviso legal', 'política', 'cookies', 'federación', 
        'privacidad', 'copyright', '©️', 'cumplimiento', 'directiva',
        'navegación', 'usuario', 'sitio web', 'configuración', 'navegador',
        'baloncesto', 'feb.es', 'deshabilite', 'utiliza', 'mediante'
    ]
    name_lower = name.lower()
    if any(word in name_lower for word in forbidden_words):
        return False
    
    if len(name) > 80:
        return False
        
    legal_words = ['cumplimiento', 'directiva', 'informa', 'utiliza', 'mediante', 'navegación']
    if sum(1 for word in legal_words if word in name_lower) >= 2:
        return False
    
    return True

def check_page_content(html, grupo_name):
    """Verifica si la página contiene datos reales de partidos"""
    soup = BeautifulSoup(html, "lxml")
    party_indicators = ["jornada", "local", "visitante", "resultado", "fecha", "hora", "vs", "partido", "calendario"]
    text_content = soup.get_text().lower()
    found_indicators = sum(1 for indicator in party_indicators if indicator in text_content)
    empty_messages = ["no hay datos", "sin partidos", "no se encontraron", "temporada no iniciada", "grupo vacío", "no hay información"]
    has_empty_message = any(msg in text_content for msg in empty_messages)
    tables = len(soup.select("table"))
    
    calendar_tables = soup.select("table.calendario, table[class*='calendar'], table[id*='calendar']")
    match_links = soup.select("a[href*='Partido.aspx?p=']")
    
    log(f"  🔍 Análisis contenido '{grupo_name}':")
    log(f"    📊 Indicadores partidos: {found_indicators}/{len(party_indicators)}")
    log(f"    📊 Tablas totales: {tables}")
    log(f"    📊 Tablas calendario: {len(calendar_tables)}")
    log(f"    📊 Enlaces partido: {len(match_links)}")
    log(f"    📊 Mensajes vacío: {has_empty_message}")
    log(f"    📊 Longitud HTML: {len(html):,} chars")
    
    is_valid = (
        (found_indicators >= 3 and not has_empty_message) or 
        len(match_links) >= 1 or
        len(calendar_tables) >= 1
    )
    
    if not is_valid:
        log(f"  ❌ Página parece vacía o sin partidos reales")
        sample_text = ' '.join(text_content.split()[:50])
        log(f"    💬 Muestra HTML: '{sample_text}...'")
    else:
        log(f"  ✅ Página parece contener partidos")
        if match_links[:3]:
            sample_links = [link.get('href') for link in match_links[:3]]
            log(f"    🔗 Enlaces ejemplo: {sample_links}")
    
    return is_valid

# --------- helpers de parsing ----------
def text_norm(s): 
    return re.sub(r"\s+", " ", s or "").strip()

# --------- parser mejorado: jornada y FECHA desde el H1, + enlaces equipos + RESULTADO ----------
JORNADA_Y_FECHA_RE = re.compile(r'jornada\s*(\d+)\s+(\d{2}/\d{2}/\d{4})', re.I)
JORNADA_SOLO_RE = re.compile(r'jornada\s*(\d+)', re.I)
RESULTADO_RE = re.compile(r'(\d+)\s*-\s*(\d+)')  # captura "##-##" con espacios opcionales

def extract_resultado_from_tr(tr):
    """Devuelve texto resultado 'NN-NN' si existe, si no None."""
    td_res = tr.select_one("td.resultado")
    if not td_res:
        return None
    # prefiero el texto del <a>, si no existe, el propio td
    a = td_res.find("a")
    raw = text_norm(a.get_text()) if a else text_norm(td_res.get_text())
    m = RESULTADO_RE.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None

def parse_matches(html, grupo_name="", liga_numero=None):
    log(f"  🔄 Parseando partidos en '{grupo_name}' (Liga {liga_numero})...")
    soup = BeautifulSoup(html, "lxml")
    rows = []

    # Buscar columnas de jornadas (div.columna)
    log("  🔍 Buscando columnas de jornadas...")
    columnas = soup.select("div.columna")
    log(f"    📊 Columnas encontradas: {len(columnas)}")
    
    if columnas:
        for col_idx, columna in enumerate(columnas, 1):
            # ---- Jornada y FECHA desde el H1 de la columna ----
            h1_jornada = columna.select_one("h1.titulo-modulo")
            jornada_title = None
            fecha_col = None
            if h1_jornada:
                title_text = text_norm(h1_jornada.get_text())
                m = JORNADA_Y_FECHA_RE.search(title_text)
                if m:
                    jornada_title = f"Jornada {m.group(1)}"
                    fecha_col = m.group(2)           # ← FECHA tomada del H1
                    log(f"    📅 Columna {col_idx}: {jornada_title} | Fecha {fecha_col}")
                else:
                    m2 = JORNADA_SOLO_RE.search(title_text)
                    if m2:
                        jornada_title = f"Jornada {m2.group(1)}"
                        log(f"    📅 Columna {col_idx}: {jornada_title} | Fecha en H1 NO encontrada")
                    else:
                        jornada_title = title_text
                        log(f"    📅 Columna {col_idx}: {jornada_title} (formato no estándar)")
            else:
                jornada_title = f"Jornada {col_idx}"
                log(f"    📅 Columna {col_idx}: Sin H1 - usando '{jornada_title}'")

            # Tabla de partidos
            tabla = columna.select_one("table")
            if not tabla:
                log(f"      ❌ No hay tabla en columna {col_idx}")
                continue
                
            filas_partidos = tabla.select("tbody tr")
            log(f"      📊 Filas en tabla: {len(filas_partidos)}")
            
            for fila_idx, tr in enumerate(filas_partidos, 1):
                # Enlace del partido (para ID/URL) — puede estar en td.fecha o td.resultado
                a_partido = tr.select_one("td.fecha a[href*='Partido.aspx?p='], td.resultado a[href*='Partido.aspx?p=']")
                partido_url = urljoin(BASE, a_partido.get("href")) if a_partido and a_partido.get("href") else None
                partido_id = None
                if partido_url:
                    try:
                        q = parse_qs(urlparse(partido_url).query)
                        partido_id = (q.get("p") or [None])[0]
                    except Exception:
                        pass

                # Nombres + enlaces de equipos
                a_local = tr.select_one("td.equipo.local a[href*='Equipo.aspx?i=']")
                a_visit = tr.select_one("td.equipo.visitante a[href*='Equipo.aspx?i=']")
                local = text_norm(a_local.get_text()) if a_local else None
                visitante = text_norm(a_visit.get_text()) if a_visit else None
                local_url = urljoin(BASE, a_local.get("href")) if a_local and a_local.get("href") else None
                visit_url = urljoin(BASE, a_visit.get("href")) if a_visit and a_visit.get("href") else None

                # Fallbacks compatibilidad clases antiguas
                if not local or not visitante:
                    td_local = tr.select_one("td.equipo_local")
                    td_visitante = tr.select_one("td.equipo_visitante")
                    if (not local) and td_local:
                        a = td_local.select_one("a[href*='Equipo.aspx?i=']")
                        if a and a.get("href"):
                            local = text_norm(a.get_text()); local_url = urljoin(BASE, a.get("href"))
                        else:
                            local = text_norm(td_local.get_text())
                    if (not visitante) and td_visitante:
                        a = td_visitante.select_one("a[href*='Equipo.aspx?i=']")
                        if a and a.get("href"):
                            visitante = text_norm(a.get_text()); visit_url = urljoin(BASE, a.get("href"))
                        else:
                            visitante = text_norm(td_visitante.get_text())

                # Último recurso: textos válidos
                if not local or not visitante:
                    all_tds = tr.select("td")
                    texts = [text_norm(td.get_text()) for td in all_tds if text_norm(td.get_text())]
                    valid_texts = [txt for txt in texts if is_valid_team_name(txt)]
                    if len(valid_texts) >= 2:
                        local = local or valid_texts[0]
                        visitante = visitante or valid_texts[-1]

                # FECHA final desde H1 cercano si no estaba en el H1 de la columna (fallback)
                fecha_final = fecha_col
                if not fecha_final:
                    h1_prev = tr.find_previous('h1', class_='titulo-modulo')
                    if h1_prev:
                        t = text_norm(h1_prev.get_text())
                        mprev = JORNADA_Y_FECHA_RE.search(t)
                        if mprev:
                            fecha_final = mprev.group(2)

                # Resultado (si existe)
                resultado = extract_resultado_from_tr(tr)

                if local and visitante and local != visitante:
                    row_data = {
                        "liga": f"Liga {liga_numero}" if liga_numero else "Sin especificar",
                        "jornada": jornada_title or "Sin especificar",
                        "fecha": fecha_final,                 # ← SOLO fecha (desde H1)
                        "resultado": resultado,               # ← NUEVO
                        "local": local,
                        "local_url": local_url,
                        "visitante": visitante,
                        "visitante_url": visit_url,
                        "partido_id": partido_id,
                        "partido_url": partido_url,
                        "raw": f"COL:{col_idx} | {local} vs {visitante}"
                    }
                    rows.append(row_data)
                    log(f"        [{fila_idx:2d}] {row_data['fecha']} - {local} ({local_url}) {('['+resultado+']') if resultado else ''} vs {visitante} ({visit_url}) | {row_data['jornada']}")

    # FALLBACK: Sin columnas → buscar por enlaces y obtener fecha/resultado desde H1/td.resultado
    if not rows:
        log("  🔄 Fallback: buscando enlaces de partidos directamente...")
        match_links = soup.select("a[href*='Partido.aspx?p=']")
        log(f"    📊 Enlaces de partido encontrados: {len(match_links)}")

        for i, link in enumerate(match_links, 1):
            partido_url = urljoin(BASE, link.get('href'))
            partido_id = None
            if partido_url:
                try:
                    q = parse_qs(urlparse(partido_url).query)
                    partido_id = (q.get("p") or [None])[0]
                except Exception:
                    pass

            tr = link.find_parent('tr')
            if not tr:
                continue

            # Jornada/fecha desde H1 anterior
            h1_prev = tr.find_previous('h1', class_='titulo-modulo')
            jornada_title = "Sin especificar"
            fecha_final = None
            if h1_prev:
                t = text_norm(h1_prev.get_text())
                m = JORNADA_Y_FECHA_RE.search(t)
                if m:
                    jornada_title = f"Jornada {m.group(1)}"
                    fecha_final = m.group(2)
                else:
                    m2 = JORNADA_SOLO_RE.search(t)
                    if m2:
                        jornada_title = f"Jornada {m2.group(1)}"

            # Equipos y URLs
            local = visitante = None
            local_url = visit_url = None
            a_local = tr.select_one("td.equipo.local a[href*='Equipo.aspx?i=']")
            a_visit = tr.select_one("td.equipo.visitante a[href*='Equipo.aspx?i=']")
            if a_local and a_local.get("href"):
                local = text_norm(a_local.get_text()); local_url = urljoin(BASE, a_local.get("href"))
            if a_visit and a_visit.get("href"):
                visitante = text_norm(a_visit.get_text()); visit_url = urljoin(BASE, a_visit.get("href"))

            if not local or not visitante:
                td_local = tr.select_one("td.equipo_local")
                td_visitante = tr.select_one("td.equipo_visitante")
                if (not local) and td_local:
                    a = td_local.select_one("a[href*='Equipo.aspx?i=']")
                    if a and a.get("href"):
                        local = text_norm(a.get_text()); local_url = urljoin(BASE, a.get("href"))
                    else:
                        local = text_norm(td_local.get_text())
                if (not visitante) and td_visitante:
                    a = td_visitante.select_one("a[href*='Equipo.aspx?i=']")
                    if a and a.get("href"):
                        visitante = text_norm(a.get_text()); visit_url = urljoin(BASE, a.get("href"))
                    else:
                        visitante = text_norm(td_visitante.get_text())

            # Resultado si existe
            resultado = extract_resultado_from_tr(tr)

            if local and visitante and local != visitante:
                row_data = {
                    "liga": f"Liga {liga_numero}" if liga_numero else "Sin especificar",
                    "jornada": jornada_title,
                    "fecha": fecha_final,                 # ← Fecha desde H1 si disponible
                    "resultado": resultado,               # ← NUEVO
                    "local": local,
                    "local_url": local_url,
                    "visitante": visitante,
                    "visitante_url": visit_url,
                    "partido_id": partido_id,
                    "partido_url": partido_url,
                    "raw": f"LINK | {local} vs {visitante}"
                }
                rows.append(row_data)
                log(f"      [{i:2d}] {row_data['fecha']} - {local} ({local_url}) {('['+resultado+']') if resultado else ''} vs {visitante} ({visit_url}) | {row_data['jornada']}")

    log(f"    📊 Total partidos extraídos: {len(rows)}")
    return rows

def parse_matches_with_validation(html, grupo_name, liga_numero=None):
    if not check_page_content(html, grupo_name):
        log(f"  ⏭️  Saltando parseo de '{grupo_name}' - página sin contenido válido")
        return []
    return parse_matches(html, grupo_name, liga_numero)

# --------- guardar CSV ----------
def save_to_csv(all_rows, filename_suffix=""):
    """Guarda los datos en CSV con nombre fijo 'datos_completos.csv' en la carpeta data/"""
    if not all_rows:
        log("❌ No hay datos para guardar en CSV")
        return None
    
    # Usar ruta fija como en final_pdf.py
    from pathlib import Path
    
    # Crear la carpeta data si no existe
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Nombre fijo del archivo
    filename = data_dir / "datos_completos.csv"
    
    # Columnas (añadimos 'liga' y 'resultado')
    columns = [
        'liga', 'grupo', 'jornada', 'fecha', 'resultado',
        'local', 'local_url', 'visitante', 'visitante_url',
        'partido_id', 'partido_url', 'raw'
    ]
    
    try:
        df = pd.DataFrame(all_rows, columns=columns)
        df.to_csv(filename, index=False, encoding='utf-8')
        
        log(f"✅ CSV guardado: {filename}")
        log(f"   📊 Total registros: {len(df)}")
        log(f"   📋 Columnas: {list(df.columns)}")
        
        ligas_unicas = df['liga'].nunique()
        grupos_unicos = df['grupo'].nunique()
        jornadas_unicas = df['jornada'].nunique()
        log(f"   📈 Estadísticas: {ligas_unicas} ligas, {grupos_unicos} grupos únicos, {jornadas_unicas} jornadas únicas")
        
        return str(filename)  # Retornar como string
        
    except Exception as e:
        log(f"❌ Error guardando CSV: {e}")
        return None

# --------- flujo principal para una liga ----------
def scrape_single_liga(liga_numero):
    """Scrapea una liga específica y devuelve los datos"""
    hr(f"SCRAPING LIGA {liga_numero}")
    URL = BASE_URL_TEMPLATE.format(liga_numero)
    log(f"🌐 URL para Liga {liga_numero}: {URL}")
    
    s = requests.Session()
    s.headers.update(HEADERS)

    try:
        r = s.get(URL, timeout=30)
        r.raise_for_status()
        if not r.encoding:
            r.encoding = r.apparent_encoding or 'utf-8'
        log(f"✅ Página Liga {liga_numero} cargada: {len(r.text):,} caracteres")
        save_debug_html(r.text, f"liga_{liga_numero}_inicial")
        
    except Exception as e:
        log(f"❌ Error cargando página Liga {liga_numero}: {e}")
        return []
    
    soup = BeautifulSoup(r.text, "lxml")
    action, payload, form = serialize_form(soup, URL)

    list_all_selects(form)

    # === Selección de TEMPORADA (antes que grupos) ===
    desired_label = f"{TARGET_SEASON_YEAR}/{TARGET_SEASON_YEAR+1}"
    log(f"🔄 Verificando temporada → {desired_label}")
    sel_season = find_season_select(form)
    if sel_season:
        season_opts = []
        selected_text = None
        for opt in sel_season.select("option"):
            val = (opt.get("value") or "").strip()
            txt = opt.get_text(strip=True)
            is_sel = opt.has_attr("selected")
            season_opts.append((val, txt, is_sel))
            if is_sel:
                selected_text = txt
        log(f"📊 Total temporadas disponibles: {len(season_opts)} | Seleccionada: {selected_text}")

        if TARGET_SEASON_YEAR == 2025:
            log("ℹ️ Temporada objetivo es 2025/2026 (por defecto) → no se hace postback de temporada.")
            html_after_season = r.text
        else:
            match = next((o for o in season_opts if o[1] == desired_label), None)
            if not match:
                log(f"⚠️ No se encontró la temporada '{desired_label}'. Se mantiene la actual.")
                html_after_season = r.text
            else:
                val, txt, is_sel = match
                if is_sel:
                    log("ℹ️ La temporada deseada ya está seleccionada → sin postback.")
                    html_after_season = r.text
                else:
                    log(f"🔄 Haciendo postback para cambiar a temporada '{txt}' (value={val})")
                    season_eventtarget = derive_eventtarget_for_select(sel_season)
                    html_after_season = postback(
                        s, action, payload, season_eventtarget,
                        field_name=sel_season.get("name"), field_value=val,
                        referer=URL, dbg_title=f"liga_{liga_numero}_temporada_{TARGET_SEASON_YEAR}"
                    )
                    if not html_after_season:
                        log("❌ Postback de temporada no devolvió HTML. Continuamos con la actual.")
                        html_after_season = r.text

        soup = BeautifulSoup(html_after_season, "lxml")
        try:
            action, payload, form = serialize_form(soup, URL)
        except Exception as e:
            log(f"⚠️ Error actualizando form state tras cambiar temporada: {e}")
    else:
        log("⚠️ No se encontró select de temporadas. Se continúa sin cambio de temporada.")
        html_after_season = r.text

    # ======= SELECCIÓN DE GRUPOS/JORNADAS =======
    log("🔍 Localizando select de GRUPOS")
    sel_groups = find_group_select(form)
    if not sel_groups: 
        log("❌ No se encontró el select de grupos.")
        return []
    
    g_name = sel_groups.get("name")
    g_id = sel_groups.get("id")
    log(f"✅ Select grupos → name={g_name} | id={g_id}")
    g_eventtarget = derive_eventtarget_for_select(sel_groups)

    options = []
    selected_index = -1
    for i, o in enumerate(sel_groups.select("option")):
        val = (o.get("value") or "").strip()
        lab = o.get_text(strip=True)
        is_selected = o.has_attr("selected")
        if val: 
            options.append((val, lab, is_selected))
            if is_selected:
                selected_index = i
    
    log(f"📊 Total grupos disponibles: {len(options)}")
    for i, (v, l, sel) in enumerate(options[:15], 1): 
        status = "SELECCIONADO" if sel else ""
        log(f"  [{i:2d}] value={v} → '{l}' {status}")
    if len(options) > 15: 
        log("  ...")

    grupos_iter = options if FULL_RUN else options[:MAX_GRUPOS_PRUEBA]
    log(f"🎯 Procesando {len(grupos_iter)} grupos...")
    
    all_rows = []
    html_base = html_after_season

    for gi, (gval, glabel, is_default) in enumerate(grupos_iter, 1):
        log(f"\n📁 GRUPO {gi}/{len(grupos_iter)}: {glabel}")
        
        if is_default:
            log(f"🔄 Grupo por defecto detectado - usando página actual SIN postback")
            html_group = html_base
        else:
            log(f"🔄 Haciendo postback para grupo: value={gval}")
            html_group = postback(s, action, payload, g_eventtarget, g_name, gval, 
                                 referer=URL, dbg_title=f"liga_{liga_numero}_grupo_{gi:02d}_{gval}")
        
        if not html_group:
            log(f"❌ Error obteniendo datos del grupo {glabel}")
            continue
        
        soup_g = BeautifulSoup(html_group, "lxml")
        try:
            action, payload_g, form_g = serialize_form(soup_g, URL)
        except Exception as e:
            log(f"⚠️ Error actualizando form state para grupo {glabel}: {e}")
            payload_g = payload.copy()
            form_g = form

        sel_j = find_jornada_select(form_g)
        if sel_j:
            j_name = sel_j.get("name")
            j_et = derive_eventtarget_for_select(sel_j)
            j_opts = []
            for opt in sel_j.select("option"):
                val = (opt.get("value") or "").strip()
                txt = opt.get_text(strip=True)
                is_sel = opt.has_attr("selected")
                if val:
                    j_opts.append((val, txt, is_sel))
            log(f"✅ Select jornadas encontrado: {len(j_opts)} opciones")
            
            jornadas_iter = j_opts if FULL_RUN else j_opts[:MAX_JORNADAS_PRUEBA]
            for ji, (jval, jlab, is_j_default) in enumerate(jornadas_iter, 1):
                log(f"  📅 Jornada {ji}/{len(jornadas_iter)}: '{jlab}' (value={jval})")
                
                if is_j_default and gi == 1:
                    log(f"    🔄 Jornada por defecto - usando HTML actual")
                    html_j = html_group
                else:
                    log(f"    🔄 Haciendo postback para jornada")
                    html_j = postback(s, action, payload_g, j_et, j_name, jval, 
                                     referer=URL, dbg_title=f"liga_{liga_numero}_grupo_{gi:02d}jornada{ji:02d}")
                
                if not html_j:
                    log(f"    ❌ Error obteniendo jornada {jlab}")
                    continue
                
                rows = parse_matches_with_validation(html_j, f"{glabel} - {jlab}", liga_numero)
                for r in rows:
                    r["grupo"] = glabel
                    if not r.get("jornada") or r["jornada"] == "Sin especificar":
                        r["jornada"] = jlab
                all_rows.extend(rows)
                log(f"    📊 Partidos agregados: {len(rows)} | Total Liga {liga_numero}: {len(all_rows)}")
                
                if not (is_j_default and gi == 1):
                    try:
                        soup_j = BeautifulSoup(html_j, "lxml")
                        action, payload_g, form_g = serialize_form(soup_j, URL)
                    except Exception as e:
                        log(f"    ⚠️ Error actualizando form state jornada: {e}")
        else:
            log("ℹ️  No hay select de jornadas, procesando página actual...")
            rows = parse_matches_with_validation(html_group, glabel, liga_numero)
            for r in rows: 
                r["grupo"] = glabel
            all_rows.extend(rows)
            log(f"  📊 Partidos del grupo: {len(rows)} | Total Liga {liga_numero}: {len(all_rows)}")

        if not is_default:
            try:
                soup_g = BeautifulSoup(html_group, "lxml")
                action, payload, form = serialize_form(soup_g, URL)
            except Exception as e:
                log(f"  ⚠️ Error actualizando form state grupo: {e}")

    log(f"🎉 Liga {liga_numero} completada! Total partidos: {len(all_rows)}")
    return all_rows

# --------- flujo principal multi-liga ----------
def main():
    """Flujo principal que scrapea múltiples ligas y genera CSV combinado"""
    log("🚀 Iniciando scraper multi-liga FEB...")
    os.makedirs("debug_html", exist_ok=True)
    
    all_data_combined = []
    ligas_procesadas = []
    
    for liga_num in LIGAS_A_SCRAPEAR:
        log(f"\n" + "="*80)
        log(f"🏀 INICIANDO SCRAPING LIGA {liga_num}")
        log(f"="*80)
        
        try:
            datos_liga = scrape_single_liga(liga_num)
            if datos_liga:
                all_data_combined.extend(datos_liga)
                ligas_procesadas.append(liga_num)
                log(f"✅ Liga {liga_num} procesada exitosamente: {len(datos_liga)} partidos")
            else:
                log(f"⚠️ Liga {liga_num} no devolvió datos")
        except Exception as e:
            log(f"❌ Error procesando Liga {liga_num}: {e}")
            continue
    
    # ===== GUARDAR RESULTADOS COMBINADOS =====
    hr("GUARDAR RESULTADOS FINALES")
    if all_data_combined:
        ligas_suffix = "".join(map(str, ligas_procesadas))
        log(f"🎉 Scraping multi-liga completado!")
        log(f"📊 Resumen total:")
        log(f"   • Ligas procesadas: {ligas_procesadas}")
        log(f"   • Total partidos: {len(all_data_combined)}")
        
        # Estadísticas por liga
        ligas_stats = {}
        for row in all_data_combined:
            liga = row.get('liga', 'Sin especificar')
            ligas_stats[liga] = ligas_stats.get(liga, 0) + 1
        
        for liga, count in ligas_stats.items():
            log(f"   • {liga}: {count} partidos")
        
        grupos_unicos = set(r['grupo'] for r in all_data_combined if r.get('grupo'))
        jornadas_unicas = set(r['jornada'] for r in all_data_combined if r.get('jornada'))
        log(f"   • Grupos únicos: {len(grupos_unicos)}")
        log(f"   • Jornadas únicas: {len(jornadas_unicas)}")
        
        csv_file = save_to_csv(all_data_combined, ligas_suffix)
        if csv_file:
            log(f"✅ Datos combinados guardados exitosamente en: {csv_file}")
        else:
            log(f"❌ Error guardando CSV, pero los datos están en memoria")
            
        log("📋 Muestra de datos combinados:")
        for i, row in enumerate(all_data_combined[:8], 1):
            log(f"   [{i}] {row.get('liga')} | {row['grupo']} | {row['jornada']} | {row.get('fecha')} | {row.get('resultado')} | {row['local']} vs {row['visitante']}")
        if len(all_data_combined) > 8:
            log(f"   ... y {len(all_data_combined) - 8} partidos más")
            
        return csv_file
    else:
        log("❌ No se extrajeron partidos de ninguna liga. Revisa los logs para identificar problemas.")
        return None

# ===== EJECUTAR EL PROGRAMA =====
if __name__ == "__main__":
    resultado = main()
    if resultado:
        log(f"\n🎯 PROCESO COMPLETADO - Archivo generado: {resultado}")
    else:
        log(f"\n❌ PROCESO FALLÓ - No se generó archivo")