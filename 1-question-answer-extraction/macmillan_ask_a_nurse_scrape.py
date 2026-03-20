import asyncio
import csv
import sys
from typing import Optional, Tuple, List

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError


# ---- Helpers ---------------------------------------------------------------

def first_nonempty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v is not None and v != "":
            return v
    return None


async def get_inner_text(locator) -> Optional[str]:
    """
    Return the locator's innerText exactly as the browser renders it.
    We do not modify, trim, normalise, or rewrite anything.
    """
    try:
        return await locator.inner_text()
    except Exception:
        return None


async def extract_thread(page):
    """
    Extract (Title, Question, Answer) from a Macmillan Ask a Nurse thread.
    Uses Macmillan/Khoros-specific, DOM-verified selectors.
    Text is extracted verbatim via inner_text().
    """

    # ---- Title ----
    title = await get_inner_text(
        page.locator("h1.name").first
    )

    # ---- Question ----
    # The original post content
    question = await get_inner_text(
        page.locator(".thread-start > .content").first
    )

    # ---- Answer ----
    # First Macmillan nurse reply
    answer = await get_inner_text(
        page.locator(
            ".content.full.threaded-reply-content.user-defined-markup .content"
        ).first
    )

    return title, question, answer


async def scrape_urls(
    urls: List[str],
    headless: bool = True,
    debug: bool = False,
) -> List[dict]:
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            slow_mo=100 if (debug and not headless) else 0,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        for i, url in enumerate(urls, start=1):
            print(f"[{i}/{len(urls)}] Fetching {url}")
            url = (url or "").strip()
            if not url:
                continue

            row = {"URL": url, "Title": None, "Question": None, "Answer": None, "Error": None}

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # --- Attempt to accept common cookie banners that can block content ---
                for btn_text in ["Accept all cookies", "Accept all", "I agree", "Accept"]:
                    try:
                        btn = page.get_by_role("button", name=btn_text)
                        if await btn.count():
                            await btn.first.click(timeout=3000)
                            break
                    except Exception:
                        pass

                # --- Wait for likely post content (but do not hard-fail if absent) ---
                try:
                    await page.wait_for_selector(
                        ".lia-message-body-content, .lia-message-body, .MessageBody, [class*='message-body']",
                        timeout=25000,
                    )
                except PWTimeoutError:
                    pass

                if debug:
                    # Quick visibility into what the page actually contains
                    print(f"\n[{i}] URL: {url}")
                    print("page title:", await page.title())
                    print("body-content count:", await page.locator(".lia-message-body-content").count())
                    print("lia-message-body count:", await page.locator(".lia-message-body").count())
                    print("MessageBody count:", await page.locator(".MessageBody").count())
                    print("fallback [class*='message-body'] count:", await page.locator("[class*='message-body']").count())
                    print("article count:", await page.locator("article").count())

                title, question, answer = await extract_thread(page)
                row["Title"] = title
                row["Question"] = question
                row["Answer"] = answer

                # Flag if missing fields
                if (title is None or title == "") or (question is None or question == "") or (answer is None or answer == ""):
                    row["Error"] = "One or more fields empty (check selectors / page layout / access)."

                    # --- Dump debug artifacts for inspection ---
                    if debug:
                        safe_idx = str(i).zfill(3)
                        html_path = f"debug_fail_{safe_idx}.html"
                        png_path = f"debug_fail_{safe_idx}.png"
                        try:
                            html = await page.content()
                            with open(html_path, "w", encoding="utf-8") as f:
                                f.write(html)
                            await page.screenshot(path=png_path, full_page=True)
                            print(f"Saved debug HTML: {html_path}")
                            print(f"Saved debug PNG : {png_path}")
                        except Exception as dump_e:
                            print("Failed to save debug artifacts:", dump_e)

            except Exception as e:
                row["Error"] = f"{type(e).__name__}: {e}"

            results.append(row)

        await context.close()
        await browser.close()

    return results


def read_urls_from_csv(path: str, url_column: Optional[str] = None) -> List[str]:
    df = pd.read_csv(path)
    if url_column and url_column in df.columns:
        col = url_column
    else:
        # Heuristic: choose first column that looks like it contains URLs
        candidates = [c for c in df.columns if "url" in c.lower()]
        col = candidates[0] if candidates else df.columns[0]
    return [str(u) for u in df[col].tolist()]


# ---- CLI -------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python macmillan_ask_a_nurse_scrape.py input.csv output.csv [url_column_name]")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    url_col = sys.argv[3] if len(sys.argv) >= 4 else None

    urls = read_urls_from_csv(input_csv, url_col)

    # Debug settings:
    # - Set debug=True to print counts and save debug_fail_XXX.html/png when extraction fails.
    # - Set headless=False to visually observe cookie banners / interstitials.
    rows = asyncio.run(scrape_urls(urls, headless=True, debug=False))
    # Once it’s working, you can switch back to faster mode: rows = asyncio.run(scrape_urls(urls, headless=True, debug=False))

    # Write output (preserve content exactly as extracted)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["URL", "Title", "Question", "Answer", "Error"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    main()
