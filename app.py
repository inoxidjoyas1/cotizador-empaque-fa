"""Cotizador de empaque (lineas F y A) - INOXIDJOYAS.

App multiusuario en la nube (Streamlit Community Cloud). Eliges productos de las
lineas de empaque F (cajas/kits) y A (cubrepolvos), pones cantidades y calcula
SUBTOTAL y TOTAL (sin IVA, precio de lista 5 de Aspel SAE).

Los precios vienen del snapshot (data/snapshot.json) que se refresca desde la PC
de la oficina con refrescar_precios.py. La app NO se conecta a SAE: por eso
funciona 24/7 aunque la PC este apagada. Ver README.md.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import streamlit as st

AQUI = Path(__file__).resolve().parent
SNAPSHOT = AQUI / "data" / "snapshot.json"

st.set_page_config(page_title="Cotizador de empaque - INOXIDJOYAS",
                   page_icon="📦", layout="wide",
                   initial_sidebar_state="collapsed")

# --------------------------------------------------------------------- estilos
CSS = """
<style>
:root { --nav1:#1F4E78; --nav2:#2E6DA4; --gold:#C8912B; --ink:#1A2530; --line:#DDE6F0; }
.block-container { padding-top: 1.1rem; max-width: 1150px; }
#MainMenu, footer {visibility: hidden;}
.hero {
  background: linear-gradient(120deg, var(--nav1) 0%, var(--nav2) 100%);
  border-radius: 16px; padding: 20px 24px; color:#fff;
  box-shadow: 0 6px 18px rgba(31,78,120,.25); margin-bottom: 14px;
}
.hero h1 { margin:0; font-size:1.55rem; font-weight:800; }
.hero .sub { opacity:.92; margin-top:4px; font-size:.92rem; }
.hero .chip {
  display:inline-block; background: rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.35); padding:3px 10px; border-radius:999px;
  font-size:.78rem; margin-top:10px; margin-right:6px;
}
.mrow { display:flex; gap:14px; flex-wrap:wrap; margin: 6px 0 2px; }
.mcard {
  flex:1; min-width:180px; background:#fff; border:1px solid var(--line);
  border-radius:14px; padding:14px 18px; box-shadow:0 2px 8px rgba(20,40,70,.05);
}
.mcard.total { background:linear-gradient(135deg,#F4F9F1,#E3F1DA); border-color:#BFE0AC; }
.mcard .lbl { color:#6b7c90; font-size:.8rem; font-weight:600; text-transform:uppercase; letter-spacing:.4px; }
.mcard .val { color:var(--ink); font-size:1.7rem; font-weight:800; line-height:1.1; margin-top:2px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------- datos
@st.cache_data(show_spinner=False)
def cargar_snapshot(mtime: float) -> dict:
    if not SNAPSHOT.exists():
        return {}
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


snap = cargar_snapshot(SNAPSHOT.stat().st_mtime if SNAPSHOT.exists() else 0.0)
if not snap or not snap.get("productos"):
    st.error("No hay datos de productos todavia. Corre `refrescar_precios.py` en la "
             "PC de la oficina para generar el snapshot y subirlo a GitHub.")
    st.stop()

productos = snap["productos"]
precio_por_clave = {p["cve_art"]: (p["precio"] or 0.0) for p in productos}
descr_por_clave = {p["cve_art"]: p["descr"] for p in productos}
linea_por_clave = {p["cve_art"]: p["linea"] for p in productos}
# Etiqueta legible para el selector: "CVE_ART - DESCRIPCION"
etiqueta = {p["cve_art"]: f"{p['cve_art']} - {p['descr']}".strip(" -") for p in productos}
clave_por_etiqueta = {v: k for k, v in etiqueta.items()}
opciones = sorted(etiqueta.values())

gen = snap.get("generado", "")
try:
    gen_fmt = dt.datetime.fromisoformat(gen).strftime("%d/%m/%Y %H:%M")
except ValueError:
    gen_fmt = gen or "?"

# --------------------------------------------------------------------- hero
st.markdown(
    f'<div class="hero"><h1>📦 Cotizador de empaque</h1>'
    f'<div class="sub">Lineas F (cajas y kits) y A (cubrepolvos) · '
    f'{snap.get("lista_nombre", "Lista 5")} · sin IVA</div>'
    f'<span class="chip">Precios actualizados: {gen_fmt}</span>'
    f'<span class="chip">{len(productos)} productos</span></div>',
    unsafe_allow_html=True,
)

if snap.get("sin_precio"):
    st.warning("Estos productos no tienen precio en la lista y salen en $0: "
               + ", ".join(snap["sin_precio"]))

# --------------------------------------------------------- datos de cotizacion
cols = st.columns([2, 1, 1])
cliente = cols[0].text_input("Cliente (opcional)", placeholder="Nombre del cliente")
folio = cols[1].text_input("Folio (opcional)", placeholder="COT-001")
fecha = cols[2].date_input("Fecha", value=dt.date.today(), format="DD/MM/YYYY")

st.markdown("#### Productos a cotizar")
st.caption("Elige el producto en la columna **Producto** y captura la **Cantidad**. "
           "Agrega renglones con el **+** de abajo.")

if "lineas_cot" not in st.session_state:
    base = pd.DataFrame({"Producto": pd.Series([], dtype="object"),
                         "Cantidad": pd.Series([], dtype="Int64")})
else:
    base = st.session_state["lineas_cot"]

edit = st.data_editor(
    base,
    num_rows="dynamic",
    use_container_width=True,
    key="editor",
    column_config={
        "Producto": st.column_config.SelectboxColumn(
            "Producto", options=opciones, required=False, width="large"),
        "Cantidad": st.column_config.NumberColumn(
            "Cantidad", min_value=0, step=1, default=1, format="%d", width="small"),
    },
)
st.session_state["lineas_cot"] = edit

# --------------------------------------------------------------- calculo
filas = []
for _, r in edit.iterrows():
    et = r.get("Producto")
    if not et or et not in clave_por_etiqueta:
        continue
    cve = clave_por_etiqueta[et]
    cant = r.get("Cantidad")
    cant = 0 if pd.isna(cant) else float(cant)
    if cant <= 0:
        continue
    pu = precio_por_clave.get(cve, 0.0)
    filas.append({
        "Clave": cve,
        "Descripcion": descr_por_clave.get(cve, ""),
        "Linea": linea_por_clave.get(cve, ""),
        "Cantidad": int(cant) if cant.is_integer() else cant,
        "P. Unitario": pu,
        "Importe": round(pu * cant, 2),
    })

det = pd.DataFrame(filas)
subtotal = float(det["Importe"].sum()) if not det.empty else 0.0
total = subtotal  # sin IVA: Total = Subtotal

st.markdown("#### Detalle")
if det.empty:
    st.info("Aun no hay renglones con producto y cantidad. La cotizacion aparecera aqui.")
else:
    st.dataframe(
        det,
        use_container_width=True,
        hide_index=True,
        column_config={
            "P. Unitario": st.column_config.NumberColumn(format="$ %.2f"),
            "Importe": st.column_config.NumberColumn(format="$ %.2f"),
        },
    )

# --------------------------------------------------------------- totales
st.markdown(
    f'<div class="mrow">'
    f'<div class="mcard"><div class="lbl">Piezas</div>'
    f'<div class="val">{int(det["Cantidad"].sum()) if not det.empty else 0}</div></div>'
    f'<div class="mcard"><div class="lbl">Subtotal</div>'
    f'<div class="val">$ {subtotal:,.2f}</div></div>'
    f'<div class="mcard total"><div class="lbl">Total (sin IVA)</div>'
    f'<div class="val">$ {total:,.2f}</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------- exportar
if not det.empty:
    enc = []
    if cliente:
        enc.append(f"Cliente:,{cliente}")
    if folio:
        enc.append(f"Folio:,{folio}")
    enc.append(f"Fecha:,{fecha.strftime('%d/%m/%Y')}")
    enc.append(f"Lista:,{snap.get('lista_nombre', 'Lista 5')} (sin IVA)")
    encabezado = "\n".join(enc) + "\n\n"
    cuerpo = det.to_csv(index=False)
    pie = f"\nSubtotal:,{subtotal:.2f}\nTotal (sin IVA):,{total:.2f}\n"
    csv = (encabezado + cuerpo + pie).encode("utf-8-sig")
    nombre = f"cotizacion_{folio or fecha.strftime('%Y%m%d')}.csv"
    st.download_button("⬇️ Descargar cotizacion (CSV / Excel)", data=csv,
                       file_name=nombre, mime="text/csv", type="primary")

st.caption(f"Precios tomados de Aspel SAE (lista {snap.get('lista_precio', 5)}), "
           f"snapshot del {gen_fmt}. Total sin IVA.")
