"""Reglas de negocio sobre los pesos/cajas del Excel (INOXIDJOYAS).

Se aplican DESPUES de leer el Excel, en el sync. No modifican el archivo maestro
(para no romper sus formulas). Aqui viven:

  * Renombres de cajas.
  * Alias: una clave toma el peso de otra (misma caja, distinto codigo en SAE).
  * Dimensiones sueltas -> peso volumetrico (L*A*H/5000).
  * Kits: peso = suma de sus componentes (se resuelven recursivamente).

Definido con el usuario el 2026-09-23.
"""
from __future__ import annotations

FACTOR_VOL = 5000  # cm3 por kg volumetrico

# Renombre de cajas (nombre viejo en el Excel -> nombre nuevo).
RENOMBRAR_CAJA = {"CAJA 1.5 KG": "CAJA 1.3 KG"}

# Capacidad util REAL por caja (en kg-volumetricos), cuando el 0.70 parejo no
# refleja la realidad. Ej.: la de pizza es plana y ancha, aguanta mas producto
# plano del que su volumen sugiere. Si una caja no esta aqui, se usa int_vol*0.70.
# Calibrado con datos del usuario (2026-09-23): la de pizza mete 8-9 PB01
# (9 x 0.0648 = 0.583) -> capacidad util ~0.60.
CAP_UTIL_CAJA = {
    "CAJA PIZZA 1 KG": 0.60,
}

# Clave SAE -> clave en el Excel de la que copia el peso.
ALIAS = {
    "PD02": "PAD02", "PD03": "PAD03", "PD04": "PAD04",
    "RD02": "TOD01", "UD01": "TID01",
}

# Clave -> (L, A, H) en cm. Se calcula peso_vol; peso_real queda sin dato.
DIMS = {
    "PE10": (8, 2.8, 0.1),
}

# Kits: clave -> lista [(componente, cantidad), ...]  o  "OTRA_CLAVE" (igual que).
KITS = {
    "PK01": [("PB01", 1), ("PC04", 1), ("PE03", 1), ("PE08", 1), ("PE09", 1)],
    "PK07": [("PA04", 1), ("PC01", 1), ("PE03", 1), ("PE08", 1), ("PE09", 1)],
    "PK08": [("PB02", 1), ("PC04", 1), ("PAD01", 1), ("PE01", 1),
             ("PE05", 1), ("PE06", 1), ("PE08", 1), ("PE09", 1)],
    "PK09": [("PA02", 1), ("PC04", 1), ("PAD01", 1), ("PE01", 1),
             ("PE05", 1), ("PE06", 1), ("PE08", 1), ("PE09", 1)],
    "PKI08": "PK08",
    "PKI09": "PK09",
}


def _tiene(w: dict | None) -> bool:
    return bool(w) and (w.get("peso_vol") is not None or w.get("peso_real") is not None)


def resolver_pesos(pesos: dict) -> dict:
    """Devuelve un dict de pesos aumentado con alias, dims y kits resueltos.

    `pesos` = {CLAVE: {"peso_vol": x, "peso_real": y}} tal como sale del Excel.
    """
    p = {k.upper(): dict(v) for k, v in pesos.items()}

    def peso_de(cve: str, visto: frozenset = frozenset()) -> dict | None:
        cve = cve.upper()
        if cve in visto:            # corta ciclos
            return None
        if _tiene(p.get(cve)):
            return p[cve]
        visto = visto | {cve}
        if cve in ALIAS:
            return peso_de(ALIAS[cve], visto)
        if cve in DIMS:
            l, a, h = DIMS[cve]
            return {"peso_vol": round(l * a * h / FACTOR_VOL, 5), "peso_real": None}
        if cve in KITS:
            comp = KITS[cve]
            if isinstance(comp, str):
                return peso_de(comp, visto)
            vol = real = 0.0
            hay = False
            for c, q in comp:
                w = peso_de(c, visto)
                if _tiene(w):
                    vol += (w.get("peso_vol") or 0.0) * q
                    real += (w.get("peso_real") or 0.0) * q
                    hay = True
            if hay:
                return {"peso_vol": round(vol, 5), "peso_real": round(real, 5)}
        return None

    for cve in list(ALIAS) + list(DIMS) + list(KITS):
        w = peso_de(cve)
        if _tiene(w):
            p[cve.upper()] = w
    return p


def ajustar_cajas(cajas: list[dict]) -> list[dict]:
    """Renombra las cajas y fija su capacidad util override si aplica."""
    for c in cajas:
        c["nombre"] = RENOMBRAR_CAJA.get(c.get("nombre"), c.get("nombre"))
        cap = CAP_UTIL_CAJA.get(c["nombre"])
        c["cap_util"] = cap  # None si no hay override -> se usa int_vol*factor
    return cajas


# alias compatible
renombrar_cajas = ajustar_cajas
