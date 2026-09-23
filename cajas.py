"""Recomendacion de caja de envio por aproximado volumetrico (sin 3D).

Trabaja con datos que ya vienen en el snapshot (peso_vol / peso_real por producto
y el catalogo de cajas). No lee el Excel: eso lo hace refrescar_precios.py en la
oficina. Por eso funciona en la nube.

- La caja recomendada = la mas chica cuyo espacio interior util (int_vol * factor)
  alcance para el volumen total de la mercancia (aprox. volumetrico, sin 3D).
- El volumen que cuenta para el envio es el de la CAJA (ahi se guarda), no el de
  la mercancia suelta. El gramaje del envio = mercancia + peso de la caja.
- 'Peso a tomar' (con el que se cotiza) = el MAYOR entre el VOLUMEN DE LA CAJA y
  el GRAMAJE (mercancia + caja).
"""
from __future__ import annotations


def recomendar(items: list[dict], cajas: list[dict], factor: float = 0.70) -> dict:
    """items: [{'peso_vol': float|None, 'peso_real': float|None, 'cant': int}].

    Devuelve:
      vol_merc   = volumen (peso volumetrico) de la mercancia
      vol_caja   = volumen (peso volumetrico) de la caja de envio (exterior)
      gram_merc  = gramaje (peso real) de la mercancia
      gram_total = gramaje de la mercancia + peso de la caja
      facturable = max(vol_caja, gram_total)  -> peso a tomar
      sin_peso, caja, excede
    """
    vol_merc = sum((it.get("peso_vol") or 0.0) * it["cant"] for it in items)
    gram_merc = sum((it.get("peso_real") or 0.0) * it["cant"] for it in items)
    sin_peso = sum(1 for it in items if not it.get("peso_vol") and not it.get("peso_real"))

    # Capacidad util de cada caja = int_vol * factor, con cap_util como PISO
    # (minimo garantizado). Asi el override escala bien si cambia el factor.
    def _cap(c):
        base = (c.get("int_vol") or 0.0) * factor
        piso = c.get("cap_util")
        return max(base, piso) if piso is not None else base

    cajas_ok = [c for c in cajas if c.get("int_vol")]
    cajas_ok.sort(key=_cap)          # ordenadas por capacidad real ascendente

    caja = None
    excede = False
    for c in cajas_ok:
        if vol_merc <= _cap(c):
            caja = c
            break
    if caja is None and cajas_ok:
        caja = cajas_ok[-1]          # la de mayor capacidad; probablemente 2+ cajas
        excede = True

    vol_caja = (caja.get("ext_vol") or 0.0) if caja else None
    gram_total = gram_merc + ((caja.get("extra") or 0.0) if caja else 0.0)
    facturable = None
    if caja:
        facturable = max(vol_caja, gram_total)

    # Ocupacion = cuanto del cupo util de la caja usa el pedido (0..1+).
    cap_caja = _cap(caja) if caja else None
    ocupacion = (vol_merc / cap_caja) if cap_caja else None

    return {
        "vol_merc": round(vol_merc, 3),
        "vol_caja": None if vol_caja is None else round(vol_caja, 3),
        "gram_merc": round(gram_merc, 3),
        "gram_total": round(gram_total, 3),
        "facturable": None if facturable is None else round(facturable, 3),
        "sin_peso": sin_peso,
        "caja": caja,
        "excede": excede,
        "cap_caja": None if cap_caja is None else round(cap_caja, 3),
        "ocupacion": None if ocupacion is None else round(ocupacion, 3),
    }
