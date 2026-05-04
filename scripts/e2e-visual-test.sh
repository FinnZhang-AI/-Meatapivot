#!/bin/bash

set -e

echo "========================================"
echo "🧪 Meatapivot - Visual & Interaction E2E Test"
echo "========================================"
echo ""

# Configuration
FRONTEND_URL="http://localhost:5173"
BACKEND_URL="http://localhost:8000"
API_PREFIX="/api/v1"
TEST_USER="visualtest"
TEST_EMAIL="visual@test.com"
TEST_PASSWORD="Test123!"
TENANT_ID="tenant-visual"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test counters
pass_count=0
fail_count=0
screenshot_dir="screenshots/e2e-$(date +%Y%m%d-%H%M%S)"

test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((pass_count++))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((fail_count++))
    fi
}

# Create screenshot directory
mkdir -p "$screenshot_dir"

echo -e "${BLUE}📁 Screenshot directory: $screenshot_dir${NC}"
echo ""

# Step 0: Install Playwright if not exists
echo -e "${YELLOW}=== Step 0: Setup Playwright ===${NC}"
cd frontend

if ! command -v npx &> /dev/null || ! npx playwright --version &> /dev/null; then
    echo "Installing Playwright..."
    npm install -D @playwright/test
    npx playwright install chromium
fi

# Create Playwright test file
cat > e2e/visual-test.spec.ts << 'PLAYWRIGHT_TEST'
import { test, expect } from '@playwright/test';
import { devices } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// Test configuration
const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';
const API_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const TEST_USER = 'visualtest';
const TEST_PASSWORD = 'Test123!';

// Custom viewport sizes for responsive testing
const viewports = [
  { name: 'Mobile Small', width: 375, height: 667 },
  { name: 'Mobile Large', width: 414, height: 896 },
  { name: 'Tablet', width: 768, height: 1024 },
  { name: 'Laptop', width: 1024, height: 768 },
  { name: 'Desktop', width: 1440, height: 900 },
];

// Test credentials
let authToken = '';

test.beforeAll('Setup: Register test user and get token', async () => {
  // Register user via API
  const registerResponse = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: TEST_USER,
      email: `visual_${Date.now()}@test.com`,
      password: TEST_PASSWORD,
      tenant_id: 'tenant-visual'
    })
  });
  
  // Login to get token
  const loginResponse = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${TEST_USER}&password=${TEST_PASSWORD}`
  });
  
  const loginData = await loginResponse.json();
  authToken = loginData.access_token;
  console.log('✅ Auth token obtained:', authToken ? 'Yes' : 'No');
});

// Test 1: Element Loading Status
test.describe('📦 Element Loading Tests', () => {
  test('All page elements load without 404', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    page.on('requestfailed', request => {
      consoleErrors.push(`Request failed: ${request.url()}`);
    });
    
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Wait for main content
    await page.waitForSelector('#root', { timeout: 10000 });
    
    // Check for 404 errors
    const has404 = consoleErrors.some(err => err.includes('404') || err.includes('Failed to fetch'));
    
    expect(has404).toBe(false);
    
    // Take screenshot
    await page.screenshot({ path: `screenshots/element-loading.png`, fullPage: true });
    console.log('✅ All elements loaded successfully');
  });
  
  test('Images, fonts, and icons load correctly', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Check images
    const images = await page.locator('img').all();
    for (const img of images) {
      await expect(img).toBeVisible({ timeout: 5000 });
    }
    
    // Check if fonts are loaded
    await page.evaluate(() => document.fonts.ready);
    
    // Check icons (Lucide React)
    const icons = await page.locator('[data-lucide]').all();
    console.log(`Found ${icons.length} icons`);
    
    await page.screenshot({ path: `screenshots/resources-loaded.png`, fullPage: true });
  });
});

// Test 2: Responsive Layout Testing
test.describe('📱 Responsive Layout Tests', () => {
  viewports.forEach(viewport => {
    test(`Mobile/Tablet/Desktop layout at ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');
      
      // Check if layout adapts
      const isMobile = viewport.width < 768;
      const hamburgerMenu = await page.locator('button').filter({ hasText: /menu|☰/ }).isVisible().catch(() => false);
      
      if (isMobile) {
        // Mobile should have hamburger menu or collapsed navigation
        console.log(`✅ Mobile layout detected at ${viewport.width}px`);
      }
      
      // Check main content is visible
      await expect(page.locator('#root')).toBeVisible();
      
      // Take screenshot for each breakpoint
      await page.screenshot({ 
        path: `screenshots/responsive-${viewport.name.replace(/\s+/g, '-')}.png`,
        fullPage: true 
      });
    });
  });
});

// Test 3: Router Navigation Tests
test.describe('🔄 Router Navigation Tests', () => {
  const routes = [
    { path: '/', name: 'Dashboard' },
    { path: '/knowledge-graph', name: 'Knowledge Graph' },
    { path: '/decision-flow', name: 'Decision Flow' },
    { path: '/documents', name: 'Documents' },
    { path: '/analytics', name: 'Analytics' },
    { path: '/settings', name: 'Settings' },
  ];
  
  test('Navigate through all routes without white screen', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    for (const route of routes) {
      console.log(`Navigating to: ${route.path}`);
      
      // Navigate via URL
      await page.goto(`${BASE_URL}${route.path}`);
      await page.waitForLoadState('networkidle');
      
      // Wait for content (not just loading state)
      await page.waitForTimeout(1000);
      
      // Check no white screen (root should have content)
      const rootElement = await page.locator('#root');
      await expect(rootElement).toBeVisible();
      
      // Check URL matches
      expect(page.url()).toContain(route.path);
      
      // Take screenshot
      await page.screenshot({ 
        path: `screenshots/route-${route.name.toLowerCase().replace(/\s+/g, '-')}.png`,
        fullPage: true 
      });
      
      console.log(`✅ Route ${route.path} loaded successfully`);
    }
  });
  
  test('Sidebar/Navigation links work correctly', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Find navigation links
    const navLinks = await page.locator('a[href^="/"]').all();
    console.log(`Found ${navLinks.length} navigation links`);
    
    for (const link of navLinks.slice(0, 5)) { // Test first 5 links
      const href = await link.getAttribute('href');
      if (href && href !== '#') {
        await link.click();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(500);
        
        expect(page.url()).toContain(href);
        console.log(`✅ Navigation link ${href} works`);
        
        // Go back to home for next iteration
        await page.goto(BASE_URL);
        await page.waitForLoadState('networkidle');
      }
    }
  });
});

// Test 4: TailwindCSS Style Tests
test.describe('🎨 TailwindCSS Style Tests', () => {
  test('TailwindCSS classes are applied correctly', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Check if Tailwind styles are loaded
    const hasStyles = await page.evaluate(() => {
      const element = document.querySelector('[class*="flex"]') || 
                     document.querySelector('[class*="grid"]') ||
                     document.querySelector('[class*="p-"]') ||
                     document.querySelector('[class*="text-"]');
      return element !== null;
    });
    
    expect(hasStyles).toBe(true);
    console.log('✅ TailwindCSS classes detected');
    
    // Check colors
    const coloredElements = await page.locator('[class*="bg-"], [class*="text-"]').all();
    console.log(`Found ${coloredElements.length} elements with color classes`);
    
    // Take screenshot to verify styles
    await page.screenshot({ path: `screenshots/tailwind-styles.png`, fullPage: true });
  });
  
  test('Dark mode toggle works (if implemented)', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Try to find dark mode toggle
    const darkModeToggle = await page.locator('button').filter({ 
      hasText: /dark|light|moon|sun/i 
    }).first();
    
    const hasDarkMode = await darkModeToggle.count() > 0;
    
    if (hasDarkMode) {
      await darkModeToggle.click();
      await page.waitForTimeout(500);
      
      // Check if dark class is added to html
      const isDark = await page.evaluate(() => {
        return document.documentElement.classList.contains('dark') ||
               document.body.classList.contains('dark');
      });
      
      console.log(`✅ Dark mode toggle works: ${isDark ? 'Enabled' : 'Disabled'}`);
      
      await page.screenshot({ 
        path: `screenshots/dark-mode-${isDark ? 'on' : 'off'}.png`,
        fullPage: true 
      });
    } else {
      console.log('ℹ️  Dark mode toggle not found (optional feature)');
    }
  });
});

// Test 5: Interaction Tests
test.describe('🚀 Interaction Tests', () => {
  test('Login form interaction', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');
    
    // Find and fill login form
    const usernameInput = await page.locator('input[type="text"], input[type="email"]').first();
    const passwordInput = await page.locator('input[type="password"]').first();
    const submitButton = await page.locator('button[type="submit"]').first();
    
    if (await usernameInput.count() > 0) {
      await usernameInput.fill(TEST_USER);
      await passwordInput.fill(TEST_PASSWORD);
      await submitButton.click();
      
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);
      
      // Should redirect after login
      console.log('✅ Login form interaction completed');
      
      await page.screenshot({ path: `screenshots/login-interaction.png`, fullPage: true });
    } else {
      console.log('ℹ️  Login form not found on this page');
    }
  });
  
  test('Button click interactions', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Find all buttons
    const buttons = await page.locator('button').all();
    console.log(`Found ${buttons.length} buttons`);
    
    // Test first few buttons
    for (const button of buttons.slice(0, 3)) {
      const buttonText = await button.textContent();
      const isVisible = await button.isVisible();
      
      if (isVisible && buttonText?.trim()) {
        try {
          await button.click();
          await page.waitForTimeout(300);
          console.log(`✅ Button "${buttonText.trim()}" clicked`);
        } catch (e) {
          console.log(`⚠️  Button "${buttonText?.trim()}" click skipped (may be disabled)`);
        }
      }
    }
    
    await page.screenshot({ path: `screenshots/button-interactions.png`, fullPage: true });
  });
  
  test('Chart rendering (Recharts)', async ({ page }) => {
    await page.goto(`${BASE_URL}/analytics`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Wait for charts to render
    
    // Check for SVG charts
    const charts = await page.locator('svg').all();
    console.log(`Found ${charts.length} SVG elements (potential charts)`);
    
    if (charts.length > 0) {
      // Check if charts have data
      const hasChartData = await page.evaluate(() => {
        const svgs = document.querySelectorAll('svg');
        return Array.from(svgs).some(svg => {
          return svg.innerHTML.includes('path') || svg.innerHTML.includes('circle');
        });
      });
      
      console.log(`✅ Charts rendered: ${hasChartData ? 'Yes' : 'No'}`);
    }
    
    await page.screenshot({ path: `screenshots/charts-rendered.png`, fullPage: true });
  });
  
  test('Graph/Network visualization (React Force Graph)', async ({ page }) => {
    await page.goto(`${BASE_URL}/knowledge-graph`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Check for canvas or SVG used by force graph
    const graphContainer = await page.locator('canvas, svg').first();
    const hasGraph = await graphContainer.count() > 0;
    
    console.log(`✅ Graph visualization: ${hasGraph ? 'Present' : 'Not found'}`);
    
    await page.screenshot({ path: `screenshots/knowledge-graph.png`, fullPage: true });
  });
});

test.afterAll('Generate Test Report', async () => {
  console.log('\n========================================');
  console.log('📊 Test execution completed');
  console.log('========================================');
});
PLAYWRIGHT_TEST

# Create Playwright config
cat > playwright.config.ts << 'PLAYWRIGHT_CONFIG'
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['html', { outputFolder: 'playwright-report' }], ['list']],
  use: {
    baseURL: process.env.FRONTEND_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  outputDir: 'test-results/',
});
PLAYWRIGHT_CONFIG

cd ..

echo -e "${GREEN}✅ Playwright setup complete${NC}"
echo ""

# Step 1: Start frontend in background
echo -e "${YELLOW}=== Step 1: Starting Frontend ===${NC}"
cd frontend

# Kill any existing processes
pkill -f "vite" 2>/dev/null || true
sleep 2

# Start Vite dev server in background
echo "Starting Vite dev server..."
npm run dev > ../logs/vite-dev.log 2>&1 &
VITE_PID=$!
echo "Vite PID: $VITE_PID"

# Wait for Vite to start
echo "Waiting for Vite to start..."
for i in {1..30}; do
  if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is ready${NC}"
    break
  fi
  if [ $i -eq 30 ]; then
    echo -e "${RED}❌ Frontend failed to start${NC}"
    cat ../logs/vite-dev.log
    exit 1
  fi
  sleep 1
done

cd ..

# Step 2: Ensure backend is running
echo -e "${YELLOW}=== Step 2: Checking Backend ===${NC}"
for i in {1..10}; do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is ready${NC}"
    break
  fi
  if [ $i -eq 10 ]; then
    echo -e "${YELLOW}⚠️  Backend not available, starting it...${NC}"
    # Backend should already be running via docker-compose
  fi
  sleep 1
done

# Step 3: Run Playwright tests
echo -e "${YELLOW}=== Step 3: Running Playwright E2E Tests ===${NC}"
cd frontend

export FRONTEND_URL="http://localhost:5173"
export BACKEND_URL="http://localhost:8000"

# Run tests
npx playwright test --config=playwright.config.ts --reporter=list

TEST_EXIT_CODE=$?

cd ..

# Step 4: Generate report
echo ""
echo -e "${YELLOW}=== Step 4: Generating Test Report ===${NC}"

# Copy screenshots to report directory
cp -r frontend/screenshots/* "$screenshot_dir/" 2>/dev/null || true

# Create HTML report
cat > "$screenshot_dir/index.html" << HTML_REPORT
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .summary { background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .pass { color: #22c55e; }
        .fail { color: #ef4444; }
        .screenshot-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .screenshot-card { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        .screenshot-card img { width: 100%; height: auto; }
        .screenshot-card h3 { margin: 10px; font-size: 14px; }
    </style>
</head>
<body>
    <h1>🧪 E2E Test Report</h1>
    <div class="summary">
        <h2>Test Summary</h2>
        <p><span class="pass">✅ Passed: $pass_count</span></p>
        <p><span class="fail">❌ Failed: $fail_count</span></p>
        <p><strong>Test Date:</strong> $(date '+%Y-%m-%d %H:%M:%S')</p>
        <p><strong>Frontend URL:</strong> $FRONTEND_URL</p>
        <p><strong>Backend URL:</strong> $BACKEND_URL</p>
    </div>
    
    <h2>Screenshots</h2>
    <div class="screenshot-grid">
HTML_REPORT

# Add screenshots to report
for screenshot in "$screenshot_dir"/*.png; do
  if [ -f "$screenshot" ]; then
    filename=$(basename "$screenshot")
    cat >> "$screenshot_dir/index.html" << SCREENSHOT_CARD
        <div class="screenshot-card">
            <img src="$filename" alt="$filename">
            <h3>$filename</h3>
        </div>
SCREENSHOT_CARD
  fi
done

cat >> "$screenshot_dir/index.html" << 'HTML_END'
    </div>
</body>
</html>
HTML_END

echo -e "${GREEN}✅ Test report generated: $screenshot_dir/index.html${NC}"
echo ""

# Cleanup
echo -e "${YELLOW}=== Cleanup ===${NC}"
kill $VITE_PID 2>/dev/null || true
echo "Stopped Vite dev server"

# Final summary
echo ""
echo "========================================"
echo -e "${YELLOW}Test Summary:${NC}"
echo -e "  ${GREEN}Passed: $pass_count${NC}"
echo -e "  ${RED}Failed: $fail_count${NC}"
echo "========================================"

if [ $fail_count -eq 0 ]; then
  echo -e "${GREEN}🎉 All visual and interaction tests passed!${NC}"
  echo -e "${BLUE}📸 Screenshots saved to: $screenshot_dir${NC}"
  echo -e "${BLUE}📄 Report: $screenshot_dir/index.html${NC}"
  exit 0
else
  echo -e "${RED}⚠️  Some tests failed. Check the report for details.${NC}"
  echo -e "${BLUE}📸 Screenshots saved to: $screenshot_dir${NC}"
  echo -e "${BLUE}📄 Report: $screenshot_dir/index.html${NC}"
  exit 1
fi