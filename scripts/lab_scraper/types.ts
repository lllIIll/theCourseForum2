export interface ScrapedLab {
  professorName: string;
  slug: string;
  profileUrl: string;
  titles: string[];
  department: string;
  /**
   * Every SEAS department filter this faculty member was found under.
   * Joint/courtesy appointments populate multiple entries. Empty when the
   * faculty is not categorized by any SEAS filter (Med-school joint
   * appointments etc.); in that case `department` comes from title parsing.
   */
  departments: string[];
  /**
   * How `department` was determined:
   *   "filter"          — at least one SEAS department filter tagged them
   *   "fallback_title"  — faculty absent from every filter, dept parsed
   *                       from title strings
   */
  departmentSource: "filter" | "fallback_title";
  isRecruiting: boolean;
  photoUrl: string | null;
  descriptionSnippet: string;
  externalLinks: { label: string; url: string }[];

  // From individual profile page (Phase 2)
  email: string | null;
  phone: string | null;
  officeLocation: string | null;
  labAffiliation: string | null;
  googleScholarUrl: string | null;
  githubUrl: string | null;
  websiteUrl: string | null;
  socialLinks: { platform: string; url: string }[];
  researchInterests: string[];
  researchDescription: string | null;
  education: { raw: string }[];
}
