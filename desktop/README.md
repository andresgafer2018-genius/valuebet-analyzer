# ValueBet Analyzer — Desktop App

App de escritorio para Windows y Mac que carga la versión web de ValueBet Analyzer.
Se actualiza automáticamente cuando hay cambios en la web.

## Requisitos
- Node.js v18 o superior
- npm

## Instalación de dependencias
```bash
npm install
```

## Probar localmente (sin compilar)
```bash
npm start
```

## Compilar instalador

### Windows (.exe)
```bash
npm run build:win
```
Genera: `dist/ValueBet Analyzer Setup 1.0.0.exe`

### Mac (.dmg)
```bash
npm run build:mac
```
Genera: `dist/ValueBet Analyzer-1.0.0.dmg`

### Ambos a la vez
```bash
npm run build:all
```

## Íconos necesarios (carpeta assets/)
- `icon.png`  → 512x512 px (base)
- `icon.ico`  → para Windows (multi-resolución)
- `icon.icns` → para Mac

## Actualización de la app
La app siempre muestra la versión más reciente de https://valuebetanalyzer.vercel.app
No hace falta distribuir un nuevo instalador cuando se hace una mejora en la web.

Solo distribuir nuevo instalador cuando:
- Cambia la URL de la app
- Se agregan funciones nativas del sistema operativo
- Se actualiza Electron por seguridad (recomendado cada 6 meses)
