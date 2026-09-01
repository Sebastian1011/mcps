import {describe, expect, it, vi} from "vitest";
import {
  canonicalPageUrl,
  classifyUserFilters,
  createAllowlistRule,
  createElementRule,
  hostnameFromInput,
  pageExceptionFilter,
  siteExceptionFilter
} from "../../src/shared/filters";

describe("URL normalization", () => {
  it("removes fragments but preserves queries", () => {
    expect(canonicalPageUrl("https://Example.com/a?x=1#section").href)
      .toBe("https://example.com/a?x=1");
  });

  it("rejects browser and extension pages", () => {
    expect(() => canonicalPageUrl("chrome://settings/")).toThrow();
    expect(() => canonicalPageUrl("file:///tmp/test.html")).toThrow();
  });

  it("accepts either a hostname or a URL for site entries", () => {
    expect(hostnameFromInput("News.Example.com")).toBe("news.example.com");
    expect(hostnameFromInput("https://例子.测试/path")).toBe("xn--fsqu00a.xn--0zwm56d");
  });
});

describe("filter generation", () => {
  it("creates a site rule that includes subdomains", () => {
    expect(siteExceptionFilter("news.example.com"))
      .toBe("@@||news.example.com^$document");
  });

  it("creates an anchored exact-page regex", () => {
    expect(pageExceptionFilter("https://example.com/a?x=1#ignored"))
      .toBe("@@/^https:\\/\\/example\\.com\\/a\\?x=1$/$document");
  });

  it("adds ClearBlock metadata", () => {
    vi.spyOn(Date, "now").mockReturnValue(42);
    const result = createAllowlistRule("site", "example.com");
    expect(result.metadata.clearBlock).toEqual({
      kind: "allowlist",
      scope: "site",
      value: "example.com",
      hostname: "example.com",
      createdAt: 42
    });
    vi.restoreAllMocks();
  });

  it("creates domain-scoped element rules and rejects newlines", () => {
    expect(createElementRule("https://example.com/path", ".sponsor").filterText)
      .toBe("example.com##.sponsor");
    expect(() => createElementRule("https://example.com", ".ad\nbody"))
      .toThrow();
  });
});

describe("user filter classification", () => {
  it("ignores unrelated filters and sorts managed rules newest-first", () => {
    const result = classifyUserFilters([
      {text: "||ads.example^"},
      {
        text: "example.com##.ad",
        metadata: {clearBlock: {kind: "element", value: ".ad", hostname: "example.com", createdAt: 2}}
      },
      {
        text: "@@||example.com^$document",
        metadata: {clearBlock: {kind: "allowlist", scope: "site", value: "example.com", hostname: "example.com", createdAt: 3}}
      }
    ]);
    expect(result.allowlist).toHaveLength(1);
    expect(result.elementRules).toHaveLength(1);
    expect(result.allowlist[0]?.value).toBe("example.com");
  });
});
