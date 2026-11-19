export interface UpdateStatusPayload {
  status: string
  version?: string
  percent?: number
  message: string
}

export interface NovelFlowDesktopBridge {
  isDesktop: boolean
  platform: string
  getVersion: () => Promise<string>
  selectFolder: () => Promise<string | null>
  checkForUpdates: () => Promise<{ status: string; version?: string; message?: string }>
  downloadUpdate: () => Promise<void>
  quitAndInstall: () => Promise<void>
  openExternal: (url: string) => Promise<void>
  onUpdateStatus?: (cb: (payload: UpdateStatusPayload) => void) => () => void
}

declare global {
  interface Window {
    novelflowDesktop?: NovelFlowDesktopBridge
  }
}

export {}
