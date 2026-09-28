"""Capture fresh screenshots of the CURRENT CTQ app into _shots2/ for the
presentation and PDF report.  Run from the project root (dev server :5173):
    .venv/Scripts/python.exe capture_shots2.py
"""
import os, time
from playwright.sync_api import sync_playwright

OUT = "_shots2"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:5173/#"

def shoot(page, name, full=False):
    page.screenshot(path=f"{OUT}/{name}.png", full_page=full)
    print("captured", name)

def js_click(page, text):
    """Click the first visible button whose label contains `text`."""
    return page.evaluate("""(t) => {
        const btn = [...document.querySelectorAll('button')]
            .find(b => b.textContent.includes(t) && b.offsetParent !== null);
        if (btn) { btn.click(); return true; }
        return false;
    }""", text)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=2)

    # 1. Home
    page.goto(BASE + "/")
    page.wait_for_selector(".hero")
    time.sleep(1.0)
    shoot(page, "01_home")

    # 2. Find Trials - structured tab top (tabs + cohort bar + sample buttons)
    page.goto(BASE + "/matcher")
    page.wait_for_selector("h1")
    time.sleep(0.8)
    shoot(page, "02_matcher_tabs")

    # 3. Load diabetes sample, scroll to labs
    page.get_by_role("button", name="Sample: Diabetes (47F)").click()
    time.sleep(0.8)
    page.locator("text=Laboratory Values").first.scroll_into_view_if_needed()
    time.sleep(0.4)
    shoot(page, "03_matcher_form")

    # 4. Run matching FIRST (before touching cohort), -> results page
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.3)
    js_click(page, "Find Matching Trials")
    page.wait_for_url("**/#/results", timeout=240000)
    page.wait_for_selector(".result-card", timeout=240000)
    time.sleep(1.5)
    shoot(page, "05_results_top")
    page.locator(".result-card").nth(2).scroll_into_view_if_needed()
    time.sleep(0.4)
    shoot(page, "06_results_cards")

    # 5. Cohort mode (fresh load): add another patient
    page.goto(BASE + "/matcher")
    page.wait_for_selector("h1")
    time.sleep(0.8)
    if js_click(page, "+ Add another patient"):
        time.sleep(0.8)
        page.locator("text=Patient 2 of 2").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        shoot(page, "04_cohort_mode")

    # 6. Unstructured tab
    page.goto(BASE + "/matcher")
    page.wait_for_selector("h1")
    time.sleep(0.6)
    js_click(page, "Unstructured Data")
    time.sleep(0.8)
    shoot(page, "07_unstructured_upload")

    # 7. Upload the 5-patient unstructured sample -> extraction + stepper
    page.locator("input[type=file]").first.set_input_files("sample_data/unstructured_5_patients.csv")
    page.wait_for_selector("text=Patient 1 of 5", timeout=300000)
    time.sleep(1.0)
    shoot(page, "08_unstructured_extracted")
    js_click(page, "Next patient")
    time.sleep(0.8)
    shoot(page, "09_unstructured_patient2")

    # 8. Evaluation page + one-click sample run
    page.goto(BASE + "/evaluation")
    page.wait_for_selector("input[type=file]")
    time.sleep(0.8)
    shoot(page, "10_evaluation_upload")
    js_click(page, "Load bundled sample data")
    page.wait_for_selector("text=Loaded 10 patient notes", timeout=180000)
    time.sleep(0.5)
    js_click(page, "Run Evaluation")
    page.wait_for_selector(".metric-tiles", timeout=600000)
    time.sleep(1.2)
    shoot(page, "11_evaluation_result")
    page.locator("text=Predictions vs labels").first.scroll_into_view_if_needed()
    time.sleep(0.5)
    shoot(page, "12_evaluation_table")

    browser.close()
    print("ALL DONE")
