"""Lee el Excel 'CAJAS ....xlsx' (control interno de INOXIDJOYAS) y saca:

  * pesos por clave:  {CLAVE: {"peso_vol": kg, "peso_real": kg}}
      - peso_vol  = PESO VOLUMETRICO  (L*A*H/5000, ya calculado en el Excel)
      - peso_real = PESO REAL
  * catalogo de cajas de envio: lista de dicts
      {nombre, l, a, h, extra, ext_vol, int_vol}
      - medidas exteriores (cm) tomadas de la columna MEDIDAS "L*A*H"
      - extra    = PESO EXTRA / CAJA (kg que suma la caja vacia)
      - ext_vol  = EXTERIOR (peso volumetrico exterior, kg)
      - int_vol  = ESPACIO INTERIOR TOTAL (capacidad util, en kg-volumetricos)

Solo se usa EN LA PC DE LA OFICINA, dentro de refrescar_precios.py, para meter
estos datos al snapshot. La app en la nube NO lee el Excel.
"""
from __future__ import annotations

import re
from pathlib import Path

# Factor de aprovechamiento de la caja (cuanto del volumen interior se usa).
# 0.60 = conservador, calibrado al peor caso conocido (6 PB01 en la 1KG = ~53%
# de llenado). Un solo factor NO puede ser correcto para todos los productos
# (cada uno acomoda distinto); se elige conservador para errar hacia caja de mas
# (que cabe) y no hacia una donde no entra. Lo fino se hace por producto (ver
# overrides_pesos) o con acomodo 3D.
FACTOR_LLENADO = 0.60


def _num(x):
    try:
        return round(float(x), 5)
    except (TypeError, ValueError):
        return None


def _medidas(txt):
    """'21*17*12' -> (21.0, 17.0, 12.0). Acepta * x × como separador."""
    if not txt:
        return (None, None, None)
    partes = re.split(r"[*xX×]", str(txt))
    nums = []
    for p in partes:
        try:
            nums.append(float(p.strip().replace(",", ".")))
        except ValueError:
            pass
    while len(nums) < 3:
        nums.append(None)
    return tuple(nums[:3])


def leer(path: str | Path) -> tuple[dict, list]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))

    pesos: dict[str, dict] = {}
    cajas: list[dict] = []
    for r in rows:
        r = list(r) + [None] * (16 - len(r)) if len(r) < 16 else r
        # --- producto: col A clave, H peso vol, J peso real ---
        clave = r[0]
        if clave and str(clave).strip().upper() not in ("", "CLAVE"):
            vol, real = _num(r[7]), _num(r[9])
            if vol is not None or real is not None:
                pesos[str(clave).strip().upper()] = {"peso_vol": vol, "peso_real": real}
        # --- caja: col L nombre 'CAJA ...' ---
        nombre = r[11]
        if nombre and str(nombre).strip().upper().startswith("CAJA"):
            l, a, h = _medidas(r[13])
            cajas.append({
                "nombre": str(nombre).strip(),
                "l": l, "a": a, "h": h,
                "extra": _num(r[12]) or 0.0,
                "ext_vol": _num(r[14]),
                "int_vol": _num(r[15]),
            })
    # cajas ordenadas por capacidad interior ascendente
    cajas = [c for c in cajas if c["int_vol"]]
    cajas.sort(key=lambda c: c["int_vol"])
    return pesos, cajas


if __name__ == "__main__":
    import json
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Users\useer\Desktop\CONTROL INOXID 2026\CAJAS 02-07.xlsx"
    pesos, cajas = leer(p)
    print(f"Pesos: {len(pesos)} claves. Cajas: {len(cajas)}")
    print("\nCajas (orden por capacidad):")
    for c in cajas:
        print(f"  {c['nombre']:16} med {c['l']}x{c['a']}x{c['h']}  "
              f"int_vol={c['int_vol']}  ext_vol={c['ext_vol']}  extra={c['extra']}")
    print("\nMuestra pesos:", json.dumps(dict(list(pesos.items())[:4]), ensure_ascii=False))
