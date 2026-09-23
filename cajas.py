"""Recomendacion de caja de envio por aproximado volumetrico (sin 3D).

Trabaja con datos que ya vienen en el snapshot (peso_vol / peso_real por producto
y el catalogo de cajas). No lee el Excel: eso lo hace refrescar_precios.py en la
oficina. Por eso funciona en la nube.

- La caja recomendada = la mas chica cuyo espacio interior util (int_vol * factor)
  alcance para el volumen total del pedido (aprox. volumetrico, sin 3D).
- El 'peso a tomar' (con el que se cotiza el envio) = el MAYOR entre el peso
  volumetrico y el gramaje (peso real) de la mercancia, igual que la columna
  "PESO A TOMAR" del Excel. NO depende de la caja.
"""
from __future__ import annotations


def recomendar(items: list[dict], cajas: list[dict], factor: float = 0.70) -> dict:
    """items: [{'peso_vol': float|None, 'peso_real': float|None, 'cant': int}].

    Devuelve dict con total_vol, total_real, sin_peso (cuantos renglones sin dato),
    caja (dict o None), excede (bool) y facturable = max(total_vol, total_real).
    """
    total_vol = sum((it.get("peso_vol") or 0.0) * it["cant"] for it in items)
    total_real = sum((it.get("peso_real") or 0.0) * it["cant"] for it in items)
    sin_peso = sum(1 for it in items if not it.get("peso_vol") and not it.get("peso_real"))

    cajas_ok = [c for c in cajas if c.get("int_vol")]
    cajas_ok.sort(key=lambda c: c["int_vol"])

    caja = None
    excede = False
    for c in cajas_ok:
        if total_vol <= c["int_vol"] * factor:
            caja = c
            break
    if caja is None and cajas_ok:
        caja = cajas_ok[-1]          # la mas grande; probablemente necesite 2+
        excede = True

    # Peso a tomar = el mayor entre volumetrico y gramaje (real) de la mercancia.
    facturable = max(total_vol, total_real)

    return {
        "total_vol": round(total_vol, 3),
        "total_real": round(total_real, 3),
        "sin_peso": sin_peso,
        "caja": caja,
        "excede": excede,
        "facturable": round(facturable, 3),
    }
