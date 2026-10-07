import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests/browser', timeout: 30000, fullyParallel: false, workers: 1, use: { baseURL: 'http://127.0.0.1:5173', headless: true, channel: 'msedge', viewport: { width: 1440, height: 1000 }, launchOptions: { args: ['--enable-unsafe-swiftshader'] } }, reporter: 'list' });
