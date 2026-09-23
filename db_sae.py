"""Conexion de SOLO LECTURA a Aspel SAE91 para el cotizador de empaque (lineas F y A).

Reutiliza el patron ya probado en las otras herramientas internas de INOXIDJOYAS:
credenciales en `.env`, barrera que rechaza todo lo que no sea SELECT, drivers 18/17.

Solo se usa para LEER el catalogo de las lineas F y A con su precio de lista 5
(PRECIO_X_PROD01, CVE_PRECIO = 5, que SAE etiqueta "Precio de lista 3").
Nunca escribe en SAE.

Este modulo corre EN LA PC DE LA OFICINA (la que alcanza Aspel SAE), no en la nube.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

# Lineas de empaque a cotizar. F = cajas/kits, A = cubrepolvos.
LINEAS = tuple(x.strip() for x in os.getenv("LINEAS", "F,A,FA").split(",") if x.strip())

# Nivel de lista de precios. El usuario lo llama "lista 5" = CVE_PRECIO 5
# (SAE lo etiqueta internamente "Precio de lista 3"). Confirmado 2026-09-17.
LISTA_PRECIO = int(os.getenv("LISTA_PRECIO", "5"))

_PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|"
    r"REVOKE|EXEC|EXECUTE|INTO)\b",
    re.IGNORECASE,
)


class SAEUnavailable(RuntimeError):
    """No se pudo conectar o consultar SAE."""


def _sae_config() -> dict:
    return {
        "server": os.getenv("SAE_SERVER", ""),
        "port": os.getenv("SAE_PORT", "1433") or "1433",
        "database": os.getenv("SAE_DB", "SAE91"),
        "user": os.getenv("SAE_USER", ""),
        "password": os.getenv("SAE_PASSWORD", ""),
    }


def is_configured() -> bool:
    cfg = _sae_config()
    return all(cfg[k] for k in ("server", "database", "user", "password"))


def _pick_driver() -> str:
    import pyodbc
    available = set(pyodbc.drivers())
    for drv in _PREFERRED_DRIVERS:
        if drv in available:
            return drv
    raise SAEUnavailable(f"No hay ODBC Driver 18/17. Instalados: {sorted(available)}")


def _conn_str(cfg: dict) -> str:
    return (
        f"DRIVER={{{_pick_driver()}}};"
        f"SERVER={cfg['server']},{cfg['port']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['user']};PWD={cfg['password']};"
        f"Encrypt=no;TrustServerCertificate=yes;"
    )


def _connect():
    import pyodbc
    if not is_configured():
        raise SAEUnavailable("Faltan credenciales SAE en el .env.")
    try:
        return pyodbc.connect(_conn_str(_sae_config()), timeout=8, readonly=True)
    except Exception as e:  # pyodbc.Error y afines
        raise SAEUnavailable(str(e)) from e


def _select(sql: str, params: tuple = ()) -> list[tuple]:
    if not sql.strip().upper().startswith("SELECT") or _FORBIDDEN.search(sql):
        raise SAEUnavailable("Solo se permiten consultas SELECT sobre SAE.")
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()


def nivel_descripcion(nivel: int | None = None) -> str:
    """Nombre de la lista en SAE (PRECIOS01). Cadena vacia si no se puede leer."""
    nivel = LISTA_PRECIO if nivel is None else nivel
    try:
        rows = _select("SELECT DESCRIPCION FROM PRECIOS01 WHERE CVE_PRECIO = ?", (nivel,))
        return str(rows[0][0]).strip() if rows else ""
    except SAEUnavailable:
        return ""


def fetch_productos(lineas: tuple[str, ...] | None = None,
                    nivel: int | None = None) -> list[dict]:
    """Catalogo activo de las lineas de empaque con su precio de lista.

    Devuelve una lista de dicts: cve_art, descr, linea, precio.
    Solo articulos STATUS='A'. Productos sin precio en la lista quedan con
    precio None (se avisan en el snapshot).
    """
    lineas = LINEAS if lineas is None else lineas
    nivel = LISTA_PRECIO if nivel is None else nivel
    ph = ",".join("?" * len(lineas))
    sql = (
        "SELECT i.CVE_ART, i.DESCR, i.LIN_PROD, p.PRECIO "
        "FROM INVE01 i "
        "LEFT JOIN PRECIO_X_PROD01 p "
        "  ON p.CVE_ART = i.CVE_ART AND p.CVE_PRECIO = ? "
        f"WHERE i.LIN_PROD IN ({ph}) AND i.STATUS = 'A' "
        "ORDER BY i.LIN_PROD, i.CVE_ART"
    )
    rows = _select(sql, (nivel, *lineas))
    out = []
    for cve, descr, lin, precio in rows:
        out.append({
            "cve_art": str(cve).strip(),
            "descr": (descr or "").strip(),
            "linea": str(lin).strip(),
            "precio": None if precio is None else round(float(precio), 2),
        })
    return out


def check_connection() -> tuple[bool, str]:
    """Prueba rapida de conexion. (ok, mensaje)."""
    try:
        v = _select("SELECT @@VERSION")[0][0].splitlines()[0]
        return True, v
    except SAEUnavailable as e:
        return False, str(e)


if __name__ == "__main__":
    ok, msg = check_connection()
    print("SAE:", "OK" if ok else "FALLO", "-", msg[:90])
    if ok:
        prods = fetch_productos()
        print(f"Lista {LISTA_PRECIO} ({nivel_descripcion()}): {len(prods)} productos "
              f"de lineas {','.join(LINEAS)}.")
        sin = [p['cve_art'] for p in prods if p['precio'] is None]
        if sin:
            print(f"  OJO: {len(sin)} sin precio en la lista: {sin}")
