"""Capture real screenshots of the CTQ app for the explanation PDF."""
import os, time
from playwright.sync_api import sync_playwright

OUT = "_shots"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:5173/#"

def shoot(page, name, full=False):
    page.screenshot(path=f"{OUT}/{name}.png", full_page=full)
    print("captured", name)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=2)

    # 1. Home
    page.goto(BASE + "/")
    page.wait_for_selector(".hero")
    time.sleep(1.0)
    shoot(page, "01_home")

    # 2. Matcher - empty
    page.goto(BASE + "/matcher")
    page.wait_for_selector("h1")
    time.sleep(0.8)
    shoot(page, "02_matcher_top")

    # 3. Matcher - sample loaded (scroll to medications)
    page.get_by_role("button", name="Sample: Diabetes (47F)").click()
    time.sleep(0.8)
    page.locator("text=Medications").first.scroll_into_view_if_needed()
    time.sleep(0.4)
    shoot(page, "03_matcher_medications")

    # 4. Full form (top)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.4)
    shoot(page, "04_matcher_full_form")

    # 5. Run matching -> results
    page.get_by_role("button", name="Find Matching Trials").click()
    page.wait_for_url("**/#/results", timeout=180000)
    page.wait_for_selector(".result-card", timeout=180000)
    time.sleep(1.5)
    shoot(page, "05_results_top")

    # 6. Results - expand first card reasons
    card = page.locator(".result-card").first
    card.scroll_into_view_if_needed()
    time.sleep(0.4)
    shoot(page, "06_results_card")

    # 7. Trials database
    page.goto(BASE + "/trials")
    page.wait_for_selector("table.data, .card", timeout=60000)
    time.sleep(1.2)
    shoot(page, "07_trials_db")

    # 8. Trial detail (click first row if clickable, else first trial link)
    try:
        page.locator("tr.clickable").first.click(timeout=5000)
        time.sleep(1.2)
        shoot(page, "08_trial_detail")
    except Exception as e:
        print("trial detail skipped:", e)

    # 9. Evaluation page (upload section)
    page.goto(BASE + "/evaluation")
    page.wait_for_selector("input[type=file]")
    time.sleep(0.8)
    shoot(page, "09_evaluation_upload")

    # 10. Run real evaluation with the demo files
    page.locator("input[type=file]").nth(0).set_input_files("evaluation_patient_P001_unlabelled.csv")
    page.wait_for_selector("text=patients parsed", timeout=60000)
    page.locator("input[type=file]").nth(1).set_input_files("evaluation_labels_P001_ground_truth.csv")
    page.wait_for_selector("text=labels parsed", timeout=60000)
    time.sleep(0.5)
    page.get_by_role("button", name="Run Evaluation").click()
    page.wait_for_selector(".metric-tiles", timeout=300000)
    time.sleep(1.0)
    shoot(page, "10_evaluation_result")

    browser.close()
    print("ALL DONE")
