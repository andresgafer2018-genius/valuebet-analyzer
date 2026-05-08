const { app, BrowserWindow, shell, Menu, Tray, nativeImage } = require('electron')
const path = require('path')

const APP_URL = 'https://valuebetanalyzer.vercel.app'
const APP_NAME = 'ValueBet Analyzer'

let mainWindow
let tray

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: APP_NAME,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false, // no mostrar hasta que cargue
    backgroundColor: '#0f1117', // color de fondo oscuro mientras carga
  })

  // Cargar la app web
  mainWindow.loadURL(APP_URL)

  // Mostrar cuando termine de cargar
  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // Abrir links externos en el browser del sistema, no en la app
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // Título dinámico
  mainWindow.on('page-title-updated', (event) => {
    event.preventDefault()
    mainWindow.setTitle(APP_NAME)
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png'))
  tray = new Tray(icon.resize({ width: 16, height: 16 }))

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Abrir ValueBet Analyzer',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        } else {
          createWindow()
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Actualizar app',
      click: () => {
        if (mainWindow) mainWindow.reload()
      }
    },
    { type: 'separator' },
    {
      label: 'Salir',
      click: () => {
        app.quit()
      }
    }
  ])

  tray.setToolTip(APP_NAME)
  tray.setContextMenu(contextMenu)
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

function createMenu() {
  const template = [
    {
      label: 'Archivo',
      submenu: [
        {
          label: 'Actualizar',
          accelerator: 'F5',
          click: () => { if (mainWindow) mainWindow.reload() }
        },
        { type: 'separator' },
        {
          label: 'Salir',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => { app.quit() }
        }
      ]
    },
    {
      label: 'Ver',
      submenu: [
        {
          label: 'Pantalla completa',
          accelerator: process.platform === 'darwin' ? 'Ctrl+Cmd+F' : 'F11',
          click: () => {
            if (mainWindow) mainWindow.setFullScreen(!mainWindow.isFullScreen())
          }
        },
        {
          label: 'Zoom +',
          accelerator: 'CmdOrCtrl+=',
          click: () => {
            if (mainWindow) {
              const zoom = mainWindow.webContents.getZoomFactor()
              mainWindow.webContents.setZoomFactor(Math.min(zoom + 0.1, 2.0))
            }
          }
        },
        {
          label: 'Zoom -',
          accelerator: 'CmdOrCtrl+-',
          click: () => {
            if (mainWindow) {
              const zoom = mainWindow.webContents.getZoomFactor()
              mainWindow.webContents.setZoomFactor(Math.max(zoom - 0.1, 0.5))
            }
          }
        },
        {
          label: 'Zoom normal',
          accelerator: 'CmdOrCtrl+0',
          click: () => {
            if (mainWindow) mainWindow.webContents.setZoomFactor(1.0)
          }
        }
      ]
    },
    {
      label: 'Ayuda',
      submenu: [
        {
          label: 'Abrir en navegador',
          click: () => { shell.openExternal(APP_URL) }
        },
        { type: 'separator' },
        {
          label: `Versión ${app.getVersion()}`,
          enabled: false
        }
      ]
    }
  ]

  // En Mac agregar menú de aplicación estándar
  if (process.platform === 'darwin') {
    template.unshift({
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    })
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// Evento principal
app.whenReady().then(() => {
  createMenu()
  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// Seguridad: bloquear navegación a URLs externas
app.on('web-contents-created', (event, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl)
    const allowedHosts = ['valuebetanalyzer.vercel.app', 'valuebet-analyzer.fly.dev']
    if (!allowedHosts.includes(parsedUrl.hostname)) {
      event.preventDefault()
      shell.openExternal(navigationUrl)
    }
  })
})
