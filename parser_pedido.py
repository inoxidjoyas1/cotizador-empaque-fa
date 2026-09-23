"""Detecta un pedido pegado como texto libre: reconoce claves y cantidades.

Reconoce, por linea (o separado por coma / punto y coma):
  '10 PA01'   'PA01 10'   'PA01 x10'   '10x PA01'   'PA01 *10'
  '10 cubrepolvo cartier'   '- 5 CAJA BLANDA ANILLO'   '3 pzas PA01'

Para cada renglon: saca la cantidad, luego busca la clave exacta y, si no la
hay, empareja de forma difusa contra la descripcion (rapidfuzz). Lo que no
alcanza el umbral se devuelve como "no reconocido" para que el usuario lo revise.

Portado del parser de cotizador-web, adaptado al snapshot de este proyecto
(campos cve_art / descr / precio).
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz, process

# Umbral de confianza para aceptar un emparejamiento difuso (0..100).
MATCH_THRESHOLD = 72

_STOPWORDS = {"de", "la", "el", "un", "una", "con", "para", "y", "por", "pieza",
              "piezas", "pza", "pzas", "pzs", "pz", "unidad", "unidades", "ud", "uds"}

# Sinonimos / apodos -> palabra que SI aparece en la descripcion del producto.
# Clave = termino canonico (como esta en el catalogo); valor = formas de decirlo.
# Se aplican al texto ANTES de emparejar, para que "morral cartier" halle el
# "CUBREPOLVO CARTIER". Ampliable: agrega mas apodos aqui.
_SINONIMOS = {
    "cubrepolvo": ["morral", "morrales", "morralito", "morralitos", "guardapolvo",
                   "guardapolvos", "funda", "fundas", "fundita", "funditas", "cubre",
                   "cubrepolvos", "bolsa de tela", "bolsita de tela", "saco", "saquito"],
    "manta pulidora": ["pano", "panos", "panito", "tela", "telas", "franela",
                       "franelas", "trapo", "trapito", "pulidor", "pulidora",
                       "pano pulidor", "tela pulidora", "limpiador"],
    "caja": ["estuche", "estuches", "cajita", "cajitas", "cajas", "box", "cajton"],
    "kit": ["juego", "juegos", "set", "sets", "combo", "combos", "paquete",
            "paquetes", "conjunto"],
    "bolsa": ["bolsita", "bolsitas", "bolsas", "bolso", "bolsos"],
    "joyero": ["cofre", "cofres", "alhajero", "alhajera", "joyerito", "joyeritos",
               "joyeros", "joyera"],
    "etiqueta": ["tag", "tags", "etiquetita", "etiquetitas", "etiquetas"],
    "tarjeta": ["tarjetita", "tarjetitas", "tarjetas", "carta"],
    "instructivo": ["manual", "manuales", "instrucciones", "instructivos", "instruccion"],
    "sticker": ["calcomania", "calcomanias", "pegatina", "pegatinas", "engomado",
                "engomados", "estampa", "estampas", "stickers", "calca"],
    "lima": ["limita", "limitas", "limador", "limas", "limadora"],
    "certificados": ["certificado", "certif", "certificacion", "certificaciones"],
    "papel": ["papeles", "hoja", "hojas"],
    "pulsera": ["brazalete", "brazaletes", "pulseras", "esclava", "esclavas",
                "pulserita", "pulseritas"],
    "anillo": ["anillos", "aro", "aros", "sortija", "sortijas", "anillito", "anillitos"],
    "blanda": ["suave", "suaves", "flexible", "flexibles", "blandas"],
    "dura": ["rigida", "rigidas", "duras", "rigido"],
    "rosa": ["rosada", "rosado", "rosados", "rosadas", "pink"],
    "chica": ["chico", "chicos", "chicas", "pequeno", "pequena", "pequenos",
              "pequenas", "peque", "chiquita", "chiquito", "mini", "cch"],
    "gr": ["grande", "grandes", "gde", "gdes", "gd"],
    # marcas / abreviaturas
    "louis vuitton": ["lv", "louisvuitton", "luis vuitton", "vuitton"],
    "van cleef": ["vc", "vancleef", "vancleff", "vancleef", "cleef", "van cliff"],
    "swarovski": ["swaro", "swarovsky", "suarovski", "swarowski", "svarovski", "swarosky"],
    "tiffany": ["tiff", "tifany", "tifani", "tiffani", "tifanny", "tiffani & co"],
    "cartier": ["cartie", "cartir", "cartiier", "kartier"],
    "pandora": ["pandra", "pandoras", "pndora"],
    "chanel": ["chanell", "canel", "channel", "chanelle"],
    "dior": ["diior", "dyor"],
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


# Mapa invertido {apodo_normalizado: termino_canonico_normalizado}, listo para usar.
_SYN = {}
for _canon, _lista in _SINONIMOS.items():
    for _s in _lista:
        _SYN[_norm(_s)] = _norm(_canon)


def _aplicar_sinonimos(query: str) -> str:
    """Reemplaza apodos por el termino canonico. Maneja frases de 2 palabras."""
    q = query
    # frases de dos palabras primero (p.ej. 'bolsa de tela', 'pano pulidor')
    for apodo, canon in _SYN.items():
        if " " in apodo and apodo in q:
            q = q.replace(apodo, canon)
    # luego palabra por palabra
    return " ".join(_SYN.get(tok, tok) for tok in q.split())


def _strip_bullets(line: str) -> str:
    line = re.sub(r"^\s*[-*•·>]+\s*", "", line)
    line = re.sub(r"^\s*\d+\s*[\).]\s+", "", line)
    return line.strip()


def _extract_qty(text: str) -> tuple[int, str]:
    """Extrae la cantidad. Reconoce '2 PA01', '2x PA01', 'PA01 x2', '3 pzas'."""
    m = re.match(r"^\s*(\d+)\s*[xX]?\s+(.+)$", text)
    if m:
        return max(int(m.group(1)), 1), m.group(2).strip()
    m = re.search(r"(?:^|\s)[xX*]\s*(\d+)\b", text)
    if m:
        qty = int(m.group(1))
        text = (text[:m.start()] + text[m.end():]).strip()
        return max(qty, 1), text
    m = re.search(r"\b(\d+)\s*(?:pz|pzs|pzas|piezas|pieza|unidades|uds?)\b", text, re.I)
    if m:
        qty = int(m.group(1))
        text = (text[:m.start()] + text[m.end():]).strip()
        return max(qty, 1), text
    # 'PA01 10' / 'CAJA ... 5': numero suelto al final = cantidad (la clave
    # tipo PA01 lleva sus digitos pegados, asi que \s+\d+ no la parte).
    m = re.match(r"^(.*\S)\s+(\d+)$", text)
    if m:
        return max(int(m.group(2)), 1), m.group(1).strip()
    return 1, text.strip()


def _clean_article_text(text: str) -> str:
    text = re.sub(r"[xX]\s*\d+", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    tokens = [t for t in _norm(text).split() if t not in _STOPWORDS]
    return " ".join(tokens).strip()


class _Cat:
    """Indice de busqueda construido una vez desde la lista de productos."""

    def __init__(self, productos: list[dict]):
        self.by_clave = {p["cve_art"].upper(): p for p in productos}
        self.choices = {p["cve_art"]: _norm(f"{p['cve_art']} {p['descr']}")
                        for p in productos}
        self.prod_by_clave = {p["cve_art"]: p for p in productos}


def _match(text: str, cat: _Cat) -> tuple[dict | None, float, str]:
    # 1) clave exacta en algun token (letras+digitos), p.ej. PA01, CAD01, CK02
    for tok in re.findall(r"[A-Za-z]{1,4}\d{1,3}", text):
        if tok.upper() in cat.by_clave:
            return cat.by_clave[tok.upper()], 100.0, "clave"
    query = _aplicar_sinonimos(_clean_article_text(text))
    if not query:
        return None, 0.0, ""
    # 2) difuso contra "clave descripcion"
    best = process.extractOne(query, cat.choices, scorer=fuzz.token_set_ratio)
    if best is None:
        return None, 0.0, ""
    _s, score, clave = best
    return cat.prod_by_clave[clave], float(score), "nombre"


def parse_pedido(texto: str, productos: list[dict]) -> tuple[list[dict], list[str]]:
    """Devuelve (reconocidos, no_reconocidos).

    reconocidos: [{cve, descr, linea, cant, precio, importe, score, como}]
                 (mismas claves fusionadas: se suman cantidades).
    no_reconocidos: lista de textos crudos que no se pudieron emparejar.
    """
    cat = _Cat(productos)
    piezas = re.split(r"[\n;,]", texto or "")
    reconocidos: dict[str, dict] = {}
    no_reconocidos: list[str] = []

    for raw in piezas:
        raw = raw.strip()
        if not raw:
            continue
        body = _strip_bullets(raw)
        if not body:
            continue
        qty, rest = _extract_qty(body)
        prod, score, como = _match(rest, cat)
        if prod and score >= MATCH_THRESHOLD:
            cve = prod["cve_art"]
            precio = prod.get("precio") or 0.0
            if cve in reconocidos:
                reconocidos[cve]["cant"] += qty
                reconocidos[cve]["importe"] = round(reconocidos[cve]["cant"] * precio, 2)
            else:
                reconocidos[cve] = {
                    "cve": cve, "descr": prod.get("descr", ""),
                    "linea": prod.get("linea", ""), "cant": qty,
                    "precio": precio, "importe": round(precio * qty, 2),
                    "score": round(score, 1), "como": como,
                }
        else:
            no_reconocidos.append(raw)

    return list(reconocidos.values()), no_reconocidos


if __name__ == "__main__":
    import json
    from pathlib import Path
    d = json.loads(Path(__file__).with_name("data").joinpath("snapshot.json")
                   .read_text(encoding="utf-8"))
    prods = d["productos"]
    demo = """10 PA01
    5 CAD01
    cubrepolvo cartier x3
    2 caja blanda anillo gr
    xyz que no existe 4
    CK02 8"""
    ok, malas = parse_pedido(demo, prods)
    print("RECONOCIDOS:")
    for r in ok:
        print(f"  {r['cve']:8} x{r['cant']:<3} {r['descr'][:30]:30} ${r['importe']:.2f} ({r['como']})")
    print("NO RECONOCIDAS:", malas)
