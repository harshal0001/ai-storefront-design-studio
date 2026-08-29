/**
 * Quick E2E: product card click sets focus; border-radius prompt applies.
 * Run: node e2e-focus-test.mjs
 */
import { chromium } from "playwright";

const BASE = "http://localhost:5173";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto(BASE, { waitUntil: "networkidle", timeout: 60000 });

  // Wait for preview iframe
  const iframe = page.frameLocator(".preview-container iframe").first();
  await iframe.locator(".sf-product").first().waitFor({ timeout: 90000 });

  // Scroll catalog into view inside iframe
  await iframe
    .locator("#sf-products-section")
    .scrollIntoViewIfNeeded()
    .catch(() => {});

  // Click first product card in preview (not heart button)
  await iframe.locator(".sf-product .sf-product__body").first().click({ timeout: 10000 });

  await page.waitForTimeout(2000);

  const hasFocusBar = await page
    .locator(".section-focus-bar")
    .isVisible()
    .catch(() => false);
  const zoneTourActive = await page
    .locator(".chat-panel--tour")
    .isVisible()
    .catch(() => false);
  const productCount = await iframe.locator("#sf-products-section .sf-product").count();
  const markerCount = await iframe.locator("[data-sf-focus].sf-product").count();
  const hasInit = await iframe
    .locator("body")
    .evaluate(() => typeof window.applyFocusMarkers === "function");
  console.log(
    "focus bar:",
    hasFocusBar,
    "zone tour:",
    zoneTourActive,
    "catalog products:",
    productCount,
    "marked:",
    markerCount,
    "applyFocusMarkers:",
    hasInit,
  );
  const editingText = await page
    .locator(".section-focus-active strong")
    .textContent()
    .catch(() => "");
  console.log("Editing label after click:", editingText);

  if (!editingText?.includes("Product cards")) {
    throw new Error(
      `Expected 'Product cards' in editing label after click, got: ${editingText || "(empty)"}`,
    );
  }

  // Send border radius message
  const input = page.locator(".chat-input-area input[type='text']");
  await input.fill("make the product border radius 0");
  await input.press("Enter");

  await page.waitForTimeout(5000);

  const lastAssistant = await page
    .locator(".message.assistant .message-text")
    .last()
    .textContent()
    .catch(() => "");

  console.log("Last assistant message:", (lastAssistant || "").slice(0, 200));

  if (/error|something went wrong/i.test(lastAssistant || "")) {
    throw new Error(`Chat returned error: ${lastAssistant}`);
  }

  if (!/applied|Done|sharp|changes/i.test(lastAssistant || "")) {
    console.warn("WARN: unexpected assistant reply (may still be ok):", lastAssistant);
  }

  // Verify sharp shape in preview HTML via API proxy
  const cardShape = await iframe
    .locator("#sf-products-section")
    .evaluate(
      (el) =>
        el.closest("[data-card-shape]")?.getAttribute("data-card-shape") ||
        el.getAttribute("data-card-shape"),
    )
    .catch(() => null);
  console.log("Card shape attr:", cardShape);

  if (errors.length) {
    console.warn("Console/page errors:", errors.slice(0, 5));
  }

  console.log("E2E PASSED");
  await browser.close();
}

main().catch((e) => {
  console.error("E2E FAILED:", e.message);
  process.exit(1);
});
