/**
 * Phase 3: Load scraped lab data from labs.json into Supabase.
 * Upserts on slug to avoid duplicates on re-runs.
 *
 * Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars.
 *
 * Usage: npx tsx scripts/lab_scraper/load-to-supabase.ts
 * Input: scripts/lab_scraper/data/labs.json
 */

import { createClient } from "@supabase/supabase-js";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import type { ScrapedLab } from "./types";

const USE_NEW = process.argv.includes("--new");
const LABS_PATH = resolve(
  __dirname,
  USE_NEW ? "data/labs_new.json" : "data/labs.json",
);

function getEnvOrDie(key: string): string {
  const val = process.env[key];
  if (!val) {
    console.error(`Missing env var: ${key}`);
    console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY");
    process.exit(1);
  }
  return val;
}

async function main() {
  if (!existsSync(LABS_PATH)) {
    console.error(
      `${LABS_PATH.replace(/^.*\/data\//, "data/")} not found. Run scrape-listing then scrape-profiles first${USE_NEW ? " with --new" : ""}.`,
    );
    process.exit(1);
  }

  const supabaseUrl = getEnvOrDie("SUPABASE_URL");
  const supabaseKey = getEnvOrDie("SUPABASE_SERVICE_ROLE_KEY");

  const supabase = createClient(supabaseUrl, supabaseKey);

  const labs: ScrapedLab[] = JSON.parse(readFileSync(LABS_PATH, "utf-8"));
  console.log(`Loaded ${labs.length} labs from labs.json`);

  let upserted = 0;
  let errors = 0;

  for (const lab of labs) {
    const row = {
      slug: lab.slug,
      name: lab.labAffiliation
        ? `${lab.labAffiliation}`
        : `${lab.professorName} Lab`,
      professor_name: lab.professorName,
      department: lab.department,
      titles: lab.titles,
      research_area: lab.researchInterests[0] || lab.department,
      research_areas: lab.researchInterests,
      description: lab.researchDescription || lab.descriptionSnippet || "",
      website_url: lab.websiteUrl || "",
      email: lab.email,
      phone: lab.phone,
      office_location: lab.officeLocation,
      lab_affiliation: lab.labAffiliation,
      google_scholar_url: lab.googleScholarUrl,
      github_url: lab.githubUrl,
      profile_image_url: lab.photoUrl,
      seas_profile_url: lab.profileUrl,
      social_links: lab.socialLinks,
      research_interests: lab.researchInterests,
      research_description: lab.researchDescription,
      education: lab.education,
      is_recruiting: lab.isRecruiting,
      last_scraped_at: new Date().toISOString(),
    };

    const { error } = await supabase
      .from("labs")
      .upsert(row, { onConflict: "slug" });

    if (error) {
      console.error(`  ERROR upserting ${lab.slug}:`, error.message);
      errors++;
    } else {
      upserted++;
    }
  }

  console.log(`\nDone! ${upserted} upserted, ${errors} errors.`);
}

main().catch((err) => {
  console.error("Loader failed:", err);
  process.exit(1);
});
