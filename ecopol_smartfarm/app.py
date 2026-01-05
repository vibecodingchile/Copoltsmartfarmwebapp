import json
import time
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Opcionales según conector
try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

try:
    from pymodbus.client import ModbusTcpClient
except Exception:
    ModbusTcpClient = None


# -----------------------------
# Config general Streamlit
# -----------------------------
st.set_page_config(page_title="Ecopol SmartFarm (MVP)", layout="wide")

# -----------------------------
# DB simple (SQLite)
# -----------------------------
DB_PATH = "data/demo.sqlite"


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db_init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          phone TEXT,
          email TEXT,
          address TEXT,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS sites(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          location TEXT,
          type TEXT, -- 'Avícola' / 'Porcina' / 'Mixta'
          FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS equipment(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          site_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          category TEXT, -- 'Climatización' 'Alimentación' 'Agua' 'Calefacción' 'Sensores'
          model TEXT,
          serial TEXT,
          install_date TEXT,
          status TEXT, -- 'Operativo' 'En observación' 'Fuera de servicio'
          FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sensor_sources(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          site_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          protocol TEXT NOT NULL, -- 'HTTP' 'MQTT' 'MODBUS' 'CSV' 'MANUAL'
          config_json TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sensor_readings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          site_id INTEGER NOT NULL,
          source_id INTEGER,
          ts TEXT NOT NULL,
          metric TEXT NOT NULL, -- 'temp_c', 'hum_pct', 'co2_ppm', 'nh3_ppm', 'water_lpm', etc.
          value REAL NOT NULL,
          meta_json TEXT,
          FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
          FOREIGN KEY(source_id) REFERENCES sensor_sources(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS thresholds(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          site_id INTEGER NOT NULL,
          metric TEXT NOT NULL,
          min_value REAL,
          max_value REAL,
          warn_min REAL,
          warn_max REAL,
          enabled INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS maintenance(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          site_id INTEGER NOT NULL,
          equipment_id INTEGER,
          type TEXT NOT NULL, -- 'Preventivo' 'Correctivo'
          status TEXT NOT NULL, -- 'Programado' 'En curso' 'Cerrado'
          priority TEXT NOT NULL, -- 'Baja' 'Media' 'Alta'
          scheduled_for TEXT,
          performed_at TEXT,
          description TEXT,
          actions_taken TEXT,
          parts_used TEXT,
          next_due TEXT,
          FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
          FOREIGN KEY(equipment_id) REFERENCES equipment(id) ON DELETE SET NULL
        );
        """
    )
    conn.commit()


def seed_demo(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM clients")
    if cur.fetchone()[0] > 0:
        return

    # Cliente + sitio + equipos
    cur.execute("INSERT INTO clients(name, phone, email, address, notes) VALUES (?,?,?,?,?)",
                ("Granja Los Robles", "+56 9 1234 5678", "contacto@cliente.cl", "Región del Maule", "Cliente demo"))
    client_id = cur.lastrowid

    cur.execute("INSERT INTO sites(client_id, name, location, type) VALUES (?,?,?,?)",
                (client_id, "Sitio 1 - Galpones", "Maule, Chile", "Avícola"))
    site_id = cur.lastrowid

    equipments = [
        ("Controlador Temp ITC10", "Climatización", "ITC10", "SN-ITC10-001", "2025-11-01", "Operativo"),
        ("Sistema Transporte Espiral", "Alimentación", "Spiral-01", "SN-SP-009", "2025-10-15", "Operativo"),
        ("Línea de Bebederos", "Agua", "WaterLine-X", "SN-WL-120", "2025-10-20", "En observación"),
        ("Radiador Infrarrojo", "Calefacción", "IR-Heat", "SN-IR-777", "2025-10-18", "Operativo"),
    ]
    for name, cat, model, serial, d, status in equipments:
        cur.execute("""
            INSERT INTO equipment(site_id, name, category, model, serial, install_date, status)
            VALUES (?,?,?,?,?,?,?)
        """, (site_id, name, cat, model, serial, d, status))

    # Umbrales demo
    cur.execute("""
        INSERT INTO thresholds(site_id, metric, min_value, max_value, warn_min, warn_max, enabled)
        VALUES (?,?,?,?,?,?,1)
    """, (site_id, "temp_c", 18, 28, 19, 27))
    cur.execute("""
        INSERT INTO thresholds(site_id, metric, min_value, max_value, warn_min, warn_max, enabled)
        VALUES (?,?,?,?,?,?,1)
    """, (site_id, "hum_pct", 45, 70, 50, 65))

    # Fuente demo MANUAL
    config = {"note": "Fuente demo. En producción se reemplaza por HTTP/MQTT/Modbus."}
    cur.execute("""
        INSERT INTO sensor_sources(site_id, name, protocol, config_json, enabled)
        VALUES (?,?,?,?,1)
    """, (site_id, "Sensores Demo", "MANUAL", json.dumps(config)))

    source_id = cur.lastrowid

    # Lecturas demo
    now = datetime.now()
    for i in range(48):
        ts = (now - timedelta(minutes=30*i)).isoformat(timespec="seconds")
        # valores semi-realistas
        temp = 22.0 + (i % 6) * 0.2
        hum = 58.0 + (i % 5) * 0.6
        cur.execute("""
            INSERT INTO sensor_readings(site_id, source_id, ts, metric, value, meta_json)
            VALUES (?,?,?,?,?,?)
        """, (site_id, source_id, ts, "temp_c", temp, None))
        cur.execute("""
            INSERT INTO sensor_readings(site_id, source_id, ts, metric, value, meta_json)
            VALUES (?,?,?,?,?,?)
        """, (site_id, source_id, ts, "hum_pct", hum, None))

    # Mantenimiento demo
    cur.execute("""
        INSERT INTO maintenance(site_id, equipment_id, type, status, priority, scheduled_for, description, next_due)
        VALUES (?,?,?,?,?,?,?,?)
    """, (site_id, 1, "Preventivo", "Programado", "Media",
          (now + timedelta(days=7)).date().isoformat(),
          "Revisión controlador temperatura / limpieza sensores / verificación relés",
          (now + timedelta(days=90)).date().isoformat()))

    conn.commit()


# -----------------------------
# Lecturas/umbral/alertas
# -----------------------------
def get_sites(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query("""
        SELECT s.id AS site_id, s.name AS site_name, s.type, c.name AS client_name
        FROM sites s
        JOIN clients c ON c.id = s.client_id
        ORDER BY c.name, s.name
    """, conn)


def get_latest_metrics(conn: sqlite3.Connection, site_id: int) -> pd.DataFrame:
    # última lectura por métrica
    return pd.read_sql_query("""
        SELECT metric, value, ts
        FROM sensor_readings
        WHERE site_id = ?
        AND ts IN (
            SELECT MAX(ts) FROM sensor_readings r2
            WHERE r2.site_id = sensor_readings.site_id
            AND r2.metric = sensor_readings.metric
        )
        ORDER BY metric
    """, conn, params=(site_id,))


def get_history(conn: sqlite3.Connection, site_id: int, metric: str, hours: int) -> pd.DataFrame:
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    return pd.read_sql_query("""
        SELECT ts, value
        FROM sensor_readings
        WHERE site_id = ? AND metric = ? AND ts >= ?
        ORDER BY ts
    """, conn, params=(site_id, metric, since))


def get_thresholds(conn: sqlite3.Connection, site_id: int) -> pd.DataFrame:
    return pd.read_sql_query("""
        SELECT id, metric, min_value, max_value, warn_min, warn_max, enabled
        FROM thresholds
        WHERE site_id = ?
        ORDER BY metric
    """, conn, params=(site_id,))


def evaluate_alerts(latest: pd.DataFrame, thr: pd.DataFrame) -> pd.DataFrame:
    if latest.empty or thr.empty:
        return pd.DataFrame(columns=["metric", "value", "status", "message"])

    tmap = {row["metric"]: row for _, row in thr.iterrows()}
    alerts = []
    for _, r in latest.iterrows():
        metric = r["metric"]
        val = float(r["value"])
        if metric not in tmap or int(tmap[metric]["enabled"]) != 1:
            continue

        tr = tmap[metric]
        mn, mx = tr["min_value"], tr["max_value"]
        wmn, wmx = tr["warn_min"], tr["warn_max"]

        status = "OK"
        msg = "Dentro de rango."
        # Crítico
        if (mn is not None and val < mn) or (mx is not None and val > mx):
            status = "CRITICO"
            msg = f"Fuera de rango crítico [{mn}, {mx}]"
        # Advertencia
        elif (wmn is not None and val < wmn) or (wmx is not None and val > wmx):
            status = "ADVERTENCIA"
            msg = f"Cerca de límites [{wmn}, {wmx}]"

        alerts.append({"metric": metric, "value": val, "status": status, "message": msg})
    return pd.DataFrame(alerts)


# -----------------------------
# Conectores de sensores (MVP)
# -----------------------------
def fetch_http_readings(url: str, headers_json: str, timeout_s: int = 5) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Espera JSON tipo:
      [{"metric":"temp_c","value":22.1,"ts":"2026-01-04T10:00:00"} , ...]
    """
    try:
        headers = json.loads(headers_json) if headers_json.strip() else {}
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return False, "Respuesta no es lista JSON.", []
        return True, "OK", data
    except Exception as e:
        return False, f"HTTP error: {e}", []


def mqtt_help_text() -> str:
    return (
        "MQTT: en este MVP mostramos configuración. Para ingestión continua, "
        "lo ideal es un 'collector' externo (servicio) que escriba en la BD."
    )


def modbus_read_example(host: str, port: int, unit_id: int, address: int, count: int) -> Tuple[bool, str, List[int]]:
    if ModbusTcpClient is None:
        return False, "pymodbus no está instalado.", []
    try:
        client = ModbusTcpClient(host=host, port=port, timeout=3)
        if not client.connect():
            return False, "No se pudo conectar a Modbus TCP.", []
        rr = client.read_holding_registers(address=address, count=count, slave=unit_id)
        client.close()
        if rr.isError():
            return False, f"Error Modbus: {rr}", []
        return True, "OK", list(rr.registers)
    except Exception as e:
        return False, f"Modbus error: {e}", []


def save_readings(conn: sqlite3.Connection, site_id: int, source_id: int, readings: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    readings: lista dict con metric, value y opcional ts
    """
    ok = 0
    bad = 0
    cur = conn.cursor()
    for r in readings:
        try:
            metric = str(r["metric"])
            value = float(r["value"])
            ts = r.get("ts") or datetime.now().isoformat(timespec="seconds")
            meta = {k: v for k, v in r.items() if k not in ("metric", "value", "ts")}
            cur.execute("""
                INSERT INTO sensor_readings(site_id, source_id, ts, metric, value, meta_json)
                VALUES (?,?,?,?,?,?)
            """, (site_id, source_id, ts, metric, value, json.dumps(meta) if meta else None))
            ok += 1
        except Exception:
            bad += 1
    conn.commit()
    return ok, bad


# -----------------------------
# UI: Sidebar selección de sitio
# -----------------------------
conn = db_connect()
db_init(conn)
seed_demo(conn)

sites = get_sites(conn)
if sites.empty:
    st.error("No hay sitios configurados.")
    st.stop()

site_label = st.sidebar.selectbox(
    "Selecciona Sitio",
    sites.apply(lambda r: f'{r.client_name} — {r.site_name} ({r.type})', axis=1).tolist(),
)
selected_site_id = int(sites.iloc[sites.apply(lambda r: f'{r.client_name} — {r.site_name} ({r.type})', axis=1).tolist().index(site_label)].site_id)

st.sidebar.markdown("---")
page = st.sidebar.radio("Módulo", ["Dashboard", "Sensores & Conexiones", "Mantenimiento", "Clientes/Equipos", "Reportes"])

# -----------------------------
# DASHBOARD
# -----------------------------
if page == "Dashboard":
    st.title("Ecopol SmartFarm — Dashboard")

    latest = get_latest_metrics(conn, selected_site_id)
    thr = get_thresholds(conn, selected_site_id)
    alerts = evaluate_alerts(latest, thr)

    c1, c2, c3, c4 = st.columns(4)
    # métricas comunes con fallback
    def get_metric(metric: str) -> Optional[float]:
        row = latest[latest.metric == metric]
        if row.empty:
            return None
        return float(row.iloc[0].value)

    temp = get_metric("temp_c")
    hum = get_metric("hum_pct")

    active_alerts = int((alerts.status != "OK").sum()) if not alerts.empty else 0

    c1.metric("Temperatura", f"{temp:.1f} °C" if temp is not None else "—")
    c2.metric("Humedad", f"{hum:.0f} %" if hum is not None else "—")
    c3.metric("Alertas activas", str(active_alerts))
    c4.metric("Última actualización", latest["ts"].max() if not latest.empty else "—")

    st.subheader("Alertas")
    if alerts.empty:
        st.info("Sin alertas configuradas o sin datos.")
    else:
        st.dataframe(alerts, use_container_width=True, hide_index=True)

    st.subheader("Tendencias")
    metric_choice = st.selectbox("Métrica", ["temp_c", "hum_pct"])
    hours = st.slider("Ventana (horas)", 6, 72, 24, 6)
    hist = get_history(conn, selected_site_id, metric_choice, hours)
    if hist.empty:
        st.warning("No hay datos en el rango.")
    else:
        hist["ts"] = pd.to_datetime(hist["ts"])
        fig = px.line(hist, x="ts", y="value", title=f"Histórico {metric_choice}")
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# SENSORES & CONEXIONES
# -----------------------------
elif page == "Sensores & Conexiones":
    st.title("Sensores & Conexiones")

    tab1, tab2, tab3 = st.tabs(["Fuentes", "Ingesta Manual / HTTP", "Modbus / MQTT (config)"])

    with tab1:
        st.subheader("Fuentes de datos configuradas")
        sources = pd.read_sql_query("""
            SELECT id, name, protocol, enabled, config_json
            FROM sensor_sources
            WHERE site_id = ?
            ORDER BY id DESC
        """, conn, params=(selected_site_id,))
        if sources.empty:
            st.info("Sin fuentes. Crea una en las pestañas.")
        else:
            st.dataframe(
                sources.drop(columns=["config_json"]),
                use_container_width=True,
                hide_index=True
            )

    with tab2:
        st.subheader("Crear fuente HTTP / Ingesta Manual")

        colA, colB = st.columns(2)
        with colA:
            protocol = st.selectbox("Protocolo", ["HTTP", "MANUAL", "CSV"])
            source_name = st.text_input("Nombre fuente", value=f"{protocol} - {datetime.now().strftime('%H:%M')}")
        with colB:
            enabled = st.checkbox("Habilitada", value=True)

        config: Dict[str, Any] = {}
        readings_to_save: List[Dict[str, Any]] = []

        if protocol == "HTTP":
            url = st.text_input("URL (GET)", value="https://example.com/sensors")
            headers = st.text_area("Headers JSON (opcional)", value="")
            timeout_s = st.number_input("Timeout (seg)", min_value=1, max_value=20, value=5)
            config = {"url": url, "headers_json": headers, "timeout_s": int(timeout_s)}

            if st.button("Probar conexión HTTP"):
                ok, msg, data = fetch_http_readings(url, headers, int(timeout_s))
                if ok:
                    st.success("Conexión OK. Muestra de datos:")
                    st.json(data[:5])
                    readings_to_save = data
                else:
                    st.error(msg)

        elif protocol == "MANUAL":
            st.caption("Ideal para demo o cuando el dueño registra visitas / mediciones.")
            metric = st.selectbox("Métrica", ["temp_c", "hum_pct", "co2_ppm", "nh3_ppm", "water_lpm", "feed_kg_h"])
            value = st.number_input("Valor", value=0.0)
            ts = st.text_input("Timestamp ISO (opcional)", value="")
            config = {"mode": "manual"}

            if st.button("Guardar lectura manual"):
                readings_to_save = [{"metric": metric, "value": value, "ts": ts.strip() or None}]

        elif protocol == "CSV":
            st.caption("Sube un CSV con columnas: metric,value,ts (ts opcional).")
            up = st.file_uploader("CSV", type=["csv"])
            config = {"mode": "csv_upload"}
            if up is not None:
                df = pd.read_csv(up)
                st.dataframe(df.head(20), use_container_width=True)
                if st.button("Guardar lecturas CSV"):
                    readings_to_save = df.to_dict(orient="records")

        # Guardar fuente + lecturas
        if st.button("Crear/Actualizar fuente (guardar config)"):
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sensor_sources(site_id, name, protocol, config_json, enabled)
                VALUES (?,?,?,?,?)
            """, (selected_site_id, source_name, protocol, json.dumps(config), 1 if enabled else 0))
            conn.commit()
            st.success("Fuente creada.")

        if readings_to_save:
            # Busca última fuente de ese protocolo para asociar lecturas
            src = pd.read_sql_query("""
                SELECT id FROM sensor_sources
                WHERE site_id = ? AND protocol = ?
                ORDER BY id DESC LIMIT 1
            """, conn, params=(selected_site_id, protocol))
            if src.empty:
                st.warning("Crea primero la fuente para asociar lecturas.")
            else:
                source_id = int(src.iloc[0].id)
                okc, badc = save_readings(conn, selected_site_id, source_id, readings_to_save)
                st.success(f"Lecturas guardadas: {okc}. Fallidas: {badc}.")

    with tab3:
        st.subheader("Modbus TCP (lectura de registros - demo)")
        st.caption("Esto muestra conectividad puntual. En producción, recomendamos un collector de fondo.")

        col1, col2, col3, col4, col5 = st.columns(5)
        host = col1.text_input("Host", value="192.168.1.50")
        port = int(col2.number_input("Puerto", value=502, min_value=1, max_value=65535))
        unit_id = int(col3.number_input("Unit ID", value=1, min_value=0, max_value=255))
        address = int(col4.number_input("Address", value=0, min_value=0, max_value=65535))
        count = int(col5.number_input("Count", value=4, min_value=1, max_value=64))

        if st.button("Leer Modbus (holding registers)"):
            ok, msg, regs = modbus_read_example(host, port, unit_id, address, count)
            if ok:
                st.success(msg)
                st.write(regs)
                st.info("Mapea registros a métricas (ej: reg0=temp*10).")
            else:
                st.error(msg)

        st.markdown("---")
        st.subheader("MQTT (configuración)")
        st.caption(mqtt_help_text())
        broker = st.text_input("Broker", value="broker.hivemq.com")
        topic = st.text_input("Topic", value="ecopol/smartfarm/site1")
        st.code(
            """Payload sugerido (JSON):
{"metric":"temp_c","value":22.3,"ts":"2026-01-04T12:00:00","site":"Sitio 1"}"""
        )

# -----------------------------
# MANTENIMIENTO
# -----------------------------
elif page == "Mantenimiento":
    st.title("Mantenimiento (Preventivo / Correctivo)")

    tabA, tabB = st.tabs(["Agenda", "Crear Ticket"])

    with tabA:
        dfm = pd.read_sql_query("""
            SELECT m.id, m.type, m.status, m.priority, m.scheduled_for, m.performed_at,
                   e.name AS equipment, m.description, m.next_due
            FROM maintenance m
            LEFT JOIN equipment e ON e.id = m.equipment_id
            WHERE m.site_id = ?
            ORDER BY COALESCE(m.scheduled_for, m.performed_at) DESC
        """, conn, params=(selected_site_id,))
        if dfm.empty:
            st.info("No hay mantenimientos registrados.")
        else:
            st.dataframe(dfm, use_container_width=True, hide_index=True)

        st.subheader("KPI Mantenimiento")
        if not dfm.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Programados", int((dfm.status == "Programado").sum()))
            c2.metric("En curso", int((dfm.status == "En curso").sum()))
            c3.metric("Cerrados", int((dfm.status == "Cerrado").sum()))

    with tabB:
        eq = pd.read_sql_query("""
            SELECT id, name, category, status
            FROM equipment
            WHERE site_id = ?
            ORDER BY name
        """, conn, params=(selected_site_id,))
        eq_label_map = {f'{r.name} ({r.category})': int(r.id) for _, r in eq.iterrows()} if not eq.empty else {}

        col1, col2, col3 = st.columns(3)
        m_type = col1.selectbox("Tipo", ["Preventivo", "Correctivo"])
        m_status = col2.selectbox("Estado", ["Programado", "En curso", "Cerrado"])
        m_priority = col3.selectbox("Prioridad", ["Baja", "Media", "Alta"])

        equipment_label = st.selectbox("Equipo (opcional)", ["—"] + list(eq_label_map.keys()))
        equipment_id = eq_label_map.get(equipment_label) if equipment_label != "—" else None

        colA, colB = st.columns(2)
        scheduled_for = colA.date_input("Programado para", value=datetime.now().date())
        next_due = colB.date_input("Próximo vencimiento (opcional)", value=(datetime.now().date() + timedelta(days=90)))

        description = st.text_area("Descripción", value="")
        actions_taken = st.text_area("Acciones realizadas (si aplica)", value="")
        parts_used = st.text_area("Repuestos usados (si aplica)", value="")

        if st.button("Guardar ticket"):
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO maintenance(site_id, equipment_id, type, status, priority, scheduled_for,
                                        performed_at, description, actions_taken, parts_used, next_due)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                selected_site_id,
                equipment_id,
                m_type,
                m_status,
                m_priority,
                scheduled_for.isoformat() if scheduled_for else None,
                datetime.now().date().isoformat() if m_status == "Cerrado" else None,
                description,
                actions_taken,
                parts_used,
                next_due.isoformat() if next_due else None
            ))
            conn.commit()
            st.success("Ticket guardado.")

# -----------------------------
# CLIENTES / EQUIPOS
# -----------------------------
elif page == "Clientes/Equipos":
    st.title("Clientes / Sitios / Equipos")

    tab1, tab2, tab3 = st.tabs(["Clientes", "Sitios", "Equipos"])

    with tab1:
        dfc = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
        st.dataframe(dfc, use_container_width=True, hide_index=True)

        st.subheader("Agregar cliente")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nombre")
        phone = c2.text_input("Teléfono")
        email = c3.text_input("Email")
        address = st.text_input("Dirección")
        notes = st.text_area("Notas")
        if st.button("Crear cliente"):
            if not name.strip():
                st.error("Nombre requerido.")
            else:
                conn.execute("INSERT INTO clients(name, phone, email, address, notes) VALUES (?,?,?,?,?)",
                             (name, phone, email, address, notes))
                conn.commit()
                st.success("Cliente creado.")

    with tab2:
        dfs = pd.read_sql_query("""
            SELECT s.*, c.name AS client_name
            FROM sites s
            JOIN clients c ON c.id = s.client_id
            ORDER BY s.id DESC
        """, conn)
        st.dataframe(dfs, use_container_width=True, hide_index=True)

        st.subheader("Agregar sitio")
        clients = pd.read_sql_query("SELECT id, name FROM clients ORDER BY name", conn)
        if clients.empty:
            st.warning("Primero crea un cliente.")
        else:
            client_sel = st.selectbox("Cliente", clients["name"].tolist())
            client_id = int(clients[clients["name"] == client_sel].iloc[0]["id"])
            sname = st.text_input("Nombre del sitio")
            loc = st.text_input("Ubicación")
            stype = st.selectbox("Tipo", ["Avícola", "Porcina", "Mixta"])
            if st.button("Crear sitio"):
                if not sname.strip():
                    st.error("Nombre requerido.")
                else:
                    conn.execute("INSERT INTO sites(client_id, name, location, type) VALUES (?,?,?,?)",
                                 (client_id, sname, loc, stype))
                    conn.commit()
                    st.success("Sitio creado.")

    with tab3:
        dfe = pd.read_sql_query("""
            SELECT e.id, e.name, e.category, e.model, e.serial, e.install_date, e.status, s.name AS site
            FROM equipment e
            JOIN sites s ON s.id = e.site_id
            ORDER BY e.id DESC
        """, conn)
        st.dataframe(dfe, use_container_width=True, hide_index=True)

# -----------------------------
# REPORTES
# -----------------------------
elif page == "Reportes":
    st.title("Reportes")

    st.caption("Reportes básicos para soporte postventa y seguimiento del dueño.")
    latest = get_latest_metrics(conn, selected_site_id)
    thr = get_thresholds(conn, selected_site_id)
    alerts = evaluate_alerts(latest, thr)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Resumen de condiciones")
        st.dataframe(latest, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("Alertas evaluadas")
        st.dataframe(alerts, use_container_width=True, hide_index=True)

    st.subheader("Exportación (CSV)")
    # Exporta histórico de últimas 24h por defecto
    hours = st.slider("Horas a exportar", 6, 168, 24, 6)
    df_export = pd.read_sql_query("""
        SELECT ts, metric, value
        FROM sensor_readings
        WHERE site_id = ?
        AND ts >= ?
        ORDER BY ts
    """, conn, params=(selected_site_id, (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")))
    st.download_button(
        "Descargar CSV de lecturas",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name=f"lecturas_site_{selected_site_id}_{hours}h.csv",
        mime="text/csv",
    )

st.sidebar.markdown("---")
st.sidebar.caption("MVP Streamlit — Ecopol SmartFarm")
