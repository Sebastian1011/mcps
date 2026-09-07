import {describe, expect, it} from "vitest";
import {
  decodeSyncSnapshot,
  encodeSyncSnapshot,
  mergeSyncedRules,
  type SyncedUserRule
} from "../../src/shared/sync";

const siteRule: SyncedUserRule = {
  filterText: "@@||example.com^$document",
  metadata: {
    kind: "allowlist",
    scope: "site",
    value: "example.com",
    hostname: "example.com",
    createdAt: 10
  }
};

describe("sync snapshot encoding", () => {
  it("round trips Unicode data using quota-safe chunks", () => {
    const unicodeRules = [1, 2, 3].map(index => {
      const selector = `[aria-label='广告${index}']`.repeat(80);
      return {
        filterText: `xn--fsqu00a.xn--0zwm56d##${selector}`,
        metadata: {
          kind: "element" as const,
          value: selector,
          hostname: "xn--fsqu00a.xn--0zwm56d",
          createdAt: 20 + index
        }
      };
    });
    const rules = [siteRule, ...unicodeRules];
    const encoded = encodeSyncSnapshot(rules, 42);

    expect(encoded.manifest).toEqual({version: 1, chunkCount: encoded.chunks.length, updatedAt: 42});
    expect(encoded.chunks.length).toBeGreaterThan(1);
    expect(encoded.chunks.every(chunk => new TextEncoder().encode(chunk).byteLength < 8_000)).toBe(true);
    expect(decodeSyncSnapshot(encoded.manifest, encoded.chunks)).toEqual({
      version: 1,
      updatedAt: 42,
      rules
    });
  });

  it("rejects missing chunks and malformed managed rules", () => {
    const encoded = encodeSyncSnapshot([siteRule], 42);
    expect(() => decodeSyncSnapshot(encoded.manifest, [])).toThrow("incomplete");

    const malformed = encodeSyncSnapshot([{
      ...siteRule,
      metadata: {...siteRule.metadata, kind: "unknown"}
    } as unknown as SyncedUserRule], 42);
    expect(() => decodeSyncSnapshot(malformed.manifest, malformed.chunks)).toThrow("invalid");
  });
});

describe("sync rule merge", () => {
  it("deduplicates by filter text and keeps newer metadata", () => {
    const newer = {...siteRule, metadata: {...siteRule.metadata, createdAt: 99}};
    const element: SyncedUserRule = {
      filterText: "example.com##.sponsor",
      metadata: {kind: "element", value: ".sponsor", hostname: "example.com", createdAt: 50}
    };

    expect(mergeSyncedRules([siteRule, element], [newer])).toEqual([newer, element]);
  });
});
