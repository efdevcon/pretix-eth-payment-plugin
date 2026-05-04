import * as esbuild from 'esbuild'
import * as fs from 'node:fs'
import * as path from 'node:path'

const watch = process.argv.includes('--watch')

const options = {
  entryPoints: ['src/index.tsx'],
  bundle: true,
  outfile: 'dist/bundle.js',
  format: 'esm',
  target: 'es2020',
  minify: !watch,
  sourcemap: true,
  loader: {
    '.svg': 'text',
  },
  external: [
    '@metamask/connect-evm', // lazy dynamic import in wagmi connectors
  ],
  define: {
    'process.env.NODE_ENV': watch ? '"development"' : '"production"',
  },
  logLevel: 'info',
}

function copyStyles() {
  if (fs.existsSync('src/styles.css')) {
    fs.mkdirSync('dist', { recursive: true })
    fs.copyFileSync('src/styles.css', path.join('dist', 'styles.css'))
  }
}

if (watch) {
  const ctx = await esbuild.context(options)
  await ctx.watch()
  console.log('Watching src/ for changes...')
  // Copy styles on initial run; for watch mode, a separate fs.watch could be added later
  copyStyles()
} else {
  await esbuild.build(options)
  copyStyles()
  console.log('Build complete: dist/bundle.js')
}
