import { defineConfig } from '@playwright/test';

// 系統需先以 docker compose 啟動並執行 flask db upgrade、flask seed
export default defineConfig({
  testDir: './tests',
  use: { baseURL: 'http://localhost:8080', locale: 'zh-TW', timezoneId: 'Asia/Taipei' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { viewport: { width: 360, height: 740 } } },
  ],
});
