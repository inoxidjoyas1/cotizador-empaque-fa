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
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

:root { --nav1:#1F4E78; --nav2:#2E6DA4; --gold:#C8912B; --ink:#1A2530;
        --line:#E1E8F1; --muted:#7c8ba0; --green1:#2f7d32; }

html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif !important;
}
.stApp { background:#F3F7FC; }
.block-container { padding-top:.6rem; padding-bottom:6.5rem; max-width:640px; }
#MainMenu, footer, header {visibility:hidden;}

/* Botones */
.stButton > button, .stDownloadButton > button {
  min-height:48px; border-radius:12px; font-weight:700; font-size:1rem;
  transition:transform .05s ease, box-shadow .15s ease;
}
.stButton > button:active, .stDownloadButton > button:active { transform:translateY(1px); }
button[kind="primary"], button[kind="primaryFormSubmit"] {
  background:linear-gradient(120deg,var(--nav1),var(--nav2)) !important;
  border:none !important; box-shadow:0 4px 12px rgba(31,78,120,.28) !important;
}
button[kind="secondary"] {
  background:#fff !important; border:1px solid var(--line) !important; color:var(--ink) !important;
}
/* Inputs mas altos y suaves */
.stNumberInput input, .stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
  min-height:44px; font-size:1rem; border-radius:10px !important;
}
.stTextArea textarea { line-height:1.5; }

/* Tabs tipo control segmentado */
.stTabs [data-baseweb="tab-list"] { gap:8px; background:transparent; border-bottom:none; }
.stTabs [data-baseweb="tab"] {
  background:#E7EEF7; border-radius:11px; padding:9px 14px; font-weight:700;
  color:var(--nav1); border:none;
}
.stTabs [data-baseweb="tab"] p { font-size:.92rem; font-weight:700; margin:0; }
.stTabs [aria-selected="true"] {
  background:linear-gradient(120deg,var(--nav1),var(--nav2)); color:#fff !important;
}
.stTabs [aria-selected="true"] p { color:#fff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

/* Hero */
.hero {
  background:linear-gradient(125deg,var(--nav1) 0%, var(--nav2) 100%);
  border-radius:18px; padding:18px 20px; color:#fff;
  box-shadow:0 8px 22px rgba(31,78,120,.28); margin-bottom:6px;
}
.hero h1 { margin:0; font-size:1.32rem; font-weight:800; letter-spacing:.2px; }
.hero .sub { opacity:.93; margin-top:4px; font-size:.85rem; }
.hero .chips { margin-top:10px; }
.hero .chip {
  display:inline-block; background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.33); padding:4px 11px; border-radius:999px;
  font-size:.72rem; margin-right:6px; font-weight:600;
}

/* Encabezado de seccion numerado */
.sec { display:flex; align-items:center; gap:11px; margin:20px 0 10px; }
.sec-n { background:linear-gradient(120deg,var(--nav1),var(--nav2)); color:#fff;
  width:28px; height:28px; border-radius:9px; display:flex; align-items:center;
  justify-content:center; font-weight:800; font-size:.95rem; flex:0 0 auto;
  box-shadow:0 3px 8px rgba(31,78,120,.25); }
.sec-t { font-weight:800; color:var(--ink); font-size:1.08rem; line-height:1.1; }
.sec-s { color:var(--muted); font-size:.8rem; margin-top:1px; }

/* Tarjetas (st.container border) como cards suaves */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--line) !important; border-radius:14px !important;
  box-shadow:0 2px 10px rgba(20,40,70,.05); background:#fff; margin-bottom:10px;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding:2px 4px; }

.itxt .cve { display:inline-block; background:#EAF0F7; color:var(--nav1);
  font-weight:800; font-size:.78rem; padding:2px 8px; border-radius:7px; margin-right:6px; }
.itxt .nom { font-weight:700; color:var(--ink); font-size:.97rem; }
.itxt .uni { color:var(--muted); font-size:.82rem; margin-top:3px; }
.itxt .imp { color:var(--nav1); font-weight:800; font-size:1.12rem; text-align:right; }
.itxt .via { color:#9aa7b8; font-size:.72rem; font-weight:600; }

/* Totales */
.mrow { display:flex; gap:12px; margin:10px 0 2px; }
.mcard { flex:1; background:#fff; border:1px solid var(--line); border-radius:14px;
  padding:14px 16px; box-shadow:0 2px 10px rgba(20,40,70,.05); text-align:center; }
.mcard.total { background:linear-gradient(135deg,#F1F9EE,#DFF0D6); border-color:#BBE0A9; }
.mcard .lbl { color:var(--muted); font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.5px; }
.mcard .val { color:var(--ink); font-size:1.55rem; font-weight:800; line-height:1.1; margin-top:3px; }
.mcard.total .val { color:var(--green1); }

/* Estado vacio */
.empty { text-align:center; color:var(--muted); background:#fff; border:1px dashed var(--line);
  border-radius:14px; padding:26px 18px; }
.empty .em { font-size:1.9rem; }
.empty .t { font-weight:700; color:var(--ink); margin-top:6px; }
.empty .s { font-size:.85rem; margin-top:2px; }

/* Barra de total fija abajo */
.sticky-wrap { position:fixed; left:0; right:0; bottom:0; z-index:999; padding:0 8px 8px;
  pointer-events:none; }
.sticky-bar { max-width:632px; margin:0 auto; pointer-events:auto;
  background:linear-gradient(120deg,var(--nav1),var(--nav2)); color:#fff;
  display:flex; justify-content:space-between; align-items:center;
  padding:12px 18px; border-radius:15px; box-shadow:0 6px 20px rgba(20,40,70,.28); }
.sticky-bar .l { font-size:.82rem; opacity:.92; font-weight:600; }
.sticky-bar .r { font-size:.78rem; opacity:.9; text-align:right; }
.sticky-bar .r b { display:block; font-size:1.3rem; font-weight:800; margin-top:-2px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------- helpers
def seccion(num: str, titulo: str, sub: str = "") -> None:
    s = f'<div class="sec-s">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="sec"><span class="sec-n">{num}</span>'
        f'<div><div class="sec-t">{titulo}</div>{s}</div></div>',
        unsafe_allow_html=True,
    )


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
    f'<div class="sub">Líneas F y A · {snap.get("lista_nombre", "Lista 5")} · sin IVA</div>'
    f'<div class="chips"><span class="chip">🗓️ Precios: {gen_fmt}</span>'
    f'<span class="chip">📦 {len(productos)} productos</span></div></div>',
    unsafe_allow_html=True,
)

if snap.get("sin_precio"):
    st.warning("Sin precio (salen en $0): " + ", ".join(snap["sin_precio"]))

# ---------------------------------------------------- agregar producto
seccion("1", "Agrega productos", "Pega el pedido completo o busca uno por uno")
tab_pegar, tab_buscar = st.tabs(["📋 Pegar pedido", "🔎 Buscar uno por uno"])

# --- Pestaña 1: pegar el pedido y detectar claves/cantidades ---------------
with tab_pegar:
    texto = st.text_area(
        "Pega el pedido", key="pegar_txt", height=140, label_visibility="collapsed",
        placeholder="Pega aquí el pedido, por ejemplo:\n\n10 PA01\n5 cubrepolvo cartier\n"
                    "CK02 x8\n3 caja blanda anillo",
    )
    if st.button("🔍 Detectar productos", use_container_width=True, type="primary"):
        ok, malas = parser_pedido.parse_pedido(texto, productos)
        st.session_state["deteccion"] = (ok, malas)

    det = st.session_state.get("deteccion")
    if det:
        ok, malas = det
        if ok:
            st.markdown(f"**✅ Detecté {len(ok)} producto(s).** Revísalos y agrégalos:")
            for r in ok:
                via = "coincidió por nombre" if r["como"] == "nombre" else "por clave"
                with st.container(border=True):
                    a, b = st.columns([3, 1.15])
                    a.markdown(
                        f'<div class="itxt"><span class="cve">{r["cve"]}</span>'
                        f'<span class="nom">{r["descr"]}</span>'
                        f'<div class="uni">{r["cant"]} × ${r["precio"]:,.2f} '
                        f'<span class="via">· {via}</span></div></div>',
                        unsafe_allow_html=True)
                    b.markdown(f'<div class="itxt"><div class="imp">${r["importe"]:,.2f}</div></div>',
                               unsafe_allow_html=True)
            if st.button(f"➕ Agregar {len(ok)} al pedido", use_container_width=True,
                         type="primary", key="add_todos"):
                for r in ok:
                    carrito[r["cve"]] = carrito.get(r["cve"], 0) + int(r["cant"])
                st.session_state.pop("deteccion", None)
                st.toast(f"Agregados {len(ok)} productos", icon="✅")
                st.rerun()
        if malas:
            st.warning("⚠️ No reconocí: " + "  ·  ".join(malas)
                       + ".  Revisa cómo está escrito o agrégalos en **Buscar uno por uno**.")

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
n_prod = len(carrito)
seccion("2", "Tu pedido", f"{n_prod} producto(s)" if n_prod else "Vacío por ahora")
if not carrito:
    st.markdown(
        '<div class="empty"><div class="em">🧾</div>'
        '<div class="t">Aún no hay productos</div>'
        '<div class="s">Pega tu pedido o busca un producto arriba para empezar.</div></div>',
        unsafe_allow_html=True)
else:
    for cve in list(carrito.keys()):
        precio = precio_por_clave.get(cve, 0.0)
        cant = int(carrito[cve])
        importe = precio * cant
        with st.container(border=True):
            a, b = st.columns([3, 1.15])
            a.markdown(
                f'<div class="itxt"><span class="cve">{cve}</span>'
                f'<span class="nom">{descr_por_clave.get(cve, "")}</span>'
                f'<div class="uni">${precio:,.2f} c/u · línea {linea_por_clave.get(cve, "")}</div>'
                f'</div>', unsafe_allow_html=True)
            b.markdown(f'<div class="itxt"><div class="imp">${importe:,.2f}</div></div>',
                       unsafe_allow_html=True)
            ca, cb = st.columns([2, 1])
            nueva = ca.number_input(f"Cantidad {cve}", min_value=1, step=1, value=cant,
                                    key=f"q_{cve}", label_visibility="collapsed")
            if int(nueva) != cant:
                carrito[cve] = int(nueva)
                st.rerun()
            if cb.button("🗑 Quitar", key=f"del_{cve}", use_container_width=True,
                         help="Quitar del pedido"):
                carrito.pop(cve, None)
                st.session_state.pop(f"q_{cve}", None)
                st.rerun()

    if st.button("🧹 Vaciar pedido", use_container_width=True):
        st.session_state["carrito"] = {}
        for k in [k for k in st.session_state if k.startswith("q_")]:
            st.session_state.pop(k, None)
        st.rerun()

# --------------------------------------------------------------- totales
piezas = sum(int(c) for c in carrito.values())
subtotal = sum(precio_por_clave.get(cve, 0.0) * int(c) for cve, c in carrito.items())
total = subtotal  # sin IVA

if carrito:
    st.markdown(
        f'<div class="mrow">'
        f'<div class="mcard"><div class="lbl">Piezas</div><div class="val">{piezas}</div></div>'
        f'<div class="mcard total"><div class="lbl">Total · sin IVA</div>'
        f'<div class="val">${total:,.2f}</div></div></div>',
        unsafe_allow_html=True)

# --------------------------------------------------------------- exportar
if carrito:
    seccion("3", "Descargar cotización", "PDF para archivar · imagen para WhatsApp")
    with st.expander("📄 Generar PDF o imagen"):
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

# --------------------------------------------------------------- barra fija
if carrito:
    st.markdown(
        f'<div class="sticky-wrap"><div class="sticky-bar">'
        f'<div class="l">🧾 {piezas} pzas · {n_prod} productos</div>'
        f'<div class="r">Total sin IVA<b>${total:,.2f}</b></div>'
        f'</div></div>', unsafe_allow_html=True)

st.caption(f"Precios de Aspel SAE (lista {snap.get('lista_precio', 5)}), "
           f"snapshot {gen_fmt}. Total sin IVA.")
