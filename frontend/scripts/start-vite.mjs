import { createServer } from 'vite'

function readArg(name, fallback) {
  const index = process.argv.indexOf(name)
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback
  }
  return process.argv[index + 1]
}

const host = readArg('--host', '0.0.0.0')
const port = Number(readArg('--port', '5173'))

const server = await createServer({
  server: {
    host,
    port,
    strictPort: true,
  },
})

await server.listen()
server.printUrls()

async function shutdown() {
  await server.close()
  process.exit(0)
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)

setInterval(() => {}, 2147483647)
