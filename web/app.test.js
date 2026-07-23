// Minimal, deliberately narrow suite (dec. #42): only the spots agreed worth
// automated coverage for a static, no-backend, single-user tool — escaping,
// portfolio URL scheme validation, and the PromptReady gate's branch states.
// Sort order, CSV formatting, and DOM/visual details are NOT covered here on
// purpose; see docs/decision_log.md dec. #42 for why.
import { describe, expect, it, beforeEach } from "vitest";
import { state, isValidPortfolioUrl, computePromptGate, renderRow } from "./app.js";

const baseEmployer = {
  employer: "ACME",
  employer_display: "Acme Design LLC",
  filing_count: 3,
  quarters: "FY2025Q4",
  repeat_sponsor: "no",
  soc_titles: "Graphic Designers",
  worksite_states: "TX",
  wage_annual_median: 90000,
};

beforeEach(() => {
  state.selected = new Set();
});

describe("renderRow escaping (the v0 M13 lesson)", () => {
  it("renders a hostile employer_display as inert text, never a live element", () => {
    const hostile = '<img src=x onerror="window.__pwned = true">';
    const tr = renderRow({ ...baseEmployer, employer_display: hostile });

    // The link's visible text is the raw hostile string, unexecuted...
    const link = tr.querySelector("td a");
    expect(link.textContent).toBe(hostile);
    // ...and no such element was actually parsed into the tree from it. (Note:
    // checking the whole row's innerHTML for a literal "<img" would false-positive
    // — the checkbox's aria-label attribute legitimately contains that substring
    // as inert attribute-value text, which HTML never re-parses as markup.)
    expect(tr.querySelector("img")).toBeNull();
    expect(link.innerHTML).not.toContain("<img");
  });

  it("renders a hostile soc_titles as inert text", () => {
    const hostile = '<script>window.__pwned = true</script>';
    const tr = renderRow({ ...baseEmployer, soc_titles: hostile });

    const cells = tr.querySelectorAll("td");
    const socCell = cells[5]; // Target?, Company, Filings, Quarters, Repeat, SOC titles
    expect(socCell.textContent).toBe(hostile);
    expect(tr.querySelector("script")).toBeNull();
  });

  it("URL-encodes a hostile employer_display in the careers-search href", () => {
    const hostile = '"><script>alert(1)</script>';
    const tr = renderRow({ ...baseEmployer, employer_display: hostile });
    const href = tr.querySelector("td a").getAttribute("href");
    expect(href).not.toContain("<script>");
    expect(href).toContain(encodeURIComponent(hostile));
  });
});

describe("isValidPortfolioUrl (dec. #38/#42)", () => {
  it("accepts http and https", () => {
    expect(isValidPortfolioUrl("https://example.com")).toBe(true);
    expect(isValidPortfolioUrl("http://example.com")).toBe(true);
  });

  it("rejects javascript: and data: schemes", () => {
    expect(isValidPortfolioUrl("javascript:alert(1)")).toBe(false);
    expect(isValidPortfolioUrl("data:text/html,<script>alert(1)</script>")).toBe(false);
  });

  it("rejects a bare domain with no scheme", () => {
    expect(isValidPortfolioUrl("example.com")).toBe(false);
  });

  it("rejects empty input", () => {
    expect(isValidPortfolioUrl("")).toBe(false);
  });
});

describe("computePromptGate branch states (dec. #41)", () => {
  const cases = [
    {
      name: "nothing at all",
      input: { portfolioRaw: "", portfolioValid: false, resumePath: "" },
      expectMissingCount: 1,
    },
    {
      name: "valid portfolio only",
      input: { portfolioRaw: "https://x.com", portfolioValid: true, resumePath: "" },
      expectMissingCount: 0,
    },
    {
      name: "résumé path only, empty portfolio",
      input: { portfolioRaw: "", portfolioValid: false, resumePath: "/tmp/r.pdf" },
      expectMissingCount: 0,
    },
    {
      name: "both present",
      input: { portfolioRaw: "https://x.com", portfolioValid: true, resumePath: "/tmp/r.pdf" },
      expectMissingCount: 0,
    },
    {
      name: "invalid portfolio text, no résumé",
      input: { portfolioRaw: "not a url", portfolioValid: false, resumePath: "" },
      expectMissingCount: 1,
    },
    {
      name: "invalid portfolio text, résumé present too",
      input: { portfolioRaw: "not a url", portfolioValid: false, resumePath: "/tmp/r.pdf" },
      expectMissingCount: 1, // portfolio typo still blocks even though résumé alone would satisfy the OR
    },
  ];

  for (const { name, input, expectMissingCount } of cases) {
    it(name, () => {
      const { missing } = computePromptGate(input);
      expect(missing.length).toBe(expectMissingCount);
    });
  }

  // Targeting is optional: the gate must never mention company selection, at any
  // selection count. This is the regression pin for "generate with no targets."
  it("never blocks on company selection", () => {
    for (const selectedCount of [0, 1, 3]) {
      const { missing } = computePromptGate({
        portfolioRaw: "https://x.com", portfolioValid: true, resumePath: "", selectedCount,
      });
      expect(missing).toEqual([]);
    }
  });

  it("flags portfolioInvalid only when non-empty text fails validation", () => {
    expect(computePromptGate({
      portfolioRaw: "not a url", portfolioValid: false, resumePath: "",
    }).portfolioInvalid).toBe(true);
    expect(computePromptGate({
      portfolioRaw: "", portfolioValid: false, resumePath: "",
    }).portfolioInvalid).toBe(false);
  });

  it("does not fall through to the OR message when portfolio text is present but invalid", () => {
    const { missing } = computePromptGate({
      portfolioRaw: "not a url", portfolioValid: false, resumePath: "",
    });
    expect(missing).toContain("fix your portfolio link (https://…)");
    expect(missing).not.toContain("add a portfolio link or a résumé path — at least one");
  });
});
