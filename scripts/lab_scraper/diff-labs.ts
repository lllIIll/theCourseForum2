/**
 * Safety gate: diff a freshly scraped labs_new.json against the current
 * Supabase `labs` table (also saved as data/supabase-snapshot.json for
 * rollback). Prints added/removed/changed slugs and highlights changes to
 * high-signal fields (is_recruiting, department, email).
 *
 * Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY
 * is enough for read).
 *
 * Usage: npx tsx scripts/lab_scraper/diff-labs.ts
 * Inputs:
 *   data/labs_new.json          (produced by scrape-profiles --new)
 * Outputs:
 *   data/supabase-snapshot.json (current table state; commit-bypass backup)
 *   stdout diff report
 */

import { createClient } from "@supabase/supabase-js";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve } from "path";

const NEW_PATH = resolve(__dirname, "data/labs_new.json");
const SNAPSHOT_PATH = resolve(__dirname, "data/supabase-snapshot.json");
const HIGH_SIGNAL = ["is_recruiting", "department", "email"] as const;

function envOrDie(key: string): string {
  const v = process.env[key];
  if (!v) {
    console.error(`Missing env var: ${key}`);
    process.exit(1);
  }
  return v;
}

async function pullSupabaseLabs(): Promise<Record<string, any>[]> {
  const url = envOrDie("SUPABASE_URL");
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    envOrDie("SUPABASE_SERVICE_ROLE_KEY");
  const client = createClient(url, key);
  const all: Record<string, any>[] = [];
  const pageSize = 1000;
  for (let start = 0; ; start += pageSize) {
    const { data, error } = await client
      .from("labs")
      .select("*")
      .order("professor_name", { ascending: true })
      .range(start, start + pageSize - 1);
    if (error) throw error;
    if (!data || data.length === 0) break;
    all.push(...data);
    if (data.length < pageSize) break;
  }
  return all;
}

function diffSets(a: Set<string>, b: Set<string>) {
  const onlyA = [...a].filter((x) => !b.has(x)).sort();
  const onlyB = [...b].filter((x) => !a.has(x)).sort();
  return { onlyA, onlyB };
}

function valueEquals(a: any, b: any): boolean {
  if (a === b) return true;
  if (a == null && b == null) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    const sa = [...a].sort();
    const sb = [...b].sort();
    return sa.every((v, i) => valueEquals(v, sb[i]));
  }
  if (typeof a === "object" && typeof b === "object") {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return false;
}

/** Map ScrapedLab -> the subset of Supabase fields we care to diff. */
function scrapedToSupabase(s: any): Record<string, any> {
  return {
    slug: s.slug,
    professor_name: s.professorName,
    department: s.department,
    is_recruiting: !!s.isRecruiting,
    email: s.email ?? null,
    phone: s.phone ?? null,
    office_location: s.officeLocation ?? null,
    google_scholar_url: s.googleScholarUrl ?? null,
    github_url: s.githubUrl ?? null,
    website_url: s.websiteUrl ?? null,
    profile_image_url: s.photoUrl ?? null,
    seas_profile_url: s.profileUrl?.startsWith("http")
      ? s.profileUrl
      : `https://engineering.virginia.edu${s.profileUrl}`,
    research_description: s.researchDescription ?? null,
  };
}

async function main() {
  if (!existsSync(NEW_PATH)) {
    console.error(`${NEW_PATH} not found. Run scrape-listing.ts --new then scrape-profiles.ts --new first.`);
    process.exit(1);
  }

  console.log("Pulling current Supabase `labs` table...");
  const current = await pullSupabaseLabs();
  writeFileSync(SNAPSHOT_PATH, JSON.stringify(current, null, 2));
  console.log(`  ${current.length} rows -> ${SNAPSHOT_PATH}\n`);

  const incoming: any[] = JSON.parse(readFileSync(NEW_PATH, "utf8"));
  console.log(`Incoming: ${incoming.length} rows from labs_new.json\n`);

  const currentBySlug = new Map(current.map((r) => [r.slug as string, r]));
  const incomingBySlug = new Map(
    incoming.map((r) => [r.slug as string, scrapedToSupabase(r)]),
  );

  const { onlyA: removedSlugs, onlyB: addedSlugs } = diffSets(
    new Set(currentBySlug.keys()),
    new Set(incomingBySlug.keys()),
  );

  console.log("--- Added (new in incoming) ---");
  addedSlugs.forEach((s) => {
    const r = incomingBySlug.get(s)!;
    console.log(`  + ${s.padEnd(36)} ${r.department || "?"}  ${r.is_recruiting ? "[RECRUITING]" : ""}`);
  });
  console.log(`  total: ${addedSlugs.length}\n`);

  console.log("--- Removed (in current, not in incoming) ---");
  removedSlugs.forEach((s) => {
    const r = currentBySlug.get(s)!;
    console.log(`  - ${s.padEnd(36)} ${r.department || "?"}  ${r.is_recruiting ? "[was RECRUITING]" : ""}`);
  });
  console.log(`  total: ${removedSlugs.length}\n`);

  console.log("--- Changed (high-signal fields) ---");
  let changedCount = 0;
  const fieldChangeTallies: Record<string, number> = {};
  for (const [slug, incoming] of incomingBySlug.entries()) {
    const curr = currentBySlug.get(slug);
    if (!curr) continue;
    const changes: { field: string; from: any; to: any }[] = [];
    for (const field of HIGH_SIGNAL) {
      if (!valueEquals(curr[field], incoming[field])) {
        changes.push({ field, from: curr[field], to: incoming[field] });
        fieldChangeTallies[field] = (fieldChangeTallies[field] || 0) + 1;
      }
    }
    if (changes.length) {
      changedCount++;
      console.log(`  ~ ${slug}`);
      changes.forEach((c) =>
        console.log(`      ${c.field}: ${JSON.stringify(c.from)}  ->  ${JSON.stringify(c.to)}`),
      );
    }
  }
  console.log(`  total rows w/ high-signal change: ${changedCount}`);
  Object.entries(fieldChangeTallies).forEach(([f, n]) =>
    console.log(`  ${f}: ${n} changes`),
  );

  console.log("\n--- Recruiting delta ---");
  const currRecruiting = current.filter((r) => r.is_recruiting).length;
  const incRecruiting = [...incomingBySlug.values()].filter(
    (r) => r.is_recruiting,
  ).length;
  console.log(`  current:  ${currRecruiting}`);
  console.log(`  incoming: ${incRecruiting}`);
  console.log(`  net:      ${incRecruiting - currRecruiting >= 0 ? "+" : ""}${incRecruiting - currRecruiting}`);

  console.log("\nReview this diff BEFORE running load-to-supabase.ts.");
}

main().catch((e) => {
  console.error("diff-labs failed:", e);
  process.exit(1);
});
