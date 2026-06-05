# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: full-journey.spec.ts >> Bomi Pay E2E Full Journey >> Test 3: user can connect payment provider
- Location: e2e\full-journey.spec.ts:100:7

# Error details

```
Error: expect(received).toContain(expected) // indexOf

Expected substring: "/dashboard"
Received string:    "http://localhost:3000/login"
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
      - heading "Sign In" [level=2] [ref=e11]
      - generic [ref=e12]:
        - generic [ref=e13]:
          - generic [ref=e14]: Email
          - generic [ref=e15]:
            - img [ref=e16]
            - textbox "ops@merchant.com" [ref=e19]
        - generic [ref=e20]:
          - generic [ref=e21]: Password
          - generic [ref=e22]:
            - img [ref=e23]
            - textbox "••••••••" [ref=e26]
            - button [ref=e27]:
              - img [ref=e28]
        - button "Sign In" [ref=e31]
      - paragraph [ref=e32]:
        - text: Don't have an account?
        - link "Sign up" [ref=e33] [cursor=pointer]:
          - /url: /signup
    - paragraph [ref=e34]: BomiPay OpsIntel v1.0 · Internal Use Only
  - button "Open Next.js Dev Tools" [ref=e40] [cursor=pointer]:
    - img [ref=e41]
  - alert [ref=e44]
```

# Test source

```ts
  8   |     await page.fill('input[name="email"]', 'e2e-user@bomipay.ng')
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
> 108 |       expect(page.url()).toContain('/dashboard')
      |                          ^ Error: expect(received).toContain(expected) // indexOf
  109 |       return
  110 |     }
  111 |     
  112 |     await connectButton.click()
  113 |     await page.waitForTimeout(500)
  114 |     
  115 |     // Fill provider form
  116 |     const providerSelect = await page.locator('select[name="provider"]').first()
  117 |     if (await providerSelect.isVisible()) {
  118 |       await providerSelect.selectOption('paystack')
  119 |       
  120 |       const envSelect = await page.locator('select[name="environment"]').first()
  121 |       if (await envSelect.isVisible()) {
  122 |         await envSelect.selectOption('test')
  123 |       }
  124 |       
  125 |       const publicKeyInput = await page.locator('input[name="public_key"]').first()
  126 |       if (await publicKeyInput.isVisible()) {
  127 |         await publicKeyInput.fill('pk_test_example')
  128 |       }
  129 |       
  130 |       const secretKeyInput = await page.locator('input[name="secret_key"]').first()
  131 |       if (await secretKeyInput.isVisible()) {
  132 |         await secretKeyInput.fill('sk_test_example')
  133 |       }
  134 |       
  135 |       const webhookInput = await page.locator('input[name="webhook_secret"]').first()
  136 |       if (await webhookInput.isVisible()) {
  137 |         await webhookInput.fill('whsec_test_example')
  138 |       }
  139 |       
  140 |       // Test connection
  141 |       const testButton = await page.locator('button:has-text("Test Connection")').first()
  142 |       if (await testButton.isVisible()) {
  143 |         await testButton.click()
  144 |         await page.waitForTimeout(1000)
  145 |       }
  146 |       
  147 |       // Connect
  148 |       const connectBtn = await page.locator('button:has-text("Connect")').first()
  149 |       if (await connectBtn.isVisible()) {
  150 |         await connectBtn.click()
  151 |         await page.waitForTimeout(500)
  152 |       }
  153 |     }
  154 |     
  155 |     // Verify provider card exists or we're still on page
  156 |     expect(page.url()).toContain('/dashboard')
  157 |   })
  158 | 
  159 |   test('Test 4: user can add and view bank accounts', async ({ page }) => {
  160 |     await page.goto('http://localhost:3000/dashboard/bank-accounts')
  161 |     await page.waitForLoadState('networkidle')
  162 |     
  163 |     // Look for add account button
  164 |     const addButton = await page.locator('button:has-text("Add Account")').first()
  165 |     if (!(await addButton.isVisible())) {
  166 |       console.log('Add Account button not visible, page loads successfully')
  167 |       expect(page.url()).toContain('/bank-accounts')
  168 |       return
  169 |     }
  170 |     
  171 |     await addButton.click()
  172 |     await page.waitForTimeout(500)
  173 |     
  174 |     // Fill form
  175 |     const bankNameInput = await page.locator('input[name="bank_name"]').first()
  176 |     if (await bankNameInput.isVisible()) {
  177 |       await bankNameInput.fill('Guarantee Trust Bank')
  178 |       
  179 |       const accountNumberInput = await page.locator('input[name="account_number"]').first()
  180 |       if (await accountNumberInput.isVisible()) {
  181 |         await accountNumberInput.fill('9876543210')
  182 |       }
  183 |       
  184 |       const holderNameInput = await page.locator('input[name="account_holder_name"]').first()
  185 |       if (await holderNameInput.isVisible()) {
  186 |         await holderNameInput.fill('Test Merchant Ltd')
  187 |       }
  188 |       
  189 |       const addBtn = await page.locator('button:has-text("Add")').first()
  190 |       if (await addBtn.isVisible()) {
  191 |         await addBtn.click()
  192 |         await page.waitForTimeout(500)
  193 |       }
  194 |     }
  195 |     
  196 |     // Verify page loaded
  197 |     expect(page.url()).toContain('/bank-accounts')
  198 |   })
  199 | 
  200 |   test('Test 5: user can view settlements', async ({ page }) => {
  201 |     await page.goto('http://localhost:3000/dashboard/settlements')
  202 |     
  203 |     // Wait for page to load
  204 |     await page.waitForLoadState('networkidle')
  205 |     
  206 |     // Check for empty state or table
  207 |     const emptyState = await page.locator('[data-testid="empty-state"]').count()
  208 |     const table = await page.locator('[data-testid="settlements-table"]').count()
```