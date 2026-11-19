import { createReadStream, readFileSync } from 'node:fs'
import { basename } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const vadAssets: Record<string, { file: string; type: string }> = {
  'vad.worklet.bundle.min.js': { file: 'node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js', type: 'text/javascript' },
  'silero_vad_v5.onnx': { file: 'node_modules/@ricky0123/vad-web/dist/silero_vad_v5.onnx', type: 'application/octet-stream' },
  'ort-wasm-simd-threaded.mjs': { file: 'node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs', type: 'text/javascript' },
  'ort-wasm-simd-threaded.wasm': { file: 'node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm', type: 'application/wasm' },
}

function serveVadAssets(): Plugin {
  return {
    name: 'serve-vad-assets',
    configureServer(server) {
      server.middlewares.use('/vad/', (req, res, next) => {
        const asset = vadAssets[basename((req.url ?? '').split('?')[0])]
        if (!asset) return next()
        res.setHeader('Content-Type', asset.type)
        createReadStream(fileURLToPath(new URL(asset.file, import.meta.url))).pipe(res)
      })
    },
    generateBundle() {
      for (const [name, asset] of Object.entries(vadAssets)) {
        this.emitFile({ type: 'asset', fileName: `vad/${name}`, source: readFileSync(fileURLToPath(new URL(asset.file, import.meta.url))) })
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
