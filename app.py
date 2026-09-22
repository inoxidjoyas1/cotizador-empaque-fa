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

import cajas as cajas_mod
import cotizacion_doc
import parser_pedido

AQUI = Path(__file__).resolve().parent
SNAPSHOT = AQUI / "data" / "snapshot.json"

st.set_page_config(page_title="Cotizador de empaque - INOXIDJOYAS",
                   page_icon="📦", layout="wide",
                   initial_sidebar_state="collapsed")

# --------------------------------------------------------------------- estilos
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

:root { --nav1:#1F4E78; --nav2:#2E6DA4; --ink:#1A2530;
        --line:#E7EDF4; --muted:#8593a4; --green1:#2f7d32; }

html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif !important;
}
.stApp { background:#F5F8FC; }
.block-container { padding-top:.7rem; padding-bottom:7rem; max-width:1040px; }
#MainMenu, footer, header {visibility:hidden;}
/* En PC los dos paneles quedan pegados arriba; en celular se apilan solos. */
div[data-testid="stHorizontalBlock"] { align-items:flex-start; }

/* Botones */
.stButton > button, .stDownloadButton > button {
  min-height:48px; border-radius:12px; font-weight:700; font-size:1rem;
}
.stButton > button:active, .stDownloadButton > button:active { transform:translateY(1px); }
button[kind="primary"], button[kind="primaryFormSubmit"] {
  background:linear-gradient(120deg,var(--nav1),var(--nav2)) !important;
  border:none !important; box-shadow:0 4px 12px rgba(31,78,120,.25) !important;
}
button[kind="secondary"] {
  background:#fff !important; border:1px solid var(--line) !important; color:var(--ink) !important;
}
.stNumberInput input, .stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
  min-height:46px; font-size:1rem; border-radius:10px !important;
}
.stTextArea textarea { line-height:1.55; }

/* Tabs = control segmentado (pista gris, activa en blanco con texto azul) */
[data-testid="stTabs"] [role="tablist"] {
  display:inline-flex; width:auto; gap:4px; background:#E7EDF5;
  border-radius:13px; padding:5px; border-bottom:none !important;
}
[data-testid="stTabs"] [role="tablist"]::after,
[data-testid="stTabs"] [role="tablist"]::before { display:none !important; content:none !important; }
[data-testid="stTab"] {
  height:auto; min-height:0; background:transparent; border:none !important;
  border-radius:9px; padding:8px 18px; color:#5b6b7e; margin:0;
}
[data-testid="stTab"] p { font-size:.93rem; font-weight:700; margin:0; white-space:nowrap; }
[data-testid="stTab"][aria-selected="true"] {
  background:#fff; box-shadow:0 1px 4px rgba(20,40,70,.14); border:none !important;
}
[data-testid="stTab"][aria-selected="true"] p { color:var(--nav1) !important; }
[data-testid="stTab"]:hover { color:var(--nav1); }
/* Oculta el indicador azul (div hijo sin testid) que Streamlit pinta abajo. */
[data-testid="stTab"] > div:not([data-testid="stMarkdownContainer"]) { display:none !important; }

/* Hero minimal */
.hero { padding:6px 2px 2px; }
.hero h1 { margin:0; font-size:1.45rem; font-weight:800; color:var(--ink); }
.hero .sub { color:var(--muted); font-size:.9rem; margin-top:2px; }

/* Titulo de seccion, limpio */
.tt { font-weight:800; color:var(--ink); font-size:1.12rem; margin:22px 0 10px;
      display:flex; justify-content:space-between; align-items:baseline; }
.tt .x { color:var(--muted); font-weight:600; font-size:.85rem; }

/* Tarjetas (st.container border) */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--line) !important; border-radius:16px !important;
  box-shadow:0 2px 10px rgba(20,40,70,.045); background:#fff; margin-bottom:12px;
}
div[data-testid="stVerticalBlockBorderWrapper"] > div { padding:4px 6px; }

.itxt .cve { display:inline-block; background:#EEF3F9; color:var(--nav1);
  font-weight:800; font-size:.72rem; padding:2px 8px; border-radius:7px; margin-right:7px;
  vertical-align:middle; letter-spacing:.3px; }
.itxt .nom { font-weight:700; color:var(--ink); font-size:.98rem; }
.itxt .uni { color:var(--muted); font-size:.8rem; margin-top:4px; }
.itxt .imp { color:var(--nav1); font-weight:800; font-size:1.18rem; text-align:right; line-height:1.9; }

/* Estado vacio */
.empty { text-align:center; color:var(--muted); padding:22px 16px; }
.empty .em { font-size:2rem; }
.empty .t { font-weight:700; color:var(--ink); margin-top:6px; font-size:1rem; }
.empty .s { font-size:.86rem; margin-top:2px; }

/* Panel interno de envio */
.envio { background:linear-gradient(135deg,#FFFCF4,#FBF1DA); border:1px solid #EEDCA9;
  border-radius:16px; padding:14px 16px; }
.envio .cap { color:#a07c22; font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.6px; }
.envio .caja { font-size:1.3rem; font-weight:800; color:#7a5a12; margin-top:2px; }
.envio .stats { display:flex; gap:10px; margin-top:12px; }
.envio .st { flex:1; background:#fff; border:1px solid #EFE1BE; border-radius:11px; padding:8px 10px; }
.envio .st .l { color:#a08a58; font-size:.68rem; font-weight:700; text-transform:uppercase; letter-spacing:.3px; }
.envio .st .v { color:#5a4a20; font-weight:800; font-size:1.02rem; margin-top:1px; }
.envio .note { color:#a07c22; font-size:.78rem; margin-top:10px; }

/* Barra de total fija abajo */
.sticky-wrap { position:fixed; left:0; right:0; bottom:0; z-index:999; padding:0 10px 10px; pointer-events:none; }
.sticky-bar { max-width:1024px; margin:0 auto; pointer-events:auto;
  background:linear-gradient(120deg,var(--nav1),var(--nav2)); color:#fff;
  display:flex; justify-content:space-between; align-items:center;
  padding:14px 20px; border-radius:16px; box-shadow:0 8px 24px rgba(20,40,70,.3); }
.sticky-bar .l { font-size:.82rem; opacity:.9; font-weight:600; }
.sticky-bar .r { text-align:right; }
.sticky-bar .r span { font-size:.72rem; opacity:.85; }
.sticky-bar .r b { display:block; font-size:1.4rem; font-weight:800; line-height:1.1; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def titulo(t: str, extra: str = "") -> None:
    x = f'<span class="x">{extra}</span>' if extra else ""
    st.markdown(f'<div class="tt"><span>{t}</span>{x}</div>', unsafe_allow_html=True)


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
pesovol_por_clave = {p["cve_art"]: p.get("peso_vol") for p in productos}
pesoreal_por_clave = {p["cve_art"]: p.get("peso_real") for p in productos}
cajas_cat = snap.get("cajas", [])
factor_llenado = snap.get("factor_llenado", 0.70)


def fmt_peso(kg: float | None) -> str:
    if not kg:
        return "—"
    return f"{kg * 1000:.0f} g" if kg < 1 else f"{kg:.2f} kg"
etiqueta = {p["cve_art"]: f"{p['cve_art']} - {p['descr']}".strip(" -") for p in productos}
clave_por_etiqueta = {v: k for k, v in etiqueta.items()}
opciones = sorted(etiqueta.values())

gen = snap.get("generado", "")
try:
    gen_fmt = dt.datetime.fromisoformat(gen).strftime("%d/%m/%Y")
except ValueError:
    gen_fmt = gen or "?"

if "carrito" not in st.session_state:
    st.session_state["carrito"] = {}
carrito: dict[str, int] = st.session_state["carrito"]

# --------------------------------------------------------------------- hero
st.markdown(
    '<div class="hero"><h1>📦 Cotizador de empaque</h1>'
    '<div class="sub">Líneas F y A · precios sin IVA</div></div>',
    unsafe_allow_html=True,
)

# Totales (se calculan antes de pintar, para los paneles y la barra fija).
n_prod = len(carrito)
piezas = sum(int(c) for c in carrito.values())
total = sum(precio_por_clave.get(cve, 0.0) * int(c) for cve, c in carrito.items())

# Dos paneles: en PC lado a lado, en celular se apilan solos.
col_add, col_ped = st.columns(2, gap="large")

# ============================ IZQUIERDA: agregar ============================
with col_add:
    titulo("Agregar productos")
    tab_pegar, tab_buscar = st.tabs(["📋 Pegar pedido", "🔎 Buscar"])

    with tab_pegar:
        texto = st.text_area(
            "Pega el pedido", key="pegar_txt", height=140, label_visibility="collapsed",
            placeholder="Pega aquí el pedido, por ejemplo:\n\n10 PA01\n5 cubrepolvo cartier\nCK02 x8",
        )
        if st.button("Detectar productos", use_container_width=True, type="primary"):
            ok, malas = parser_pedido.parse_pedido(texto, productos)
            st.session_state["deteccion"] = (ok, malas)

        det = st.session_state.get("deteccion")
        if det:
            ok, malas = det
            if ok:
                for r in ok:
                    with st.container(border=True):
                        a, b = st.columns([3, 1.1])
                        a.markdown(
                            f'<div class="itxt"><span class="cve">{r["cve"]}</span>'
                            f'<span class="nom">{r["descr"]}</span>'
                            f'<div class="uni">{r["cant"]} × ${r["precio"]:,.2f}</div></div>',
                            unsafe_allow_html=True)
                        b.markdown(f'<div class="itxt"><div class="imp">${r["importe"]:,.2f}</div></div>',
                                   unsafe_allow_html=True)
                if st.button(f"Agregar {len(ok)} al pedido", use_container_width=True,
                             type="primary", key="add_todos"):
                    for r in ok:
                        carrito[r["cve"]] = carrito.get(r["cve"], 0) + int(r["cant"])
                    st.session_state.pop("deteccion", None)
                    st.rerun()
            if malas:
                st.warning("No reconocí: " + "  ·  ".join(malas))

    with tab_buscar:
        sel = st.selectbox("Producto", opciones, index=None,
                           placeholder="Escribe clave o nombre…", label_visibility="collapsed")
        c1, c2 = st.columns([1, 2])
        cant_add = c1.number_input("Cantidad", min_value=1, step=1, value=1,
                                   label_visibility="collapsed")
        if c2.button("Agregar al pedido", use_container_width=True, type="primary",
                     disabled=sel is None) and sel is not None:
            cve = clave_por_etiqueta[sel]
            carrito[cve] = carrito.get(cve, 0) + int(cant_add)
            st.rerun()

# =================== DERECHA: pedido + envio + descarga ====================
with col_ped:
    titulo("Tu pedido", f"{n_prod} producto(s)" if n_prod else "")
    if not carrito:
        st.markdown(
            '<div class="empty"><div class="em">🧾</div>'
            '<div class="t">Tu pedido está vacío</div>'
            '<div class="s">Pega tu pedido o busca un producto arriba.</div></div>',
            unsafe_allow_html=True)
    else:
        for cve in list(carrito.keys()):
            precio = precio_por_clave.get(cve, 0.0)
            cant = int(carrito[cve])
            with st.container(border=True):
                a, b = st.columns([3, 1.1])
                a.markdown(
                    f'<div class="itxt"><span class="cve">{cve}</span>'
                    f'<span class="nom">{descr_por_clave.get(cve, "")}</span>'
                    f'<div class="uni">${precio:,.2f} c/u</div></div>',
                    unsafe_allow_html=True)
                b.markdown(f'<div class="itxt"><div class="imp">${precio * cant:,.2f}</div></div>',
                           unsafe_allow_html=True)
                ca, cb = st.columns([2, 1])
                nueva = ca.number_input(f"Cantidad {cve}", min_value=1, step=1, value=cant,
                                        key=f"q_{cve}", label_visibility="collapsed")
                if int(nueva) != cant:
                    carrito[cve] = int(nueva)
                    st.rerun()
                if cb.button("Quitar", key=f"del_{cve}", use_container_width=True):
                    carrito.pop(cve, None)
                    st.session_state.pop(f"q_{cve}", None)
                    st.rerun()

        if st.button("Vaciar pedido", use_container_width=True):
            st.session_state["carrito"] = {}
            for k in [k for k in st.session_state if k.startswith("q_")]:
                st.session_state.pop(k, None)
            st.rerun()

    # ------------------------------------------ envio (uso interno)
    if carrito and cajas_cat:
        items = [{"peso_vol": pesovol_por_clave.get(cve),
                  "peso_real": pesoreal_por_clave.get(cve), "cant": int(c)}
                 for cve, c in carrito.items()]
        rec = cajas_mod.recomendar(items, cajas_cat, factor_llenado)
        caja_txt = rec["caja"]["nombre"] if rec["caja"] else "—"
        notas = []
        if rec["excede"]:
            notas.append("⚠️ El pedido excede la caja más grande: probablemente se "
                         "necesiten 2 o más cajas.")
        if rec["sin_peso"]:
            notas.append(f"ℹ️ {rec['sin_peso']} producto(s) sin peso registrado: el "
                         "cálculo es aproximado.")
        nota_html = "".join(f'<div class="note">{n}</div>' for n in notas)
        titulo("Envío", "uso interno")
        st.markdown(
            f'<div class="envio"><div class="cap">📦 Caja recomendada</div>'
            f'<div class="caja">{caja_txt}</div>'
            f'<div class="stats">'
            f'<div class="st"><div class="l">Volumétrico</div>'
            f'<div class="v">{fmt_peso(rec["total_vol"])}</div></div>'
            f'<div class="st"><div class="l">Gramaje (real)</div>'
            f'<div class="v">{fmt_peso(rec["total_real"])}</div></div>'
            f'<div class="st"><div class="l">Peso a tomar</div>'
            f'<div class="v">{fmt_peso(rec["facturable"])}</div></div>'
            f'</div>{nota_html}</div>',
            unsafe_allow_html=True)

    # ------------------------------------------ exportar
    if carrito:
        with st.expander("📄 Descargar cotización (PDF o imagen)"):
            cliente = st.text_input("Cliente", placeholder="Nombre del cliente")
            folio = st.text_input("Folio", placeholder="COT-001")
            fecha = st.date_input("Fecha", value=dt.date.today(), format="DD/MM/YYYY")

            meta = {"cliente": cliente, "folio": folio,
                    "fecha": fecha.strftime("%d/%m/%Y"),
                    "lista": snap.get("lista_nombre", "Lista 5")}
            filas = [{
                "clave": cve, "descr": descr_por_clave.get(cve, ""), "linea": "",
                "cant": int(c), "pu": precio_por_clave.get(cve, 0.0),
                "importe": precio_por_clave.get(cve, 0.0) * int(c),
            } for cve, c in carrito.items()]
            base_nombre = f"cotizacion_{folio or fecha.strftime('%Y%m%d')}"

            pdf_bytes = cotizacion_doc.construir_pdf(meta, filas, total, total)
            png_bytes = cotizacion_doc.pdf_a_png(pdf_bytes)

            d1, d2 = st.columns(2)
            d1.download_button("⬇️ PDF", data=pdf_bytes, file_name=f"{base_nombre}.pdf",
                               mime="application/pdf", use_container_width=True, type="primary")
            if png_bytes:
                d2.download_button("🖼️ Imagen", data=png_bytes, file_name=f"{base_nombre}.png",
                                   mime="image/png", use_container_width=True)

# --------------------------------------------------------------- barra fija
if carrito:
    st.markdown(
        f'<div class="sticky-wrap"><div class="sticky-bar">'
        f'<div class="l">{piezas} piezas · {n_prod} productos</div>'
        f'<div class="r"><span>Total sin IVA</span><b>${total:,.2f}</b></div>'
        f'</div></div>', unsafe_allow_html=True)

st.caption(f"Precios actualizados al {gen_fmt}.")
