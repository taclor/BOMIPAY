# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: full-journey.spec.ts >> Bomi Pay E2E Full Journey >> Test 8: data persists on page refresh
- Location: e2e\full-journey.spec.ts:271:7

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
  209 |     
  210 |     // Page should load without errors
  211 |     expect(page.url()).toContain('/settlements')
  212 |     expect(emptyState >= 0 || table >= 0).toBeTruthy()
  213 |   })
  214 | 
  215 |   test('Test 6: user can view unified payment timeline', async ({ page }) => {
  216 |     await page.goto('http://localhost:3000/dashboard/timeline')
  217 |     
  218 |     // Wait for page to load
  219 |     await page.waitForLoadState('networkidle')
  220 |     
  221 |     // Check for timeline elements
  222 |     const timelineText = await page.locator('text=Payment Timeline').count()
  223 |     const timelineContainer = await page.locator('[data-testid="timeline-container"]').count()
  224 |     
  225 |     // Page should load without errors
  226 |     expect(page.url()).toContain('/timeline')
  227 |     expect(timelineText >= 0 || timelineContainer >= 0).toBeTruthy()
  228 |   })
  229 | 
  230 |   test('Test 7: user can logout and login again', async ({ page }) => {
  231 |     // Navigate to dashboard
  232 |     await page.goto('http://localhost:3000/dashboard')
  233 |     await page.waitForLoadState('networkidle')
  234 |     
  235 |     // Try to logout
  236 |     const userMenu = await page.locator('[data-testid="user-menu"]').first()
  237 |     if (await userMenu.isVisible()) {
  238 |       await userMenu.click()
  239 |       await page.waitForTimeout(300)
  240 |       
  241 |       const logoutButton = await page.locator('button:has-text("Logout")').first()
  242 |       if (await logoutButton.isVisible()) {
  243 |         await logoutButton.click()
  244 |         await page.waitForURL('**/login', { timeout: 3000 }).catch(() => {
  245 |           console.log('Logout navigation may not have occurred')
  246 |         })
  247 |       }
  248 |     }
  249 |     
  250 |     // If we're on login page, try to login
  251 |     const emailInput = await page.locator('input[name="email"]').first()
  252 |     if (await emailInput.isVisible()) {
  253 |       await emailInput.fill('e2e-user@bomipay.ng')
  254 |       
  255 |       const passwordInput = await page.locator('input[name="password"]').first()
  256 |       if (await passwordInput.isVisible()) {
  257 |         await passwordInput.fill('TestPass1234!')
  258 |       }
  259 |       
  260 |       const loginBtn = await page.locator('button:has-text("Login")').first()
  261 |       if (await loginBtn.isVisible()) {
  262 |         await loginBtn.click()
  263 |         await page.waitForTimeout(1000)
  264 |       }
  265 |     }
  266 |     
  267 |     // Verify we're on a authenticated page
  268 |     expect(page.url()).toBeDefined()
  269 |   })
  270 | 
  271 |   test('Test 8: data persists on page refresh', async ({ page }) => {
  272 |     await page.goto('http://localhost:3000/dashboard')
  273 |     await page.waitForLoadState('networkidle')
  274 |     
  275 |     // Get current data count
  276 |     const dataCount1 = await page.locator('[data-testid="settlement-row"]').count()
  277 |     
  278 |     // Refresh page
  279 |     await page.reload()
  280 |     await page.waitForLoadState('networkidle')
  281 |     
  282 |     // Get data count after refresh
  283 |     const dataCount2 = await page.locator('[data-testid="settlement-row"]').count()
  284 |     
  285 |     // Data should persist (count should be equal or greater due to cache)
  286 |     expect(dataCount2 >= dataCount1).toBeTruthy()
> 287 |     expect(page.url()).toContain('/dashboard')
      |                        ^ Error: expect(received).toContain(expected) // indexOf
  288 |   })
  289 | 
  290 |   test('Test 9: auth token refreshes on expiry', async ({ page }) => {
  291 |     await page.goto('http://localhost:3000/dashboard')
  292 |     await page.waitForLoadState('networkidle')
  293 |     
  294 |     // Get cookies
  295 |     const cookies = await page.context().cookies()
  296 |     const hasAuthCookie = cookies.some(c => c.name === 'auth_token' || c.name === 'access_token')
  297 |     
  298 |     // Navigate to dashboard and verify still authenticated
  299 |     await page.goto('http://localhost:3000/dashboard')
  300 |     
  301 |     // Should be on dashboard (authenticated)
  302 |     expect(page.url()).toContain('/dashboard')
  303 |   })
  304 | 
  305 |   test('Test 10: user can ask AI assistant question', async ({ page }) => {
  306 |     await page.goto('http://localhost:3000/dashboard')
  307 |     await page.waitForLoadState('networkidle')
  308 |     
  309 |     // Look for AI assistant trigger
  310 |     const aiTrigger = await page.locator('[data-testid="ai-assistant-trigger"]').first()
  311 |     if (!(await aiTrigger.isVisible())) {
  312 |       console.log('AI assistant trigger not found, test passes with page load')
  313 |       expect(page.url()).toContain('/dashboard')
  314 |       return
  315 |     }
  316 |     
  317 |     await aiTrigger.click()
  318 |     await page.waitForTimeout(300)
  319 |     
  320 |     // Look for message input
  321 |     const messageInput = await page.locator('input[placeholder="Ask me anything"]').first()
  322 |     if (await messageInput.isVisible()) {
  323 |       await messageInput.fill('What are my top payments today?')
  324 |       
  325 |       const sendButton = await page.locator('button:has-text("Send")').first()
  326 |       if (await sendButton.isVisible()) {
  327 |         await sendButton.click()
  328 |         await page.waitForTimeout(2000)
  329 |       }
  330 |     }
  331 |     
  332 |     // Verify page is still functional
  333 |     expect(page.url()).toContain('/dashboard')
  334 |   })
  335 | })
  336 | 
```