# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: full-journey.spec.ts >> Bomi Pay E2E Full Journey >> Test 1: user can sign up with email, name, password
- Location: e2e\full-journey.spec.ts:4:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('input[name="email"]')

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - img [ref=e6]
      - heading "BomiPay" [level=1] [ref=e8]
      - paragraph [ref=e9]: Operations Intelligence
    - generic [ref=e10]:
      - heading "Create Account" [level=2] [ref=e11]
      - generic [ref=e12]:
        - generic [ref=e13]:
          - generic [ref=e14]: Full Name
          - generic [ref=e15]:
            - img [ref=e16]
            - textbox "Ada Okonkwo" [ref=e19]
        - generic [ref=e20]:
          - generic [ref=e21]: Email
          - generic [ref=e22]:
            - img [ref=e23]
            - textbox "ops@merchant.com" [ref=e26]
        - generic [ref=e27]:
          - generic [ref=e28]: Phone (optional)
          - generic [ref=e29]:
            - img [ref=e30]
            - textbox "+234 800 000 0000" [ref=e32]
        - generic [ref=e33]:
          - generic [ref=e34]: Password
          - generic [ref=e35]:
            - img [ref=e36]
            - textbox "Min. 12 characters" [ref=e39]
            - button [ref=e40]:
              - img [ref=e41]
        - generic [ref=e44]:
          - generic [ref=e45]: Confirm Password
          - generic [ref=e46]:
            - img [ref=e47]
            - textbox "Re-enter your password" [ref=e50]
            - button [ref=e51]:
              - img [ref=e52]
        - button "Create Account" [ref=e55]
      - paragraph [ref=e56]:
        - text: Already have an account?
        - link "Sign in" [ref=e57] [cursor=pointer]:
          - /url: /login
    - paragraph [ref=e58]: BomiPay OpsIntel v1.0 · Internal Use Only
  - button "Open Next.js Dev Tools" [ref=e64] [cursor=pointer]:
    - img [ref=e65]
  - alert [ref=e68]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test'
  2   | 
  3   | test.describe('Bomi Pay E2E Full Journey', () => {
  4   |   test('Test 1: user can sign up with email, name, password', async ({ page }) => {
  5   |     await page.goto('http://localhost:3000/signup')
  6   |     
  7   |     // Fill signup form
> 8   |     await page.fill('input[name="email"]', 'e2e-user@bomipay.ng')
      |                ^ Error: page.fill: Test timeout of 30000ms exceeded.
  9   |     await page.fill('input[name="full_name"]', 'E2E Test User')
  10  |     await page.fill('input[name="password"]', 'TestPass1234!')
  11  |     await page.fill('input[name="confirmPassword"]', 'TestPass1234!')
  12  |     
  13  |     // Click sign up button
  14  |     await page.click('button:has-text("Sign Up")')
  15  |     
  16  |     // Wait for navigation to onboarding
  17  |     await page.waitForURL('**/onboarding', { timeout: 5000 }).catch(() => {
  18  |       // If navigation doesn't happen, check if we're on signup with errors
  19  |       console.log('Navigation to onboarding did not occur')
  20  |     })
  21  |     
  22  |     // Verify we're on onboarding or dashboard
  23  |     const url = page.url()
  24  |     expect(url).toMatch(/\/(onboarding|dashboard)/)
  25  |   })
  26  | 
  27  |   test('Test 2: user can complete merchant onboarding', async ({ page }) => {
  28  |     // Navigate to onboarding
  29  |     await page.goto('http://localhost:3000/onboarding')
  30  |     
  31  |     await page.waitForLoadState('networkidle')
  32  |     
  33  |     // Step 1: Business Profile
  34  |     const companyInput = await page.locator('input[name="company_name"]').first()
  35  |     if (await companyInput.isVisible()) {
  36  |       await companyInput.fill('Test Company')
  37  |       
  38  |       const industrySelect = await page.locator('select[name="industry"]').first()
  39  |       if (await industrySelect.isVisible()) {
  40  |         await industrySelect.selectOption('fintech')
  41  |       }
  42  |       
  43  |       const countryInput = await page.locator('input[name="country"]').first()
  44  |       if (await countryInput.isVisible()) {
  45  |         await countryInput.fill('NG')
  46  |       }
  47  |       
  48  |       const nextButton = await page.locator('button:has-text("Next")').first()
  49  |       if (await nextButton.isVisible()) {
  50  |         await nextButton.click()
  51  |         await page.waitForTimeout(500)
  52  |       }
  53  |     }
  54  |     
  55  |     // Step 2: Connect Provider (skip for now)
  56  |     const skipButton = await page.locator('button:has-text("Skip")').first()
  57  |     if (await skipButton.isVisible()) {
  58  |       await skipButton.click()
  59  |       await page.waitForTimeout(500)
  60  |     }
  61  |     
  62  |     // Step 3: Bank Account
  63  |     const accountNumberInput = await page.locator('input[name="account_number"]').first()
  64  |     if (await accountNumberInput.isVisible()) {
  65  |       await accountNumberInput.fill('1234567890')
  66  |       
  67  |       const bankNameInput = await page.locator('input[name="bank_name"]').first()
  68  |       if (await bankNameInput.isVisible()) {
  69  |         await bankNameInput.fill('Access Bank')
  70  |       }
  71  |       
  72  |       const nextBtn = await page.locator('button:has-text("Next")').first()
  73  |       if (await nextBtn.isVisible()) {
  74  |         await nextBtn.click()
  75  |         await page.waitForTimeout(500)
  76  |       }
  77  |     }
  78  |     
  79  |     // Step 4: Statement Upload (skip)
  80  |     const skipBtn = await page.locator('button:has-text("Skip")').first()
  81  |     if (await skipBtn.isVisible()) {
  82  |       await skipBtn.click()
  83  |       await page.waitForTimeout(500)
  84  |     }
  85  |     
  86  |     // Step 5: Complete
  87  |     const dashboardButton = await page.locator('button:has-text("Go to Dashboard")').first()
  88  |     if (await dashboardButton.isVisible()) {
  89  |       await dashboardButton.click()
  90  |       await page.waitForURL('**/dashboard', { timeout: 5000 }).catch(() => {
  91  |         console.log('Dashboard navigation may have skipped')
  92  |       })
  93  |     }
  94  |     
  95  |     // Just verify we're on a page without errors
  96  |     await page.waitForLoadState('networkidle')
  97  |     expect(page.url()).toBeDefined()
  98  |   })
  99  | 
  100 |   test('Test 3: user can connect payment provider', async ({ page }) => {
  101 |     await page.goto('http://localhost:3000/dashboard')
  102 |     await page.waitForLoadState('networkidle')
  103 |     
  104 |     // Look for connect provider button
  105 |     const connectButton = await page.locator('button:has-text("Connect Provider")').first()
  106 |     if (!(await connectButton.isVisible())) {
  107 |       console.log('Connect Provider button not found, test passes with page load')
  108 |       expect(page.url()).toContain('/dashboard')
```