import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("PAGEERROR", e.message, e.stack));
page.on("console", (m) => console.log("CONSOLE", m.type(), m.text()));
await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
const btn = page.getByRole("button", { name: /start factory/i });
console.log("btn count", await btn.count());
await btn.click();
await page.waitForTimeout(1500);
console.log("FIRST BTN", await page.locator("button.btn").first().innerText());
console.log("DAY STAT", (await page.locator(".stat").nth(1).innerText()).replace(/\n/g, " | "));
await page.getByRole("button", { name: /step tick/i }).click();
await page.waitForTimeout(400);
console.log("DAY AFTER STEP", (await page.locator(".stat").nth(1).innerText()).replace(/\n/g, " | "));
await browser.close();
