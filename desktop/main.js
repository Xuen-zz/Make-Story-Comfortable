const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron')
const path = require('path')
const net = require('net')
const http = require('http')
const fs = require('fs')
const { spawn, execSync } = require('child_process')

let autoUpdater = null
try {
  ({ autoUpdater } = require('electron-updater'))
} catch {
  autoUpdater = null
}

let mainWindow = null
let backendProc = null
let backendPort = 7860

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.unref()
    srv.on('error', reject)
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address()
      srv.close(() => resolve(port))
    })
  })
}

function waitForBackendHealth(port, timeoutMs = 45000) {
  const started = Date.now()
  return new Promise((resolve, reject) => {
    const probe = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        res.resume()
        if (res.statusCode === 200) {
          resolve()
          return
        }
        retry()
      })
      req.on('error', retry)
      req.setTimeout(1500, () => {
        req.destroy()
      })
    }
    const retry = () => {
      if (Date.now() - started >= timeoutMs) {
        reject(new Error(`后端引擎在 ${Math.round(timeoutMs / 1000)} 秒内未响应`))
        return
      }
      setTimeout(probe, 300)
    }
    probe()
  })
}

function startBackend(port) {
  const userDataDir = app.getPath('userData')
  fs.mkdirSync(userDataDir, { recursive: true })

  let cmd = ''
  let args = []
  let cwd = userDataDir

  if (app.isPackaged) {
    const exePath = path.join(process.resourcesPath, 'backend', 'novelflow-engine.exe')
    cmd = exePath
    args = ['--host', '127.0.0.1', '--port', String(port), '--data-dir', userDataDir]
    cwd = path.dirname(exePath)
  } else {
    const repoRoot = path.resolve(__dirname, '..')
    cmd = process.env.NOVELFLOW_PYTHON || 'python'
    args = [
      path.join(repoRoot, 'api_server.py'),
      '--host',
      '127.0.0.1',
      '--port',
      String(port),
      '--data-dir',
      userDataDir,
    ]
    cwd = repoRoot
  }

  const logFile = path.join(userDataDir, 'backend_spawn.log')
  const outStream = fs.createWriteStream(logFile, { flags: 'a' })

  backendProc = spawn(cmd, args, {
    cwd,
    env: {
      ...process.env,
      NOVELFLOW_DATA_DIR: userDataDir,
      PYTHONIOENCODING: 'utf-8',
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  if (backendProc.stdout) backendProc.stdout.pipe(outStream)
  if (backendProc.stderr) backendProc.stderr.pipe(outStream)

  backendProc.on('exit', (code) => {
    outStream.write(`\n[NovelFlow Electron] backend exited with code ${code}\n`)
    backendProc = null
  })
}

function stopBackend() {
  if (!backendProc || !backendProc.pid) return
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /pid ${backendProc.pid} /T /F`, { stdio: 'ignore' })
    } else {
      backendProc.kill('SIGTERM')
    }
  } catch {
    // 忽略退出竞态错误
  } finally {
    backendProc = null
  }
}

function sendUpdateStatus(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('novelflow:update-status', payload)
  }
}

let isManualUpdateCheck = false
let downloadAttemptCount = 0
const MAX_DOWNLOAD_ATTEMPTS = 2

const OFFICIAL_FEED = {
  provider: 'github',
  owner: 'Xuen-zz',
  repo: 'Make-Story-Comfortable',
  releaseType: 'release',
}

const ACCELERATED_MIRROR_FEED = {
  provider: 'generic',
  url: 'https://ghproxy.net/https://github.com/Xuen-zz/Make-Story-Comfortable/releases/latest/download/',
  channel: 'latest',
}

function applyFeedURL(useMirror = false) {
  if (!autoUpdater) return
  try {
    if (useMirror) {
      autoUpdater.setFeedURL(ACCELERATED_MIRROR_FEED)
    } else {
      autoUpdater.setFeedURL(OFFICIAL_FEED)
    }
  } catch (err) {
    console.error('[NovelFlow AutoUpdater] setFeedURL error:', err)
  }
}

function setupAutoUpdater() {
  if (!autoUpdater || !app.isPackaged) return
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false // 禁止退出静默安装，防止后台因进程锁死默默失败
  autoUpdater.disableDifferentialDownload = true // 核心防死循环补丁：禁用易产生校验失败的 blockmap 差分下载

  // 默认启用国内高速镜像加速源
  applyFeedURL(true)

  const logUpdate = (msg) => {
    try {
      const logFile = path.join(app.getPath('userData'), 'app.log')
      fs.appendFileSync(logFile, `${new Date().toISOString()} - [Updater] - ${msg}\n`)
    } catch {}
  }

  autoUpdater.on('checking-for-update', () => {
    logUpdate('Checking for update from GitHub Releases (Accelerated Mirror)...')
    if (isManualUpdateCheck) {
      sendUpdateStatus({ status: 'checking', message: '正在连接高速镜像源检查版本更新…' })
    }
  })
  autoUpdater.on('update-available', (info) => {
    logUpdate(`Update available: v${info.version}`)
    isManualUpdateCheck = false
    downloadAttemptCount = 0
    sendUpdateStatus({
      status: 'available',
      version: info.version,
      message: `发现新版本 v${info.version}，可立即下载升级`,
    })
  })
  autoUpdater.on('update-not-available', (info) => {
    logUpdate(`App is up to date: v${app.getVersion()}`)
    if (isManualUpdateCheck) {
      sendUpdateStatus({
        status: 'up-to-date',
        message: `当前已是最新版本 v${app.getVersion()}`,
      })
      isManualUpdateCheck = false
    }
  })
  autoUpdater.on('download-progress', (progress) => {
    sendUpdateStatus({
      status: 'downloading',
      percent: progress.percent,
      message: `正在通过高速镜像下载更新包…`,
    })
  })
  autoUpdater.on('update-downloaded', (info) => {
    logUpdate(`Update downloaded: v${info.version}`)
    downloadAttemptCount = 0
    sendUpdateStatus({
      status: 'downloaded',
      version: info.version,
      message: `新版本 v${info.version} 下载校验完成，可立即重启安装`,
    })
  })
  autoUpdater.on('error', (err) => {
    const errorMsg = err?.message || String(err)
    logUpdate(`Updater error: ${errorMsg}`)
    if (isManualUpdateCheck || downloadAttemptCount > 0) {
      sendUpdateStatus({
        status: 'error',
        message: `更新服务提示: ${errorMsg}`,
      })
      isManualUpdateCheck = false
    }
  })
}

function createWindow(port) {
  Menu.setApplicationMenu(null)
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: '#0c0d10',
    title: 'NovelFlow Studio',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.loadURL(`http://127.0.0.1:${port}/`)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })
}

function registerIpc() {
  ipcMain.handle('novelflow:get-version', () => app.getVersion())
  ipcMain.handle('novelflow:select-folder', async () => {
    if (!mainWindow) return null
    const res = await dialog.showOpenDialog(mainWindow, {
      title: '选择小说文件与档案存储文件夹',
      properties: ['openDirectory', 'createDirectory'],
    })
    return res.canceled ? null : res.filePaths[0] || null
  })
  ipcMain.handle('novelflow:open-external', (_ev, url) => {
    if (typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
      return shell.openExternal(url)
    }
    return undefined
  })
  ipcMain.handle('novelflow:check-for-updates', async () => {
    isManualUpdateCheck = true
    if (!autoUpdater || !app.isPackaged) {
      const payload = {
        status: 'up-to-date',
        version: app.getVersion(),
        message: `当前版本 v${app.getVersion()}（开发模式；打包安装版支持一键自动更新）`,
      }
      sendUpdateStatus(payload)
      isManualUpdateCheck = false
      return payload
    }
    // 优先通过国内高速镜像源检查
    try {
      applyFeedURL(true)
      const result = await autoUpdater.checkForUpdates()
      const nextVer = result?.updateInfo?.version
      return {
        status: nextVer && nextVer !== app.getVersion() ? 'available' : 'up-to-date',
        version: nextVer || app.getVersion(),
      }
    } catch (mirrorErr) {
      // 镜像源若超时或不可用，自动平滑回退到官方源
      try {
        applyFeedURL(false)
        const result = await autoUpdater.checkForUpdates()
        const nextVer = result?.updateInfo?.version
        return {
          status: nextVer && nextVer !== app.getVersion() ? 'available' : 'up-to-date',
          version: nextVer || app.getVersion(),
        }
      } catch (officialErr) {
        isManualUpdateCheck = false
        const errorMsg = officialErr?.message || String(officialErr)
        sendUpdateStatus({
          status: 'error',
          message: `检查更新失败: ${errorMsg}`,
        })
        return {
          status: 'error',
          message: errorMsg,
        }
      }
    }
  })
  ipcMain.handle('novelflow:download-update', async () => {
    if (autoUpdater && app.isPackaged) {
      if (downloadAttemptCount >= MAX_DOWNLOAD_ATTEMPTS) {
        sendUpdateStatus({
          status: 'error',
          message: '自动下载多次未完成，建议使用“浏览器极速下载”获取安装包覆盖升级',
        })
        return
      }
      downloadAttemptCount += 1
      try {
        await autoUpdater.downloadUpdate()
      } catch (err) {
        const errorMsg = err?.message || String(err)
        sendUpdateStatus({
          status: 'error',
          message: `下载中断: ${errorMsg}，可使用浏览器极速下载`,
        })
      }
    }
  })
  ipcMain.handle('novelflow:quit-and-install', async () => {
    if (autoUpdater && app.isPackaged) {
      sendUpdateStatus({
        status: 'installing',
        message: '正在终止本地引擎并启动安装程序向导…',
      })
      stopBackend()
      // 等待 800ms 保证 Windows 完全释放可执行文件句柄
      await new Promise((r) => setTimeout(r, 800))
      // isSilent: false 前台显示安装向导，isForceRunAfter: true 安装完成后重启
      autoUpdater.quitAndInstall(false, true)
    }
  })
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  app.whenReady().then(async () => {
    registerIpc()
    setupAutoUpdater()
    try {
      backendPort = await findFreePort()
      startBackend(backendPort)
      await waitForBackendHealth(backendPort, 45000)
      createWindow(backendPort)
      if (autoUpdater && app.isPackaged) {
        // 启动后 15 秒静默检查一次
        setTimeout(() => {
          isManualUpdateCheck = false
          autoUpdater.checkForUpdates().catch(() => {})
        }, 15000)

        // 后台每 3 小时静默轮询一次，仅在发现新版本时提醒用户
        setInterval(() => {
          isManualUpdateCheck = false
          autoUpdater.checkForUpdates().catch(() => {})
        }, 3 * 60 * 60 * 1000)
      }
    } catch (err) {
      dialog.showErrorBox(
        'NovelFlow Studio 启动失败',
        `本地引擎未能就绪：\n${err?.message || String(err)}\n\n请查看日志目录：${app.getPath('userData')}`,
      )
      stopBackend()
      app.quit()
    }
  })

  app.on('before-quit', () => {
    stopBackend()
  })

  app.on('window-all-closed', () => {
    stopBackend()
    if (process.platform !== 'darwin') app.quit()
  })
}
