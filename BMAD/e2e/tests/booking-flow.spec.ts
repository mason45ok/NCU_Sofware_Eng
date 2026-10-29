import { expect, test } from '@playwright/test';

// 主流程：登入 → 搜尋 → 預約 → 付款失敗 → 重付成功 → 取消。尚未執行（需要完整系統啟動）。
test('會員從搜尋到預約、付款、取消', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('user1@judian.local');
  await page.getByLabel('密碼').fill('Passw0rd!');
  await page.getByRole('button', { name: '登入' }).click();

  await page.goto('/spaces');
  await page.getByText('201 會議室').first().click();
  await page.getByRole('button', { name: /可預約/ }).first().click();
  await expect(page.getByText(/NT\$/)).toBeVisible();
  await page.getByRole('button', { name: '預約' }).click();
  await page.getByRole('button', { name: '送出預約並前往付款' }).click();

  await page.getByLabel('卡號').fill('4000 0000 0000 0002');
  await page.getByRole('button', { name: /確認付款/ }).click();
  await expect(page.getByText('卡片遭拒')).toBeVisible();

  await page.getByLabel('卡號').fill('4242 4242 4242 4242');
  await page.getByRole('button', { name: /確認付款/ }).click();
  await expect(page.getByText('房間密碼')).toBeVisible();

  await page.getByRole('button', { name: '取消訂單' }).click();
  await expect(page.getByText(/將退款/)).toBeVisible();
  await page.getByRole('button', { name: '確認取消' }).click();
  await expect(page.getByText('已取消').first()).toBeVisible();
});
