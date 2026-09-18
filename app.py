"""Cotizador de empaque (lineas F y A) - INOXIDJOYAS.

App multiusuario en la nube (Streamlit Community Cloud), pensada para usarse
DESDE EL CELULAR. Eliges productos de las lineas de empaque F (cajas/kits) y A
(cubrepolvos), pones cantidades y calcula SUBTOTAL y TOTAL (sin IVA, precio de
lista 5 de Aspel SAE).

Los precios vienen del snapshot (data/snapshot.json) que se refresca desde la PC
de la oficina con refrescar_precios.py. La app NO se conecta a SAE: por eso
funciona 24/7 aunque la PC este apagada. Ver README.md.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import streamlit as st

AQUI = Path(__file__).resolve().parent
SNAPSHOT = AQUI / "data" / "snapshot.json"

st.set_page_config(page_title="Cotizador de empaque - INOXIDJOYAS",
                   page_icon="📦", layout="centered",
                   initial_sidebar_state="collapsed")

# --------------------------------------------------------------------- estilos
# Diseno mobile-first: tap targets grandes, tipografia comoda, tarjetas.
CSS = """
<style>
:root { --nav1:#1F4E78; --nav2:#2E6DA4; --gold:#C8912B; --ink:#1A2530; --line:#DDE6F0; }
.block-container { padding-top: .8rem; padding-bottom: 5rem; max-width: 640px; }
#MainMenu, footer, header {visibility: hidden;}

/* Botones grandes y comodos para el dedo */
.stButton > button, .stDownloadButton > button {
  min-height: 46px; border-radius: 12px; font-weight: 700; font-size: 1rem;
}
/* Inputs mas altos */
.stNumberInput input, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
  min-height: 44px; font-size: 1rem;
}

.hero {
  background: linear-gradient(120deg, var(--nav1) 0%, var(--nav2) 100%);
  border-radius: 16px; padding: 16px 18px; color:#fff;
  box-shadow: 0 6px 18px rgba(31,78,120,.25); margin-bottom: 12px;
}
.hero h1 { margin:0; font-size:1.3rem; font-weight:800; }
.hero .sub { opacity:.92; margin-top:3px; font-size:.85rem; }
.hero .chip {
  display:inline-block; background: rgba(255,255,255,.18);
  border:1px solid rgba(255,255,255,.35); padding:3px 9px; border-radius:999px;
  font-size:.72rem; margin-top:8px; margin-right:5px;
}

/* Tarjeta de cada renglon del pedido */
.item { background:#fff; border:1px solid var(--line); border-radius:14px;
  padding:12px 14px 8px; margin-bottom:10px; box-shadow:0 2px 8px rgba(20,40,70,.05); }
.item .nom { font-weight:700; color:var(--ink); font-size:.98rem; line-height:1.25; }
.item .cve { color:#6b7c90; font-weight:600; }
.item .imp { color:var(--nav1); font-weight:800; font-size:1.05rem; }
.item .uni { color:#8a99aa; font-size:.82rem; }

/* Totales */
.mrow { display:flex; gap:12px; margin: 8px 0 4px; }
.mcard { flex:1; background:#fff; border:1px solid var(--line); border-radius:14px;
  padding:14px 16px; box-shadow:0 2px 8px rgba(20,40,70,.05); text-align:center; }
.mcard.total { background:linear-gradient(135deg,#F4F9F1,#E3F1DA); border-color:#BFE0AC; }
.mcard .lbl { color:#6b7c90; font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.4px; }
.mcard .val { color:var(--ink); font-size:1.5rem; font-weight:800; line-height:1.1; margin-top:2px; }
.mcard.total .val { color:#2f6b2f; }
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
etiqueta = {p["cve_art"]: f"{p['cve_art']} - {p['descr']}".strip(" -") for p in productos}
clave_por_etiqueta = {v: k for k, v in etiqueta.items()}
opciones = sorted(etiqueta.values())

gen = snap.get("generado", "")
try:
    gen_fmt = dt.datetime.fromisoformat(gen).strftime("%d/%m/%Y %H:%M")
except ValueError:
    gen_fmt = gen or "?"

# El pedido vive en session_state: {cve_art: cantidad}
if "carrito" not in st.session_state:
    st.session_state["carrito"] = {}
carrito: dict[str, int] = st.session_state["carrito"]

# --------------------------------------------------------------------- hero
st.markdown(
    f'<div class="hero"><h1>📦 Cotizador de empaque</h1>'
    f'<div class="sub">Lineas F y A · {snap.get("lista_nombre", "Lista 5")} · sin IVA</div>'
    f'<span class="chip">Precios: {gen_fmt}</span>'
    f'<span class="chip">{len(productos)} productos</span></div>',
    unsafe_allow_html=True,
)

if snap.get("sin_precio"):
    st.warning("Sin precio (salen en $0): " + ", ".join(snap["sin_precio"]))

# ---------------------------------------------------- agregar producto
st.markdown("### 1) Agrega productos")
sel = st.selectbox("Producto", opciones, index=None,
                   placeholder="Escribe clave o nombre…", label_visibility="collapsed")
c1, c2 = st.columns([1, 2])
cant_add = c1.number_input("Cantidad", min_value=1, step=1, value=1,
                           label_visibility="collapsed")
agregar = c2.button("➕ Agregar al pedido", use_container_width=True, type="primary",
                    disabled=sel is None)
if agregar and sel is not None:
    cve = clave_por_etiqueta[sel]
    carrito[cve] = carrito.get(cve, 0) + int(cant_add)
    st.toast(f"Agregado: {cve} ×{int(cant_add)}", icon="✅")
    st.rerun()

# ---------------------------------------------------- pedido (tarjetas)
st.markdown("### 2) Tu pedido")
if not carrito:
    st.info("Aun no agregas productos. Elige uno arriba y toca **Agregar**.")
else:
    for cve in list(carrito.keys()):
        precio = precio_por_clave.get(cve, 0.0)
        cant = int(carrito[cve])
        importe = precio * cant
        st.markdown(
            f'<div class="item"><div class="nom">'
            f'<span class="cve">{cve}</span> · {descr_por_clave.get(cve, "")}</div>'
            f'<div class="uni">${precio:,.2f} c/u · linea {linea_por_clave.get(cve, "")}'
            f' &nbsp;→&nbsp; <span class="imp">${importe:,.2f}</span></div></div>',
            unsafe_allow_html=True,
        )
        ca, cb = st.columns([2, 1])
        nueva = ca.number_input(f"Cantidad {cve}", min_value=1, step=1, value=cant,
                                key=f"q_{cve}", label_visibility="collapsed")
        if int(nueva) != cant:
            carrito[cve] = int(nueva)
            st.rerun()
        if cb.button("🗑 Quitar", key=f"del_{cve}", use_container_width=True):
            carrito.pop(cve, None)
            st.session_state.pop(f"q_{cve}", None)
            st.rerun()

    if st.button("Vaciar pedido", use_container_width=True):
        st.session_state["carrito"] = {}
        for k in [k for k in st.session_state if k.startswith("q_")]:
            st.session_state.pop(k, None)
        st.rerun()

# --------------------------------------------------------------- totales
piezas = sum(int(c) for c in carrito.values())
subtotal = sum(precio_por_clave.get(cve, 0.0) * int(c) for cve, c in carrito.items())
total = subtotal  # sin IVA

st.markdown(
    f'<div class="mrow">'
    f'<div class="mcard"><div class="lbl">Piezas</div><div class="val">{piezas}</div></div>'
    f'<div class="mcard"><div class="lbl">Subtotal</div><div class="val">${subtotal:,.2f}</div></div>'
    f'<div class="mcard total"><div class="lbl">Total sin IVA</div><div class="val">${total:,.2f}</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------- exportar
if carrito:
    with st.expander("Datos de la cotizacion (opcional) y descarga"):
        cliente = st.text_input("Cliente", placeholder="Nombre del cliente")
        folio = st.text_input("Folio", placeholder="COT-001")
        fecha = st.date_input("Fecha", value=dt.date.today(), format="DD/MM/YYYY")

        lineas = []
        lineas.append("Clave,Descripcion,Linea,Cantidad,P_Unitario,Importe")
        for cve, c in carrito.items():
            c = int(c)
            pu = precio_por_clave.get(cve, 0.0)
            desc = descr_por_clave.get(cve, "").replace(",", " ")
            lineas.append(f"{cve},{desc},{linea_por_clave.get(cve, '')},{c},{pu:.2f},{pu * c:.2f}")
        enc = []
        if cliente:
            enc.append(f"Cliente:,{cliente}")
        if folio:
            enc.append(f"Folio:,{folio}")
        enc.append(f"Fecha:,{fecha.strftime('%d/%m/%Y')}")
        enc.append(f"Lista:,{snap.get('lista_nombre', 'Lista 5')} (sin IVA)")
        cuerpo = "\n".join(enc) + "\n\n" + "\n".join(lineas)
        cuerpo += f"\n\nSubtotal:,{subtotal:.2f}\nTotal (sin IVA):,{total:.2f}\n"
        csv = cuerpo.encode("utf-8-sig")
        nombre = f"cotizacion_{folio or fecha.strftime('%Y%m%d')}.csv"
        st.download_button("⬇️ Descargar cotizacion (Excel/CSV)", data=csv,
                           file_name=nombre, mime="text/csv",
                           use_container_width=True, type="primary")

st.caption(f"Precios de Aspel SAE (lista {snap.get('lista_precio', 5)}), "
           f"snapshot {gen_fmt}. Total sin IVA.")
