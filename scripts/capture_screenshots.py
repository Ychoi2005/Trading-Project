"""Capture real local Streamlit views; requires Playwright and installed Chromium.

Install tooling separately: python -m pip install playwright
Start Streamlit first, then run with --base-url and --browser as needed.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    parser.add_argument("--browser", default="/usr/bin/chromium")
    parser.add_argument("--output", type=Path, default=Path("docs/screenshots"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.browser, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1150}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.base_url, wait_until="domcontentloaded")
        expect(page.get_by_role("button", name="Compare across seeds")).to_be_visible(timeout=30000)

        def capture(name: str) -> None:
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            expect(page.locator('[data-testid="stSkeleton"]')).to_have_count(0, timeout=30000)
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(800)  # Allow final chart/font paint; never synthesize pixels.
            page.screenshot(path=str(args.output / f"{name}.png"), full_page=True)

        capture("executive_overview")
        page.get_by_text("Policy Comparison", exact=True).click()
        page.get_by_role("button", name="Run matched experiment").click()
        expect(
            page.get_by_text("CURRENT RESULTS · 10 executed seeds per scenario", exact=True)
        ).to_be_visible(timeout=30000)
        expect(page.locator(".js-plotly-plot").first).to_be_visible(timeout=30000)
        capture("policy_comparison")
        page.get_by_role("tab", name="Data-quality exposure", exact=True).click()
        capture("data_quality")
        page.get_by_role("tab", name="Penalty sensitivity", exact=True).click()
        capture("penalty_sensitivity")
        page.get_by_text("Market Simulation", exact=True).click()
        expect(page.locator(".js-plotly-plot").first).to_be_visible(timeout=30000)
        capture("market_simulation")
        page.get_by_text("Decision Explorer", exact=True).click()
        page.get_by_role("combobox", name="Policy to inspect").click()
        page.get_by_role("option", name="Wait for Fresh Data", exact=True).click()
        expect(
            page.get_by_text("Awaiting a sufficiently fresh delivered quote", exact=True)
        ).to_be_visible(timeout=30000)
        capture("decision_explorer")
        assert not errors, errors
        (args.output / "capture.json").write_text(
            json.dumps(
                dict(
                    viewport=dict(width=1600, height=1150),
                    browser=browser.version,
                    scenario="Reliability stress demonstration",
                    seed=42,
                    trials=10,
                    tooling="Playwright against the actual local Streamlit server",
                    browser_page_errors=errors,
                ),
                indent=2,
            )
            + "\n"
        )
        browser.close()
    print(f"Captured six actual dashboard screenshots in {args.output}")


if __name__ == "__main__":
    main()
