# Cotizador de empaque (líneas F y A) — INOXIDJOYAS

App web para cotizar productos de **empaque**: línea **F** (cajas y kits) y línea **A**
(cubrepolvos). Eliges productos, pones cantidades y calcula **Subtotal** y **Total**
(**sin IVA**, con el **precio de lista 5** de Aspel SAE — que SAE etiqueta "Precio de lista 3").

## Cómo funciona (importante)

La app **no** se conecta a SAE. Vive en la nube (Streamlit Community Cloud) y lee un
**snapshot** de precios (`data/snapshot.json`). Por eso funciona **24/7 aunque tu PC
esté apagada**.

Los precios se refrescan desde la **PC de la oficina** (la única que alcanza Aspel SAE):
un script lee SAE y sube el snapshot a GitHub. La app en la nube se actualiza sola.

```
  PC oficina (con SAE)                    GitHub                 Nube (Streamlit)
 ┌─────────────────────┐   git push   ┌──────────────┐  deploy  ┌──────────────────┐
 │ refrescar_precios.py │ ───────────▶ │ snapshot.json │ ───────▶ │ app.py (cotizador)│
 │  (Programador tareas)│              └──────────────┘          │  URL para todos   │
 └─────────────────────┘                                        └──────────────────┘
```

- **Truco clave:** un cambio de precio solo se hace en SAE (con la PC encendida). El
  siguiente refresco sube ese cambio. En la práctica los precios están siempre al día.
- Refresco programado: **cada 15 días** + cuando lo dispares a mano (no cambian seguido).

---

## Puesta en marcha (una sola vez)

### 1. Subir el proyecto a GitHub
En tu cuenta **github.com/inoxidjoyas1**, crea un repositorio **vacío** llamado
`cotizador-empaque-fa` (sin README). Luego, en esta carpeta:

```bash
git remote add origin https://github.com/inoxidjoyas1/cotizador-empaque-fa.git
git push -u origin main
```

> `.env` y `.streamlit/secrets.toml` **no** se suben (están en `.gitignore`). Ahí viven
> las credenciales de SAE y la contraseña de la app.

### 2. Publicar la app en Streamlit Community Cloud (gratis)
1. Entra a https://share.streamlit.io con tu cuenta de GitHub.
2. **New app** → repo `inoxidjoyas1/cotizador-empaque-fa`, branch `main`, archivo `app.py`.
3. **Advanced settings → Secrets**, pega:
   ```toml
   app_password = "inoxid2026"
   ```
   (cámbiala por la que quieras; es la que pedirá la app).
4. **Deploy**. En ~1 minuto tienes una URL pública tipo
   `https://cotizador-empaque-fa.streamlit.app` para compartir.

### 3. Configurar el refresco automático en la PC de la oficina

**a) Prueba manual** (debe decir "Snapshot OK" y "Git push OK"):
```bash
python refrescar_precios.py
```
Si el push pide usuario/token la primera vez, guárdalo (Windows lo recuerda con el
Administrador de credenciales). Con GitHub usa un **Personal Access Token** como contraseña.

**b) Programar cada 15 días** (Programador de tareas de Windows):
1. Abre **Programador de tareas** → **Crear tarea básica**.
2. Nombre: `Refrescar precios cotizador empaque`.
3. Desencadenador: **Diariamente**, y en "Repetir cada" pon **15 días**.
4. Acción: **Iniciar un programa** → Programa/script:
   `C:\Users\useer\Desktop\Proyectos Claude\conectores y skills\cotizador-empaque-fa\actualizar_precios.bat`
5. Finalizar.

> También puedes **actualizar cuando quieras**: doble clic en `actualizar_precios.bat`
> (o corre `python refrescar_precios.py`) justo después de cambiar precios en SAE.

---

## Uso diario (cualquier vendedor)
1. Abre la URL de la app.
2. Escribe la contraseña.
3. En la tabla, elige el **Producto** (busca por clave o nombre) y la **Cantidad**.
   Agrega más renglones con el **+**.
4. Lee el **Subtotal** y **Total**. Botón **Descargar** para guardar la cotización
   (CSV que abre en Excel).

---

## Archivos
| Archivo | Qué es |
|---|---|
| `app.py` | La app web (corre en la nube). |
| `db_sae.py` | Conexión de solo lectura a SAE (solo en la PC de oficina). |
| `refrescar_precios.py` | Lee SAE → escribe `data/snapshot.json` → `git push`. |
| `actualizar_precios.bat` | Lo que corre el Programador de tareas (o doble clic). |
| `data/snapshot.json` | Foto de precios que lee la app. Se sube a git. |
| `.env` | Credenciales SAE (**local, no se sube**). Ver `.env.ejemplo`. |
| `.streamlit/secrets.toml` | Contraseña de la app (**local, no se sube**). |

## Datos técnicos
- Productos: `INVE01` filtrado por `LIN_PROD IN ('F','A')` y `STATUS='A'` (65 activos al 2026-09-17).
- Precio: `PRECIO_X_PROD01` con `CVE_PRECIO = 5`.
- Total = Subtotal (sin IVA).
- Cambiar líneas/lista: variables `LINEAS` y `LISTA_PRECIO` en el `.env`.
