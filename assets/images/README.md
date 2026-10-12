# Fotos de producto (slots del panel)

El panel (`index.html`) deja un **slot vacío** en cada tarjeta mientras un producto no tenga foto.
Para llenarlo no hay que tocar HTML ni CSS:

1. Guarda la foto aquí (WebP recomendado, mínimo 800×450 px; el slot recorta con `object-fit: cover`).
2. En `data/user_products.json`, agrega a ese producto: `"image_url": "assets/images/<archivo>.webp"`
   (o una URL `https://` de Shopify/CDN).
3. Pulsa **Actualizar** en el panel (o `python main.py`): la ruta viaja a `data/dashboard_data.js`.

| id (`user_products.json`) | Archivo esperado                   |
|---------------------------|------------------------------------|
| `steamfur-pro`            | `assets/images/steamfur.webp`      |
| `prosmile-ultrasonic`     | `assets/images/prosmile.webp`      |
| `spinerelief-pro`         | `assets/images/spinerelief.webp`   |
| `aeroforce-x3`            | `assets/images/aeroforce.webp`     |

Si la ruta no existe o la imagen falla al cargar, el panel vuelve a mostrar el slot vacío (nunca una foto de relleno).
Rutas con `..`, absolutas (`/…`) o esquemas como `javascript:`/`data:` se rechazan y salen como alerta roja.
