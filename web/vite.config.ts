import { createReadStream, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { basename, dirname, join } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// pnpm은 하위 의존성(onnxruntime-web)을 web/node_modules 바로 아래에 두지 않는다.
// 경로를 고정하지 않고 vad-web이 실제로 쓰는 패키지 위치에서 찾는다. (npm·pnpm 모두 동작)
const requireFromWeb = createRequire(import.meta.url)
const vadEntry = requireFromWeb.resolve('@ricky0123/vad-web')
const vadDist = dirname(vadEntry)
const ortDist = dirname(createRequire(vadEntry).resolve('onnxruntime-web'))

const vadAssets: Record<string, { file: string; type: string }> = {
  'vad.worklet.bundle.min.js': { file: join(vadDist, 'vad.worklet.bundle.min.js'), type: 'text/javascript' },
  'silero_vad_v5.onnx': { file: join(vadDist, 'silero_vad_v5.onnx'), type: 'application/octet-stream' },
  'ort-wasm-simd-threaded.mjs': { file: join(ortDist, 'ort-wasm-simd-threaded.mjs'), type: 'text/javascript' },
  'ort-wasm-simd-threaded.wasm': { file: join(ortDist, 'ort-wasm-simd-threaded.wasm'), type: 'application/wasm' },
}

function serveVadAssets(): Plugin {
  return {
    name: 'serve-vad-assets',
    configureServer(server) {
      server.middlewares.use('/vad/', (req, res, next) => {
        const asset = vadAssets[basename((req.url ?? '').split('?')[0])]
        if (!asset) return next()
        // 파일을 못 찾아도 개발 서버가 죽지 않고 404만 돌려준다.
        createReadStream(asset.file)
          .on('error', () => { if (!res.headersSent) res.statusCode = 404; res.end() })
          .once('open', () => res.setHeader('Content-Type', asset.type))
          .pipe(res)
      })
    },
    generateBundle() {
      for (const [name, asset] of Object.entries(vadAssets)) {
        this.emitFile({ type: 'asset', fileName: `vad/${name}`, source: readFileSync(asset.file) })
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  server: { host: '0.0.0.0', port: 5173, strictPort: true, allowedHosts: true },
  plugins: [react(), tailwindcss(), serveVadAssets()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
