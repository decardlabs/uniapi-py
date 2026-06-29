/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: '../webui',
    // This is now correct; source maps should only be generated for development mode, not production
    sourcemap: mode === 'development',
    // Increase chunk size warning limit to reduce noise for legitimate large chunks
    chunkSizeWarningLimit: 500, // Reduced from 1000 to encourage better chunking
    // Enable advanced minification and optimization
    minify: 'esbuild',
    target: 'esnext',
    // Additional build optimizations
    cssCodeSplit: true, // Enable CSS code splitting
    assetsInlineLimit: 4096, // Inline assets smaller than 4KB
    reportCompressedSize: true, // Report compressed sizes in build output
    // Enable advanced esbuild optimizations
    esbuild: {
      legalComments: 'none',
      treeShaking: true,
      minifyIdentifiers: true,
      minifySyntax: true,
      minifyWhitespace: true,
    },
    rollupOptions: {
      // Improve tree shaking and dead code elimination
      treeshake: {
        preset: 'recommended',
        moduleSideEffects: 'no-external',
        propertyReadSideEffects: false,
        tryCatchDeoptimization: false,
      },
      // Optimize external dependencies
      external: [],
      output: {
        // Use both name and hash for chunk file names to aid debugging and cache busting
        chunkFileNames: '[name].[hash].js',
        manualChunks: {
          // Core - safe to split (no inter-chunk import issues)
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],

          // Markdown is very large - safe to split independently
          'markdown': ['react-markdown', 'marked', 'remark-gfm', 'remark-math', 'remark-emoji',
                       'rehype-highlight', 'rehype-katex', 'katex', 'rehype-sanitize'],

          // Charts
          charts: ['recharts'],
        },
      },
    },
  },
  server: {
    port: 3001,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/v1': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
}));
