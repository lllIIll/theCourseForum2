/**
 * Audit helper: snapshots the SEAS faculty department filter dropdown to
 * data/dept-filters.json so future filter-ID drift is visible as a diff.
 *
 * Also runs a coverage sanity check: sums unique faculty slugs across every
 * filter ID and compares to the unfiltered total. Any drop surfaces a
 * faculty not categorized by SEAS under any dept.
 *
 * Usage: npx tsx scripts/lab_scraper/snapshot-filters.ts
 * Output: scripts/lab_scraper/data/dept-filters.json
 */

import { chromium, type Page } from "playwright";
import { writeFileSync } from "fs";
import { resolve } from "path";

const FACULTY_URL = "https://engineering.virginia.edu/faculty";
const DELAY_MS = 1500;
const OUTPUT_PATH = resolve(__dirname, "data/dept-filters.json");

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

async function scrapeFilterOptions(page: Page) {
  return page.$$eval(
    'select.filter_tool_select[name="department"] option',
    (opts) =>
      opts
        .map((o) => ({
          value: (o as HTMLOptionElement).value,
          label: o.textContent?.trim() || "",
        }))
        .filter((o) => o.value && o.value !== "All" && o.label && !o.label.startsWith("-")),
  );
}

async function countFacultyOnPage(page: Page, url: string): Promise<number> {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("ul.people_list_rows, .no_results", { timeout: 15000 });
  return page.$$eval("li.people_list_row", (cards) => cards.length);
}

async function getTotalPages(page: Page): Promise<number> {
  // Filters with only one page of results have no pagination element.
  // Wait briefly, then bail to 1 instead of the 30s default timeout.
  const loc = page.locator(".pagination_form_suffix");
  try {
    const count = await loc.count();
    if (count === 0) return 1;
    const suffix = await loc.first().textContent({ timeout: 2000 });
    if (!suffix) return 1;
    const match = suffix.match(/of\s+(\d+)/);
    return match ? parseInt(match[1], 10) : 1;
  } catch {
    return 1;
  }
}

async function scrapeSlugsForDept(
  page: Page,
  deptId: string,
): Promise<Set<string>> {
  const firstUrl = `${FACULTY_URL}?department=${deptId}`;
  await page.goto(firstUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  // No-results is a valid state — not all depts populate
  const hasRows = (await page.locator("ul.people_list_rows").count()) > 0;
  if (!hasRows) return new Set();

  await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
  const totalPages = await getTotalPages(page);

  const slugs = new Set<string>();
  for (let p = 0; p < totalPages; p++) {
    if (p > 0) {
      await page.goto(`${FACULTY_URL}?department=${deptId}&page=${p}`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
      await sleep(DELAY_MS);
    }
    const pageSlugs = await page.$$eval(
      "li.people_list_row a.contact_block_name_link",
      (links) =>
        links.map((a) =>
          (a as HTMLAnchorElement).getAttribute("href")?.replace("/faculty/", "") || "",
        ),
    );
    pageSlugs.forEach((s) => s && slugs.add(s));
  }
  return slugs;
}

async function scrapeUnfilteredSlugs(page: Page): Promise<Set<string>> {
  await page.goto(FACULTY_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
  const totalPages = await getTotalPages(page);

  const slugs = new Set<string>();
  for (let p = 0; p < totalPages; p++) {
    if (p > 0) {
      await page.goto(`${FACULTY_URL}?page=${p}`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
      await sleep(DELAY_MS);
    }
    const pageSlugs = await page.$$eval(
      "li.people_list_row a.contact_block_name_link",
      (links) =>
        links.map((a) =>
          (a as HTMLAnchorElement).getAttribute("href")?.replace("/faculty/", "") || "",
        ),
    );
    pageSlugs.forEach((s) => s && slugs.add(s));
  }
  return slugs;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  const page = await ctx.newPage();

  console.log(`Fetching ${FACULTY_URL} to read filter dropdown...`);
  await page.goto(FACULTY_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector('select.filter_tool_select[name="department"]');
  const rawOptions = await scrapeFilterOptions(page);
  // SEAS renders the filter dropdown twice (desktop + mobile). Dedupe by id.
  const seen = new Set<string>();
  const filters = rawOptions
    .filter((o) => {
      if (seen.has(o.value)) return false;
      seen.add(o.value);
      return true;
    })
    .map((o) => ({
      id: parseInt(o.value, 10),
      label: o.label,
      slug: slugify(o.label),
    }));
  console.log(`Discovered ${filters.length} department filters:\n`);
  filters.forEach((f) => console.log(`  ${f.id.toString().padStart(4)}  ${f.label}`));

  console.log("\n--- Coverage sanity check ---");
  console.log("Unfiltered total:");
  const unfilteredSlugs = await scrapeUnfilteredSlugs(page);
  console.log(`  ${unfilteredSlugs.size} unique faculty\n`);

  console.log("Per-filter counts:");
  const filterResults: Record<string, { slugs: string[]; count: number }> = {};
  const allFilteredSlugs = new Set<string>();
  for (const f of filters) {
    const slugs = await scrapeSlugsForDept(page, f.id.toString());
    console.log(`  ${f.label.padEnd(40)} ${slugs.size}`);
    filterResults[f.label] = { slugs: [...slugs], count: slugs.size };
    slugs.forEach((s) => allFilteredSlugs.add(s));
  }

  console.log("\n--- Coverage delta ---");
  const onlyUnfiltered = [...unfilteredSlugs].filter((s) => !allFilteredSlugs.has(s));
  const onlyFiltered = [...allFilteredSlugs].filter((s) => !unfilteredSlugs.has(s));
  console.log(`In unfiltered but no filter tags them: ${onlyUnfiltered.length}`);
  if (onlyUnfiltered.length) console.log("  " + onlyUnfiltered.join(", "));
  console.log(`In some filter but not unfiltered listing: ${onlyFiltered.length}`);
  if (onlyFiltered.length) console.log("  " + onlyFiltered.join(", "));

  const output = {
    scraped_at: new Date().toISOString(),
    faculty_url: FACULTY_URL,
    filters,
    coverage: {
      unfiltered_total: unfilteredSlugs.size,
      union_of_filters_total: allFilteredSlugs.size,
      only_unfiltered: onlyUnfiltered,
      only_filtered: onlyFiltered,
    },
    per_filter_counts: Object.fromEntries(
      Object.entries(filterResults).map(([k, v]) => [k, v.count]),
    ),
  };
  writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));
  console.log(`\nSaved to ${OUTPUT_PATH}`);

  await browser.close();
}

main().catch((e) => {
  console.error("snapshot-filters failed:", e);
  process.exit(1);
});
