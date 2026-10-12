# 🎯 Dropshipping Hunter — evaluador de productos para EE. UU.

Te dice **qué producto lanzar, cuál probar, cuál vigilar y cuál sacar de tu tienda**, con datos medidos de verdad.
Nada se inventa: si una fuente no responde, el panel dice «Sin datos».

- **Panel en tu PC:** ícono **«Dropshipping Hunter»** del escritorio (o `iniciar_centinela.bat`).
- **Panel en el teléfono:** https://anderssonfranco78-jpg.github.io/dropshipping_hunter/ (guárdalo en la pantalla de inicio).

---

## Cómo funciona (en 5 pasos)

1. **Mide el mercado de EE. UU.**
   - **YouTube Shorts:** vistas de los Shorts más vistos del producto y cuántos pasan el millón de vistas (competencia). Es el mismo tipo de video que publicarás en YouTube Shorts, Instagram Reels y Facebook Reels.
   - **Google Trends:** cómo se busca la *categoría* semana a semana durante 12 meses. Muchos gadgets casi no se buscan por nombre (se descubren en video), por eso se mide la categoría.
2. **Califica el producto** con las **7 Reglas de Oro** (WOW en 3 s, dolor real, que no esté en Walmart, margen y markup ≥ 3×, precio de $29–$69, que no sea frágil ni de tallas, envío ≤ 12 días).
3. **Calcula la ganancia real** por venta en el peor caso: venta − proveedor − envío − pasarela (3.49% + $0.49) − 15% del costo para reponer cajas dañadas − 1% de reclamos.
4. **Da un veredicto:** `LANZAR` · `PROBAR` · `VIGILAR` · `DESCARTAR`. Si lo tienes marcado «En mi tienda»: `MANTENER` o `RETIRAR` (cuando queda en Vigilar/Descartar 3 corridas seguidas).
5. **Sigue buscando:** el **Radar** mide solo, unas pocas ideas por corrida, y te muestra las búsquedas que están subiendo en Google.

## Qué haces tú

1. En el **Radar** o en tu búsqueda, eliges una idea → la buscas en **DSers** (Shopify) → eliges proveedor **AliExpress Choice** con 100+ unidades.
2. En el panel pulsas **«Evaluar con costos»** y copias precio, costo y envío de DSers. El Hunter lo mide y lo ubica en el **Ranking**.
3. Si sale `LANZAR`: lo publicas en Shopify, creas **una cuenta por plataforma** (YouTube Shorts, Instagram Reels, Facebook Reels) y sigues la lista de lanzamiento del panel.
4. Lo marcas **«En mi tienda»**. Desde ahí el Hunter te avisa si sus números caen.

El stock **no hace falta anotarlo**: DSers lo revisa al importar y lo sincroniza a diario. Si anotas menos de 100 unidades, el producto queda `KO-STOCK`.

## Dónde corre

| Dónde | Cuándo | Qué hace |
|---|---|---|
| **Tu PC** (motor / centinela) | Arranca solo con Windows, sin ventanas. Botón «Actualizar ahora» o cada N horas | Mide, recalcula y **sube los datos a GitHub** para tu teléfono |
| **GitHub Actions** (nube) | Cada 6 h (6 a. m., 12 p. m., 6 p. m., 12 a. m.; GitHub puede retrasarlo varias horas), al guardar un producto desde el teléfono, o **al instante con «Actualizar» en el teléfono** | Lo mismo, y publica en el panel del teléfono |

**Botón «Actualizar» en el teléfono:** la primera vez toca «Conectar con GitHub», crea el permiso (el enlace ya viene rellenado; elige el repositorio `dropshipping_hunter`) y pega el código. Queda guardado solo en ese teléfono. Desde ahí «Actualizar» enciende el robot y muestra su avance, y puedes guardar productos sin la PC.

**Google:** sus datos son semanales, así que el Hunter pregunta **una vez al día por término** y comparte esa medición entre PC y nube (`data/trends_cache.json`). Si Google bloquea la red (429 / CAPTCHA por «tráfico inusual»), no insiste: en el PC hace una pausa de 6 h y usa la última medición real (máx. 7 días, con su fecha). La nube cambia de IP en cada corrida.

## Archivos

| Archivo | Quién lo escribe | Para qué |
|---|---|---|
| `data/user_products.json` | **Tú** (a mano o con los botones del panel en tu PC) | Productos en evaluación: costos de DSers, palabras clave, «en_tienda» |
| `data/radar_ideas.json` | **Tú** (opcional) | Ideas que el Radar debe medir |
| `data/dashboard_data.js`, `data/radar.json`, `data/history/`, `data/trends_cache.json` | El robot | Lo que muestra el panel e historial de corridas |
| `dossier_productos_ganadores.md` | El robot | Guiones completos de los 4 ganchos por producto |
| `assets/images/` | Tú | Fotos de producto (ver `assets/images/README.md`) |

## Comandos

```bash
python main.py                 # una corrida completa (productos + Radar)
python main.py --no-radar      # solo tus productos
python centinela_local.py      # motor + panel en http://127.0.0.1:8765
python -m unittest discover -s tests -p "test_*.py"   # pruebas
```

> ⚠️ El repositorio es **público**: cualquiera con el enlace puede ver tus productos, costos y márgenes en el panel del teléfono.
