import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static',      // build va directo a la carpeta static/ de Flask
    emptyOutDir: true,
  },
  base: './',                 // rutas relativas para que funcione desde Flask
})