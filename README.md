# 🎯 Dropshipping Hunter — Sistema de Inteligencia y Ganadores

Sistema integral y automatizado de inteligencia de mercado y prospección de productos ganadores para **comercio electrónico orgánico ($0 en publicidad)**, diseñado bajo la metodología canónica del **Segundo Cerebro Antigravity**.

---

## ✅ Cómo se opera hoy (octubre 2026)

**El Hunter es el cerebro de decisión, no un buscador de proveedores.** Tú eliges producto y proveedor (búsqueda por imagen + lista de 5 puntos de la Nota 17); DSers sincroniza stock y pedidos con Shopify; el Hunter decide si el producto merece importarse.

1. **Tus datos van en `data/user_products.json`** (el robot solo lo lee, nunca lo escribe):
   - `unit_cost_usd` + `shipping_cost_usd` (con envío a EE. UU.), `srp_usd`.
   - `verified_stock` (unidades de la variante elegida) y `verified_date` (AAAA-MM-DD).
   - `rule_inputs`: tus puntuaciones de las 7 Reglas de Oro; `trends_keyword` para Google Trends.
2. **Reglas automáticas:**
   - Stock < 100 → **KO-STOCK** (descalificado sin importar el puntaje).
   - Stock sin verificar o con más de 7 días → no puede ser Ganador (*Contendiente condicional*).
   - **Margen estresado** = venta − costo puesto − pasarela (3.49% + $0.49) − 15% de reemplazos − 1% contracargos.
3. **Actualizar:** doble clic en `iniciar_centinela.bat` → panel en `http://127.0.0.1:8765` → **Actualizar ahora**. Todo en segundo plano, sin ventanas. En la nube corre solo cada día a las 06:00 (El Salvador).
4. **Alertas del panel:** 🔴 requiere acción (KO-STOCK, margen estresado < 50%, Google Trends caído, errores en tu archivo) · 🟡 verificación pendiente · gris = fuente retirada (TikTok/Meta/Freight, no se consultan).

Flags opcionales de `main.py`: `--scrape-suppliers` (intenta leer AliExpress con Chrome headless; suele ser bloqueado), `--probe-all-sources` (intenta TikTok/Meta/Freight), `--require-live` (código 3 si hay alertas rojas), `--offline` (solo pruebas, datos MOCK).

> ⚠️ Si el repositorio es público, GitHub Pages publica también costos y márgenes de `data/`.

> La tabla "Ganadores Actuales Validados" de abajo es histórica (septiembre 2026); la fuente vigente es `data/user_products.json` y el panel.

---

## 🚀 ¿Qué es Dropshipping Hunter?

Es un motor privado y 100% gratuito que rastrea y audita señales de demanda real en internet conectándose de forma silenciosa y programática a:
1. **TikTok Creative Center:** Anuncios con mayor CTR y longevidad en redes.
2. **Meta Ad Library:** Tiendas escalando creativos activos en Facebook e Instagram.
3. **Google Trends:** Curvas de interés ascendente en los últimos 90 días.
4. **AliExpress / CJ Dropshipping:** Costos de fábrica y tiempos de envío express (7-10 días).

Todo producto cosechado es evaluado matemáticamente bajo el **Filtro de Acero de las 7 Reglas de Oro**.

---

## ⚖️ Las 7 Reglas de Oro (Filtro Canónico)

1. **Efecto WOW Visual (0-3s):** Demostración instantánea de transformación o funcionamiento que frena el scroll.
2. **Dolor Agudo o Pasión Ferviente:** Resuelve una molestia física/emocional real (ciática, manchas dentales, pelos de mascotas).
3. **Inexistencia en Retail Local:** Imposible de comprar en el supermercado de la esquina.
4. **Margen Bruto Mínimo 3x (Markup):** $P_{\text{venta}} \ge \text{Costo Puesto} \times 3$. Margen neto limpio $\ge 65\%$.
5. **Rango de Ticket Óptimo ($29 – $69 USD):** Compra por impulso sin fricción deliberativa.
6. **Cero Problemas de Tallas o Fragilidad:** Libre de vidrios rompibles y tallajes de ropa.
7. **Logística Rápida Rastreable (7 a 10 días):** Almacenes con YunExpress / CJPacket con entrega USPS/Royal Mail.

---

## 🏆 Ganadores Actuales Validados (Septiembre 2026)

| # | Producto | Nicho | Costo Puesto | Venta | Ganancia Limpia | Margen | Markup |
|:---:|---|---|:---:|:---:|:---:|:---:|:---:|
| **1** | **ProSmile Ultrasonic™** | Salud Dental | $8.20 | $34.99 | **+$25.13** | **71.8%** | 4.27x |
| **2** | **SteamFur Pro™** | Mascotas & Hogar | $7.70 | $29.99 | **+$20.82** | **69.4%** | 3.89x |
| **3** | **SpineRelief Pro™** | Salud & Ergonomía | $14.80 | $54.99 | **+$37.75** | **68.7%** | 3.72x |
| **4** | **AeroForce X3™** | Autos & Táctico | $16.80 | $59.99 | **+$40.55** | **67.6%** | 3.57x |

---

## 💻 Panel Web Interactivo

El proyecto incluye un dashboard web interactivo (`index.html`) con:
- Gráficas de tendencia estilo bolsa de valores en cada producto.
- Filtro desplegable por nichos (Mascotas, Dental, Autos, Ergonomía, Hogar).
- Buscador inteligente en tiempo real.
- Ficha emergente con los **4 Ganchos de Video para TikTok/Reels** (Curiosidad, Dolor, Contrariano y Transformación).

---

## 🛠️ Ejecución Local

Para ejecutar el cazador en cualquier momento:

```powershell
python main.py
```

---
*Desarrollado para el ecosistema Antigravity 2.0 y producción audiovisual en Remotion Modalidad 3.*
