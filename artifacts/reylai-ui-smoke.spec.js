const { test } = require('@playwright/test');
test('mock account menu panels', async ({ page }) => {
  await page.setViewportSize({ width: 1365, height: 768 });
  await page.goto('https://ai.reyliar.xyz/?v=9c21388', { waitUntil: 'networkidle' });
  await page.evaluate(() => {
    _accountUser = {
      id: 'mock-admin',
      display_name: 'Alkim Gencali',
      email: 'mynamesreyli@gmail.com',
      role: 'admin',
      is_admin: true,
      email_verified: false,
      roles: [{ label: 'Admin', icon: 'shield' }, { label: 'Staff', icon: 'sparkles' }],
      avatar_data_url: ''
    };
    hideAccountAuth();
    document.body.classList.add('app-ready');
    document.body.classList.remove('account-auth-visible');
    updateAccountUI();
    toggleAccountMenu();
  });
  await page.screenshot({ path: 'artifacts/profile-menu.png' });
  await page.evaluate(() => openProfileSettings());
  await page.screenshot({ path: 'artifacts/profile-settings.png' });
});
