/**
 * Phase 2: Scrape individual SEAS faculty profile pages.
 * Reads listing.json, fetches each profile, enriches with full details.
 *
 * Usage: npx tsx scripts/lab_scraper/scrape-profiles.ts
 * Input:  scripts/lab_scraper/data/listing.json
 * Output: scripts/lab_scraper/data/labs.json
 */

import { chromium, type Page } from "playwright";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve } from "path";
import type { ScrapedLab } from "./types";

const BASE_URL = "https://engineering.virginia.edu";
const DELAY_MS = 1500;
const USE_NEW = process.argv.includes("--new");
const LISTING_PATH = resolve(
  __dirname,
  USE_NEW ? "data/listing_new.json" : "data/listing.json",
);
const OUTPUT_PATH = resolve(
  __dirname,
  USE_NEW ? "data/labs_new.json" : "data/labs.json",
);
const PROGRESS_PATH = resolve(
  __dirname,
  USE_NEW ? "data/.progress_new.json" : "data/.progress.json",
);

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Helper to get text content from a locator, returns null if not found */
async function textOrNull(page: Page, selector: string): Promise<string | null> {
  const el = page.locator(selector).first();
  if ((await el.count()) === 0) return null;
  const text = await el.textContent();
  return text?.trim() || null;
}

/** Helper to get href from a locator, returns null if not found */
async function hrefOrNull(page: Page, selector: string): Promise<string | null> {
  const el = page.locator(selector).first();
  if ((await el.count()) === 0) return null;
  return await el.getAttribute("href");
}

/** Helper to get all text contents from a selector */
async function allTexts(page: Page, selector: string): Promise<string[]> {
  const els = page.locator(selector);
  const count = await els.count();
  const results: string[] = [];
  for (let i = 0; i < count; i++) {
    const text = await els.nth(i).textContent();
    if (text?.trim()) results.push(text.trim());
  }
  return results;
}

async function scrapeProfile(
  page: Page,
  url: string
): Promise<Partial<ScrapedLab>> {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

  // Email — Cloudflare may protect it, but Playwright renders decoded DOM
  const email = await textOrNull(
    page,
    ".desktop_meta .people_meta_detail_item.email .people_meta_detail_info_link"
  );

  // Phone
  const phone = await textOrNull(
    page,
    '.desktop_meta .people_meta_detail_info_link[href^="tel:"]'
  );

  // Location
  const officeLocation = await textOrNull(
    page,
    ".desktop_meta .people_meta_detail.location .people_meta_detail_info"
  );

  // Lab affiliation
  const labAffiliation = await textOrNull(
    page,
    ".desktop_meta .people_meta_detail.lab .people_meta_detail_info"
  );

  // Social links
  const socialLinkEls = page.locator(".desktop_meta .people_meta_social_link");
  const socialCount = await socialLinkEls.count();
  const socialLinks: { platform: string; url: string }[] = [];
  for (let i = 0; i < socialCount; i++) {
    const el = socialLinkEls.nth(i);
    const platform = await el.locator(".people_meta_social_link_label").textContent();
    const href = await el.getAttribute("href");
    if (platform && href) {
      socialLinks.push({ platform: platform.trim(), url: href });
    }
  }

  // External links
  const extLinkEls = page.locator(".people_entry_links a.people_entry_link");
  const extCount = await extLinkEls.count();
  let googleScholarUrl: string | null = null;
  let githubUrl: string | null = null;
  let websiteUrl: string | null = null;

  for (let i = 0; i < extCount; i++) {
    const el = extLinkEls.nth(i);
    const href = await el.getAttribute("href");
    const label = await el.locator(".people_entry_link_label").textContent();
    if (!href) continue;

    if (href.includes("scholar.google.com")) {
      googleScholarUrl = href;
    } else if (href.includes("github.com")) {
      githubUrl = href;
    } else if (
      label?.includes("Personal Website") ||
      label?.toLowerCase().includes("website")
    ) {
      websiteUrl = href;
    } else if (
      !websiteUrl &&
      !href.includes("engineering.virginia.edu")
    ) {
      websiteUrl = href;
    }
  }

  // Research interests — only from the "Research Interests" grid, not courses/awards
  const researchInterests: string[] = [];
  const gridSections = page.locator(".directory_grid");
  const gridCount = await gridSections.count();
  for (let i = 0; i < gridCount; i++) {
    const title = await gridSections.nth(i).locator(".directory_grid_title").textContent();
    if (title?.trim().toLowerCase() === "research interests") {
      const items = gridSections.nth(i).locator(".directory_grid_item");
      const itemCount = await items.count();
      for (let j = 0; j < itemCount; j++) {
        // Get only the first text node (the interest name), not nested semester info
        const text = await items.nth(j).evaluate((el) => {
          const firstChild = el.childNodes[0];
          if (!firstChild) return null;
          // Walk to find a text-bearing element
          const inner = el.querySelector(".directory_grid_item_label");
          if (inner) return inner.textContent?.trim() || null;
          return el.textContent?.trim()?.split("\n")[0]?.trim() || null;
        });
        if (text) researchInterests.push(text);
      }
      break;
    }
  }

  // Research description — try About section first, then testimonial quote
  const testimonialQuote = await textOrNull(page, "blockquote.testimonial_quote p");

  // For About section and Education, use a single evaluate with a plain function string
  // to avoid tsx __name injection issues
  const typographySections = await page.evaluate(`
    (function() {
      var result = { about: null, education: [] };
      var el = document.querySelector('.typography');
      if (!el) return result;
      var headings = el.querySelectorAll('h2');
      for (var i = 0; i < headings.length; i++) {
        var h = headings[i];
        var title = (h.textContent || '').trim().toLowerCase();
        if (title === 'about') {
          var paragraphs = [];
          var sib = h.nextElementSibling;
          while (sib && sib.tagName !== 'H2') {
            if (sib.tagName === 'P') paragraphs.push((sib.textContent || '').trim());
            sib = sib.nextElementSibling;
          }
          result.about = paragraphs.join('\\n\\n') || null;
        }
        if (title === 'education') {
          var sib2 = h.nextElementSibling;
          while (sib2 && sib2.tagName !== 'H2') {
            if (sib2.tagName === 'P' || sib2.tagName === 'LI') {
              var t = (sib2.textContent || '').trim();
              if (t) result.education.push({ raw: t });
            }
            if (sib2.tagName === 'UL' || sib2.tagName === 'OL') {
              var lis = sib2.querySelectorAll('li');
              for (var j = 0; j < lis.length; j++) {
                var lt = (lis[j].textContent || '').trim();
                if (lt) result.education.push({ raw: lt });
              }
            }
            sib2 = sib2.nextElementSibling;
          }
        }
      }
      return result;
    })()
  `) as { about: string | null; education: { raw: string }[] };

  const researchDescription = typographySections.about || testimonialQuote || null;
  const education = typographySections.education || [];

  return {
    email,
    phone,
    officeLocation,
    labAffiliation,
    googleScholarUrl,
    githubUrl,
    websiteUrl,
    socialLinks,
    researchInterests,
    researchDescription,
    education,
  };
}

async function main() {
  if (!existsSync(LISTING_PATH)) {
    console.error(
      "listing.json not found. Run scrape-listing.ts first."
    );
    process.exit(1);
  }

  const listing: Partial<ScrapedLab>[] = JSON.parse(
    readFileSync(LISTING_PATH, "utf-8")
  );
  console.log(`Loaded ${listing.length} faculty from listing.json`);

  // Load progress if resuming
  let completed = new Set<string>();
  let results: ScrapedLab[] = [];
  if (existsSync(PROGRESS_PATH)) {
    const progress = JSON.parse(readFileSync(PROGRESS_PATH, "utf-8"));
    completed = new Set(progress.completed || []);
    results = progress.results || [];
    console.log(`Resuming: ${completed.size} already scraped`);
  }

  const remaining = listing.filter((f) => !completed.has(f.slug!));
  console.log(`${remaining.length} profiles to scrape\n`);

  if (remaining.length === 0) {
    console.log("All profiles already scraped. Writing final output.");
    writeFileSync(OUTPUT_PATH, JSON.stringify(results, null, 2));
    console.log(`Saved to ${OUTPUT_PATH}`);
    return;
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();

  for (let i = 0; i < remaining.length; i++) {
    const faculty = remaining[i];
    const url = `${BASE_URL}${faculty.profileUrl}`;
    const progress = `[${completed.size + 1}/${listing.length}]`;

    console.log(`${progress} ${faculty.professorName} — ${url}`);

    try {
      const profile = await scrapeProfile(page, url);

      const merged: ScrapedLab = {
        professorName: faculty.professorName || "",
        slug: faculty.slug || "",
        profileUrl: `${BASE_URL}${faculty.profileUrl}`,
        titles: faculty.titles || [],
        department: faculty.department || "",
        departments: faculty.departments || [],
        departmentSource: faculty.departmentSource || "fallback_title",
        isRecruiting: faculty.isRecruiting || false,
        photoUrl: faculty.photoUrl
          ? faculty.photoUrl.startsWith("http")
            ? faculty.photoUrl
            : `${BASE_URL}${faculty.photoUrl}`
          : null,
        descriptionSnippet: faculty.descriptionSnippet || "",
        externalLinks: faculty.externalLinks || [],
        email: profile.email || null,
        phone: profile.phone || null,
        officeLocation: profile.officeLocation || null,
        labAffiliation: profile.labAffiliation || null,
        googleScholarUrl: profile.googleScholarUrl || null,
        githubUrl: profile.githubUrl || null,
        websiteUrl: profile.websiteUrl || null,
        socialLinks: profile.socialLinks || [],
        researchInterests: profile.researchInterests || [],
        researchDescription: profile.researchDescription || null,
        education: profile.education || [],
      };

      results.push(merged);
      completed.add(faculty.slug!);

      // Save progress every 10 profiles
      if (completed.size % 10 === 0) {
        writeFileSync(
          PROGRESS_PATH,
          JSON.stringify(
            { completed: Array.from(completed), results },
            null,
            2
          )
        );
        console.log(`  [checkpoint saved: ${completed.size} done]`);
      }
    } catch (err) {
      console.error(`  ERROR scraping ${faculty.slug}:`, err);
    }

    if (i < remaining.length - 1) {
      await sleep(DELAY_MS);
    }
  }

  await browser.close();

  // Final output
  writeFileSync(OUTPUT_PATH, JSON.stringify(results, null, 2));
  console.log(`\nDone! ${results.length} faculty profiles saved to ${OUTPUT_PATH}`);

  // Stats
  const recruiting = results.filter((r) => r.isRecruiting);
  const withEmail = results.filter((r) => r.email);
  const withScholar = results.filter((r) => r.googleScholarUrl);
  console.log(`\nStats:`);
  console.log(`  Recruiting: ${recruiting.length}`);
  console.log(`  With email: ${withEmail.length}`);
  console.log(`  With Google Scholar: ${withScholar.length}`);
  console.log(`  With research interests: ${results.filter((r) => r.researchInterests.length > 0).length}`);

  // Clean up progress file
  if (existsSync(PROGRESS_PATH)) {
    const { unlinkSync } = require("fs");
    unlinkSync(PROGRESS_PATH);
  }
}

main().catch((err) => {
  console.error("Scraper failed:", err);
  process.exit(1);
});
