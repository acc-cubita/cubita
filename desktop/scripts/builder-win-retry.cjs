#!/usr/bin/env node
// Windows Defender may briefly lock the freshly extracted Electron executable.
// Retry only electron-builder's staging-directory rename, not arbitrary file moves.
const fs = require('node:fs/promises')
const path = require('node:path')

const rename = fs.rename.bind(fs)
fs.rename = async (from, to) => {
  if (process.platform !== 'win32' || path.basename(from) !== 'win-unpacked.tmp' || path.basename(to) !== 'win-unpacked') {
    return rename(from, to)
  }
  for (let attempt = 0; ; attempt++) {
    try {
      return await rename(from, to)
    } catch (error) {
      if (error.code !== 'EPERM') throw error
      if (attempt >= 10) {
        // The extracted executable can stay locked until this process exits.
        // A same-volume copy still gives builder the expected staging directory.
        await fs.cp(from, to, { recursive: true })
        return
      }
      await new Promise((resolve) => setTimeout(resolve, 500))
    }
  }
}

require('electron-builder/cli')
