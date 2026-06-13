const http = require('http');

const PORT = Number(process.env.PORT || 3000);

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' });
  res.end('ReylAI independent container server is running.\n');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`ReylAI container server listening on port ${PORT}`);
});
