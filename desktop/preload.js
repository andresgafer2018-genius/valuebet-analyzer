// preload.js - Se ejecuta en contexto aislado antes que la página web
// Expone APIs seguras al renderer si fueran necesarias en el futuro
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  version: process.env.npm_package_version || '1.0.0'
})
