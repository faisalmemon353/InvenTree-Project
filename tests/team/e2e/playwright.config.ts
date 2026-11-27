import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'playwright-results.json' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    channel: 'msedge',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: '..\\..\\..\\.venv\\Scripts\\python.exe sqe_web_portal_server.py 8765',
    url: 'http://127.0.0.1:8765/sqe/api/state',
    reuseExistingServer: true,
    timeout: 60000,
  },
});
