import { defineConfig } from 'vite';
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const packageInfo = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as { version: string };
const hash = createHash('sha256');

function addFile(path: string, name: string) {
  hash.update(name);
  const contents = readFileSync(path);
  hash.update(/\.(?:ts|tsx|css|json|svg|html|py|txt|yaml|yml|conf)$/.test(path)
    ? contents.toString('utf8').replaceAll('\r\n', '\n')
    : contents);
}

function addFiles(directory: string, prefix: string) {
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0)) {
    if (entry.name.startsWith('.') || entry.name === '__pycache__' || entry.name === 'node_modules') continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) addFiles(path, `${prefix}/${entry.name}`);
    else if (entry.isFile() && !/\.(?:pyc|sqlite3|log)$/.test(entry.name)) addFile(path, `${prefix}/${entry.name}`);
  }
}

addFile(join(root, 'package.json'), 'frontend/package.json');
addFile(join(root, 'vite.config.ts'), 'frontend/vite.config.ts');
addFiles(join(root, 'src'), 'frontend/src');
addFiles(existsSync(join(root, 'backend-version')) ? join(root, 'backend-version') : join(root, '..', 'backend'), 'backend');
addFiles(existsSync(join(root, 'infra-version')) ? join(root, 'infra-version') : join(root, '..', 'infra'), 'infra');
addFile(existsSync(join(root, 'compose-version.yaml')) ? join(root, 'compose-version.yaml') : join(root, '..', 'compose.yaml'), 'compose.yaml');

const buildInfo = {
  version: packageInfo.version,
  revision: hash.digest('hex').slice(0, 8),
  builtAt: new Date().toISOString(),
};

export default defineConfig({
  define: { __SME_BUILD_INFO__: JSON.stringify(buildInfo) },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
});
