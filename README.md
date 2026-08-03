# 📊 Monitor de Precios — iPhone 16e Chile

Dashboard profesional que monitorea los precios del iPhone 16e 128GB en tiendas chilenas y te avisa por WhatsApp cuando bajan.

![Dashboard](https://img.shields.io/badge/Status-Live-10b981?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Netlify](https://img.shields.io/badge/Netlify-Deployed-00c7b7?style=for-the-badge&logo=netlify&logoColor=white)

## 🏪 Tiendas Monitoreadas

| Tienda | Método |
|--------|--------|
| Falabella | JSON-LD (schema.org) |
| MacOnline | JSON-LD (schema.org) |

## 🚀 ¿Cómo funciona?

1. **GitHub Actions** ejecuta el scraper Python cada hora
2. El scraper extrae precios de las tiendas usando datos estructurados (JSON-LD)
3. Si un precio baja → **WhatsApp** te avisa al instante vía CallMeBot
4. Los datos se guardan en `data/precios.json`
5. **Netlify** despliega automáticamente el dashboard web con cada actualización

## 📱 Alertas WhatsApp

Las alertas se envían mediante [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/):
- 📉 **Baja de precio** — con monto y porcentaje de ahorro
- 📈 **Suba de precio** — para que estés informado
- ⚠️ **Producto agotado** — si deja de estar disponible

## 🛠️ Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/precios.git
cd precios
```

### 2. Configurar secretos en GitHub

Ve a **Settings → Secrets and variables → Actions** y agrega:

| Secret | Valor |
|--------|-------|
| `WHATSAPP_PHONE` | Tu número con código de país (ej: `56912345678`) |
| `WHATSAPP_APIKEY` | Tu API key de CallMeBot |

### 3. Conectar con Netlify

1. Crea una cuenta en [netlify.com](https://netlify.com)
2. Click en **"Add new site" → "Import an existing project"**
3. Conecta tu repositorio de GitHub
4. Publish directory: `.` (raíz)
5. ¡Listo! Se despliega automáticamente

### 4. Ejecución local (opcional)

```bash
pip install -r requirements.txt
# Crear archivo .env con tus credenciales
echo "WHATSAPP_PHONE=56912345678" > .env
echo "WHATSAPP_APIKEY=tu_apikey" >> .env
python monitor_precio_ml.py
```

## 📁 Estructura del Proyecto

```
precios/
├── index.html              # Dashboard web
├── css/style.css            # Estilos premium (dark mode, glassmorphism)
├── js/app.js                # Lógica del dashboard (Chart.js)
├── data/precios.json        # Datos de precios (auto-generado)
├── monitor_precio_ml.py     # Scraper de precios + alertas WhatsApp
├── requirements.txt         # Dependencias Python
├── netlify.toml             # Configuración de Netlify
├── .github/workflows/
│   └── monitor.yml          # GitHub Actions (cron cada hora)
└── .gitignore
```

## 📄 Licencia

MIT — Uso personal.
