"""Browser smoke test of the main flow on sample emails (no Google, no key needed).

Start the backend with LLM_PROVIDER=mock and the frontend first (README Quick start; use `npm run build && npm run start` for the frontend), then:
  pip install playwright && playwright install chromium
  python e2e/smoke_test.py
Uses data/drafts.json, so delete that file afterwards if you do not want the test draft.
"""
import re, sys
from playwright.sync_api import sync_playwright, expect
results = []
def check(n, ok, x=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + n + (f" [{x}]" if x else ""))
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("http://localhost:3000")
    expect(page.locator("button.row").first).to_be_visible(timeout=15000)
    check("35 sample emails load", page.locator("button.row").count() == 35)
    check("Demo sending pill", page.locator(".demo-pill", has_text="Demo sending").is_visible())
    page.locator("button.row", has_text="Server down").click()
    page.get_by_role("button", name="Summarize", exact=True).click()
    expect(page.locator(".card h3", has_text="Summary")).to_be_visible(timeout=10000); check("Summarize works", True)
    page.get_by_role("button", name="Prioritize all").click()
    expect(page.get_by_text("35/35 prioritized")).to_be_visible(timeout=60000); check("Prioritize all works", True)
    page.locator("button.row", has_text="Server down").click()
    page.get_by_role("button", name="Reply with AI").click()
    page.get_by_label("Instruction").fill("Say we are looking into it now")
    page.get_by_role("button", name="Generate draft").click()
    expect(page.get_by_label("Subject")).to_be_visible(timeout=10000); check("Draft generated", True)
    check("Send disabled before approval", page.get_by_role("button", name=re.compile(r"^Send \(demo\)")).is_disabled())
    page.get_by_role("button", name="Approve draft").click()
    expect(page.get_by_text("You can now send it.")).to_be_visible(timeout=10000)
    page.get_by_label("Message").fill("Hello,\n\nWe are looking into it now.\n\nBest regards")
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_role("button", name="Approve draft")).to_be_visible(timeout=10000)
    check("Editing after approval removes approval", page.get_by_role("button", name=re.compile(r"^Send \(demo\)")).is_disabled())
    page.get_by_role("button", name="Approve draft").click()
    expect(page.get_by_text("You can now send it.")).to_be_visible(timeout=10000)
    page.get_by_role("button", name="Send (demo)…").click()
    page.locator("dialog.confirm").get_by_role("button", name="Send (demo)", exact=True).click()
    expect(page.get_by_text("Demo mode: it was marked as sent")).to_be_visible(timeout=10000); check("Demo send works", True)
    page.get_by_role("button", name="Drafts", exact=True).click()
    expect(page.locator(".activity").get_by_text("Email sent").first).to_be_visible(timeout=10000)
    check("Activity log shows the demo send", page.locator(".activity .badge", has_text="demo").count() >= 1)
    page.get_by_role("button", name="Connect", exact=True).click()
    expect(page.get_by_text("Not set up yet.")).to_be_visible(timeout=10000); check("Connect tab explains Gmail setup", True)
    check("no JS errors", not errs, "; ".join(errs)[:150]); b.close()
print(f"{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
