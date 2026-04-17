/**
 * Phase 1: Scrape SEAS Faculty Directory.
 *
 * Two-pass strategy:
 *   Pass A — unfiltered `?page=N` pagination. Provides coverage guarantee
 *            (every faculty on the directory, including Med-school joint
 *             appointments that aren't tagged to any SEAS department).
 *   Pass B — per-filter `?department={id}&page=N` pagination. Provides
 *            authoritative department tagging from SEAS's own categorization.
 *
 * Results are merged by slug. `departments[]` captures every filter a
 * faculty appeared under (exposes joint appointments). `department` is a
 * deterministic primary pick with a `departmentSource` flag so downstream
 * can distinguish filter-backed tagging from title fallback.
 *
 * Usage: npx tsx scripts/lab_scraper/scrape-listing.ts [--new] [--only=ID]
 *   --new      Writes to data/listing_new.json instead of data/listing.json
 *              (safety gate before overwriting the current file)
 *   --only=ID  Restricts Pass B to the single department filter ID and
 *              skips Pass A. Fast sanity check before a full crawl.
 *
 * Output: scripts/lab_scraper/data/listing.json (or listing_new.json)
 */

import { chromium, type Page } from "playwright";
import { writeFileSync } from "fs";
import { resolve } from "path";
import type { ScrapedLab } from "./types";

const BASE_URL = "https://engineering.virginia.edu";
const FACULTY_URL = `${BASE_URL}/faculty`;
const DELAY_MS = 1500;

const USE_NEW_OUTPUT = process.argv.includes("--new");
const ONLY_FILTER = (() => {
  const arg = process.argv.find((a) => a.startsWith("--only="));
  return arg ? arg.split("=")[1] : null;
})();
const OUTPUT_PATH = resolve(
  __dirname,
  USE_NEW_OUTPUT ? "data/listing_new.json" : "data/listing.json",
);

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function getTotalPages(page: Page): Promise<number> {
  const loc = page.locator(".pagination_form_suffix");
  try {
    if ((await loc.count()) === 0) return 1;
    const suffix = await loc.first().textContent({ timeout: 2000 });
    if (!suffix) return 1;
    const match = suffix.match(/of\s+(\d+)/);
    return match ? parseInt(match[1], 10) : 1;
  } catch {
    return 1;
  }
}

/** Per-card DOM extraction. Pulled into its own fn so both passes share it. */
async function scrapeCards(page: Page): Promise<Partial<ScrapedLab>[]> {
  return page.$$eval("li.people_list_row", (cards) =>
    cards.map((card) => {
      const nameEl = card.querySelector(
        ".contact_block_name_link_label",
      ) as HTMLElement | null;
      const linkEl = card.querySelector(
        "a.contact_block_name_link",
      ) as HTMLAnchorElement | null;
      const titleEls = card.querySelectorAll(
        ".people_list_item_title_group .people_list_item_title",
      );
      const hiringEl = card.querySelector(
        ".people_list_item_hiring",
      ) as HTMLElement | null;
      const photoEl = card.querySelector(
        "img.people_list_item_image",
      ) as HTMLImageElement | null;
      const descEl = card.querySelector(
        ".people_list_item_description",
      ) as HTMLElement | null;
      const linkEls = card.querySelectorAll(
        ".people_list_item_links a.people_list_item_link",
      );

      const profilePath = linkEl?.getAttribute("href") || "";
      const slug = profilePath.replace("/faculty/", "");

      return {
        professorName: nameEl?.textContent?.trim() || "",
        slug,
        profileUrl: profilePath,
        titles: Array.from(titleEls).map(
          (el) => (el as HTMLElement).textContent?.trim() || "",
        ),
        isRecruiting: hiringEl !== null,
        photoUrl: photoEl?.getAttribute("src") || null,
        descriptionSnippet: descEl?.textContent?.trim() || "",
        externalLinks: Array.from(linkEls).map((a) => ({
          label:
            (
              a.querySelector(
                ".people_list_item_link_label",
              ) as HTMLElement | null
            )?.textContent?.trim() || "",
          url: (a as HTMLAnchorElement).href || "",
        })),
      };
    }),
  );
}

/** Legacy title-based department parser. Used only as last-resort fallback. */
function departmentFromTitles(titles: string[]): string {
  for (const title of titles) {
    // Most common shape: "Rank, Department of X" or "Rank, X Engineering"
    // Pull the segment after the first comma.
    const afterComma = title.split(",").slice(1).join(",").trim();
    if (!afterComma) continue;
    // Strip leading "Department of "
    const cleaned = afterComma.replace(/^Department of\s+/i, "").trim();
    if (cleaned) return cleaned;
  }
  // Fallback: last comma-delimited segment of the first title
  const first = titles[0] || "";
  const m = first.match(/(?:Department of\s+)?([^,]+)$/);
  return m ? m[1].trim() : first;
}

async function scrapeFilterOptions(
  page: Page,
): Promise<{ id: string; label: string }[]> {
  const raw = await page.$$eval(
    'select.filter_tool_select[name="department"] option',
    (opts) =>
      opts
        .map((o) => ({
          id: (o as HTMLOptionElement).value,
          label: o.textContent?.trim() || "",
        }))
        .filter(
          (o) =>
            o.id &&
            o.id !== "All" &&
            o.label &&
            !o.label.startsWith("-"),
        ),
  );
  // SEAS renders the dropdown twice (desktop + mobile). Dedup by id.
  const seen = new Set<string>();
  return raw.filter((o) => {
    if (seen.has(o.id)) return false;
    seen.add(o.id);
    return true;
  });
}

async function scrapePaginated(
  page: Page,
  buildUrl: (pageNum: number) => string,
): Promise<Partial<ScrapedLab>[]> {
  const firstUrl = buildUrl(0);
  await page.goto(firstUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  const hasRows = (await page.locator("ul.people_list_rows").count()) > 0;
  if (!hasRows) return [];
  await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
  const totalPages = await getTotalPages(page);

  const all: Partial<ScrapedLab>[] = [];
  for (let p = 0; p < totalPages; p++) {
    if (p > 0) {
      await page.goto(buildUrl(p), {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForSelector("ul.people_list_rows", { timeout: 15000 });
      await sleep(DELAY_MS);
    }
    const cards = await scrapeCards(page);
    all.push(...cards);
  }
  return all;
}

function pickPrimaryDepartment(
  titles: string[],
  departments: string[],
): string {
  if (departments.length === 0) return "";
  if (departments.length === 1) return departments[0];
  // Iterate titles in order — title[0] is the faculty's primary self-
  // identification, title[1+] are courtesy/joint appointments. For each
  // title, return the first filter label that appears verbatim in it.
  // This prevents alphabetical sort order from picking a courtesy
  // appointment over a primary one (xun-zhao: primary MAE, courtesy ECE
  // -- must return MAE, not ECE).
  for (const title of titles) {
    const lower = title.toLowerCase();
    for (const d of departments) {
      if (lower.includes(d.toLowerCase())) return d;
    }
  }
  // No title matched any filter label. Fall back to lowest-id filter.
  return departments[0];
}

async function main() {
  console.log(
    `Starting SEAS Faculty Directory scraper (two-pass, writing to ${OUTPUT_PATH.replace(
      /^.*\/data\//,
      "data/",
    )})...\n`,
  );

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();

  // ---------- Discovery: filter IDs ----------
  console.log(`Fetching ${FACULTY_URL} (filter dropdown)...`);
  await page.goto(FACULTY_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector('select.filter_tool_select[name="department"]');
  const filters = await scrapeFilterOptions(page);
  // Sort by numeric id ascending — stable ordering for primary-dept tiebreak.
  filters.sort((a, b) => parseInt(a.id, 10) - parseInt(b.id, 10));
  console.log(`Discovered ${filters.length} department filters.\n`);

  const bySlug = new Map<string, Partial<ScrapedLab>>();

  if (!ONLY_FILTER) {
    // ---------- Pass A: unfiltered (coverage) ----------
    console.log("Pass A — unfiltered /faculty paging:");
    const unfilteredCards = await scrapePaginated(
      page,
      (p) => `${FACULTY_URL}?page=${p}`,
    );
    console.log(`  ${unfilteredCards.length} cards (with duplicates)`);
    for (const c of unfilteredCards) {
      if (c.slug && !bySlug.has(c.slug)) bySlug.set(c.slug, c);
    }
    console.log(`  ${bySlug.size} unique faculty\n`);
  } else {
    console.log(`Skipping Pass A — --only=${ONLY_FILTER} restricts to single filter\n`);
  }

  // ---------- Pass B: per-filter tagging ----------
  const filtersToUse = ONLY_FILTER
    ? filters.filter((f) => f.id === ONLY_FILTER)
    : filters;
  if (ONLY_FILTER && filtersToUse.length === 0) {
    console.error(`--only=${ONLY_FILTER} did not match any discovered filter id.`);
    process.exit(1);
  }
  console.log(`Pass B — per-department filters${ONLY_FILTER ? ` (--only=${ONLY_FILTER})` : ""}:`);
  const deptsBySlug = new Map<string, Set<string>>();
  for (const f of filtersToUse) {
    const cards = await scrapePaginated(
      page,
      (p) => `${FACULTY_URL}?department=${f.id}&page=${p}`,
    );
    const uniqueSlugs = new Set<string>();
    for (const c of cards) {
      if (!c.slug) continue;
      uniqueSlugs.add(c.slug);
      if (!deptsBySlug.has(c.slug)) deptsBySlug.set(c.slug, new Set());
      deptsBySlug.get(c.slug)!.add(f.label);
      // If Pass A missed this slug (e.g., late additions), capture it.
      if (!bySlug.has(c.slug)) bySlug.set(c.slug, c);
    }
    console.log(`  ${f.label.padEnd(42)} ${uniqueSlugs.size}`);
  }

  // ---------- Merge ----------
  const output: Partial<ScrapedLab>[] = [];
  let filterCount = 0;
  let fallbackCount = 0;
  for (const [slug, card] of bySlug.entries()) {
    const deptSet = deptsBySlug.get(slug);
    const deptsArr = deptSet ? [...deptSet].sort() : [];
    let primary: string;
    let source: "filter" | "fallback_title";
    if (deptsArr.length > 0) {
      primary = pickPrimaryDepartment(card.titles || [], deptsArr);
      source = "filter";
      filterCount++;
    } else {
      primary = departmentFromTitles(card.titles || []);
      source = "fallback_title";
      fallbackCount++;
    }
    output.push({
      ...card,
      slug,
      department: primary,
      departments: deptsArr,
      departmentSource: source,
    });
  }

  // Sort output by slug for deterministic file contents (friendly diffs).
  output.sort((a, b) => (a.slug || "").localeCompare(b.slug || ""));

  // ---------- Summary ----------
  console.log("\n--- Summary ---");
  console.log(`Total unique faculty: ${output.length}`);
  console.log(`  filter-tagged:        ${filterCount}`);
  console.log(`  fallback_title:       ${fallbackCount}`);
  const recruiting = output.filter((x) => x.isRecruiting);
  console.log(`Currently recruiting:   ${recruiting.length}`);

  // Flag any fallback with empty department (worst case — manual review)
  const emptyDept = output.filter(
    (x) => x.departmentSource === "fallback_title" && !x.department,
  );
  if (emptyDept.length) {
    console.warn(
      `\nWARNING: ${emptyDept.length} faculty have no department tag from filter OR title fallback:`,
    );
    emptyDept.forEach((x) => console.warn(`  ${x.professorName} (${x.slug})`));
  }

  writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));
  console.log(`\nSaved to ${OUTPUT_PATH}`);

  await browser.close();
}

main().catch((err) => {
  console.error("Scraper failed:", err);
  process.exit(1);
});
