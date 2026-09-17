"""Regenera data/snapshot.json con el catalogo y precios frescos de SAE y lo
sube al repo de GitHub para que la app en la nube se actualice sola.

SE CORRE EN LA PC DE LA OFICINA (la que alcanza Aspel SAE), NO en la nube.
Lo dispara el Programador de tareas de Windows (cada 15 dias) o tu, a mano,
cuando cambies precios. Ver README.md.

Que hace, en orden:
  1. Lee de SAE91 las lineas F y A (activos) con su precio de lista 5.
  2. Escribe data/snapshot.json.
  3. Si el snapshot cambio, hace git add + commit + push a origin.
     (Si no cambio nada, no hace commit.)

Uso:
    python refrescar_precios.py            # lee SAE, escribe snapshot y sube a git
    python refrescar_precios.py --no-push  # solo escribe el snapshot local
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import db_sae

AQUI = Path(__file__).resolve().parent
SNAPSHOT = AQUI / "data" / "snapshot.json"


def _log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ts}] {msg}"
    print(linea)
    logs = AQUI / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / "refresco.log").open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


def _git(*args: str) -> tuple[int, str]:
    """Corre un comando git en la carpeta del proyecto. Devuelve (codigo, salida)."""
    p = subprocess.run(("git", *args), cwd=AQUI, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def construir_snapshot() -> dict:
    if not db_sae.is_configured():
        raise db_sae.SAEUnavailable("Faltan credenciales SAE en el .env.")

    productos = db_sae.fetch_productos()
    if not productos:
        raise db_sae.SAEUnavailable(
            "SAE respondio pero no devolvio productos de las lineas "
            f"{','.join(db_sae.LINEAS)}. Se aborta para no borrar el snapshot bueno."
        )

    sin_precio = [p["cve_art"] for p in productos if p["precio"] is None]
    return {
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "lista_precio": db_sae.LISTA_PRECIO,
        "lista_nombre": db_sae.nivel_descripcion() or f"Lista {db_sae.LISTA_PRECIO}",
        "lineas": list(db_sae.LINEAS),
        "n_productos": len(productos),
        "sin_precio": sin_precio,
        "productos": productos,
    }


def _payload_cambio(nuevo: dict) -> bool:
    """True si el catalogo/precios cambiaron respecto al snapshot en disco.

    Compara solo los productos (ignora el timestamp 'generado') para no hacer
    commits vacios cuando nada cambio.
    """
    if not SNAPSHOT.exists():
        return True
    try:
        viejo = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return viejo.get("productos") != nuevo["productos"]


def escribir(snapshot: dict) -> None:
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def subir_a_git() -> None:
    code, _ = _git("rev-parse", "--is-inside-work-tree")
    if code != 0:
        _log("AVISO: la carpeta no es un repo git todavia; no se sube. "
             "Corre los pasos del README (git init + remote) una sola vez.")
        return

    _git("add", "data/snapshot.json")
    code, _ = _git("diff", "--cached", "--quiet")
    if code == 0:
        _log("Git: nada que commitear (el archivo no cambio en git).")
        return

    fecha = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    code, out = _git("commit", "-m", f"Actualiza precios empaque F/A ({fecha})")
    if code != 0:
        _log(f"Git commit FALLO: {out[:200]}")
        return

    code, out = _git("push")
    if code != 0:
        _log(f"Git push FALLO: {out[:200]} "
             "(revisa que el remoto 'origin' este configurado y con credenciales).")
        return
    _log("Git push OK. La app en la nube se refresca en ~1 minuto.")


def main() -> int:
    push = "--no-push" not in sys.argv
    try:
        snap = construir_snapshot()
    except db_sae.SAEUnavailable as e:
        _log(f"SAE no disponible: {str(e)[:160]}. NO se toca el snapshot anterior.")
        return 1

    cambio = _payload_cambio(snap)
    escribir(snap)
    aviso = "" if not snap["sin_precio"] else f" | SIN PRECIO: {snap['sin_precio']}"
    _log(f"Snapshot OK: {snap['n_productos']} productos, lista {snap['lista_precio']} "
         f"({snap['lista_nombre']}){aviso}. Cambio={'si' if cambio else 'no'}.")

    if not push:
        _log("Modo --no-push: no se sube a git.")
        return 0
    if not cambio and SNAPSHOT.exists():
        # Igual intentamos por si el commit anterior quedo sin push.
        subir_a_git()
        return 0
    subir_a_git()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
