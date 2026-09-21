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

import cotizacion_doc
import parser_pedido

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
tab_pegar, tab_buscar = st.tabs(["📋 Pegar pedido", "🔎 Buscar uno por uno"])

# --- Pestaña 1: pegar el pedido y detectar claves/cantidades ---------------
with tab_pegar:
    st.caption("Pega el pedido tal cual te lo pasaron. El sistema detecta clave "
               "o nombre y cantidad. Revisa y confirma.")
    texto = st.text_area(
        "Pega el pedido", key="pegar_txt", height=130, label_visibility="collapsed",
        placeholder="Ej:\n10 PA01\n5 cubrepolvo cartier\nCK02 x8\n3 caja blanda anillo",
    )
    if st.button("🔍 Detectar productos", use_container_width=True, type="primary"):
        ok, malas = parser_pedido.parse_pedido(texto, productos)
        st.session_state["deteccion"] = (ok, malas)

    det = st.session_state.get("deteccion")
    if det:
        ok, malas = det
        if ok:
            st.success(f"Detecté {len(ok)} producto(s). Revisa y agrega:")
            for r in ok:
                via = "por nombre" if r["como"] == "nombre" else "clave"
                st.markdown(
                    f'<div class="item"><div class="nom">'
                    f'<span class="cve">{r["cve"]}</span> · {r["descr"]} '
                    f'<span class="uni">({via})</span></div>'
                    f'<div class="uni">{r["cant"]} × ${r["precio"]:,.2f} '
                    f'→ <span class="imp">${r["importe"]:,.2f}</span></div></div>',
                    unsafe_allow_html=True,
                )
            if st.button(f"➕ Agregar {len(ok)} al pedido", use_container_width=True,
                         type="primary", key="add_todos"):
                for r in ok:
                    carrito[r["cve"]] = carrito.get(r["cve"], 0) + int(r["cant"])
                st.session_state.pop("deteccion", None)
                st.toast(f"Agregados {len(ok)} productos", icon="✅")
                st.rerun()
        if malas:
            st.warning("⚠️ No reconocí: " + "  ·  ".join(malas)
                       + ".  Revisa la escritura o agrégalos en la pestaña **Buscar**.")

# --- Pestaña 2: selector uno por uno ---------------------------------------
with tab_buscar:
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
    with st.expander("📄 Descargar cotización (PDF o imagen)"):
        cliente = st.text_input("Cliente", placeholder="Nombre del cliente")
        folio = st.text_input("Folio", placeholder="COT-001")
        fecha = st.date_input("Fecha", value=dt.date.today(), format="DD/MM/YYYY")

        meta = {"cliente": cliente, "folio": folio,
                "fecha": fecha.strftime("%d/%m/%Y"),
                "lista": snap.get("lista_nombre", "Lista 5")}
        filas = [{
            "clave": cve, "descr": descr_por_clave.get(cve, ""),
            "linea": linea_por_clave.get(cve, ""), "cant": int(c),
            "pu": precio_por_clave.get(cve, 0.0),
            "importe": precio_por_clave.get(cve, 0.0) * int(c),
        } for cve, c in carrito.items()]
        base_nombre = f"cotizacion_{folio or fecha.strftime('%Y%m%d')}"

        pdf_bytes = cotizacion_doc.construir_pdf(meta, filas, subtotal, total)
        png_bytes = cotizacion_doc.pdf_a_png(pdf_bytes)

        d1, d2 = st.columns(2)
        d1.download_button("⬇️ PDF", data=pdf_bytes, file_name=f"{base_nombre}.pdf",
                           mime="application/pdf", use_container_width=True, type="primary")
        if png_bytes:
            d2.download_button("🖼️ Imagen", data=png_bytes, file_name=f"{base_nombre}.png",
                               mime="image/png", use_container_width=True)
        else:
            d2.caption("Imagen no disponible")
        st.caption("La imagen es ideal para enviar por WhatsApp (se previsualiza).")

st.caption(f"Precios de Aspel SAE (lista {snap.get('lista_precio', 5)}), "
           f"snapshot {gen_fmt}. Total sin IVA.")
