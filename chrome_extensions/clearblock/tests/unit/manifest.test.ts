import {readFile} from "node:fs/promises";
import path from "node:path";
import {describe, expect, it} from "vitest";

const root = path.resolve(import.meta.dirname, "../..");

describe("built extension", () => {
  it("uses Manifest V3 with the required local-only entry points", async () => {
    const manifest = JSON.parse(await readFile(path.join(root, "dist/manifest.json"), "utf8"));
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.background).toEqual({service_worker: "background.js"});
    expect(manifest.permissions).not.toContain("declarativeNetRequestFeedback");
    expect(manifest.host_permissions).toEqual(["http://*/*", "https://*/*"]);
    expect(manifest.declarative_net_request.rule_resources).toHaveLength(3);
    expect(manifest.declarative_net_request.rule_resources.every((rule: {enabled: boolean}) => rule.enabled))
      .toBe(true);
  });

  it("contains no remote script references", async () => {
    for (const file of ["popup.html", "options.html"]) {
      const html = await readFile(path.join(root, "dist", file), "utf8");
      expect(html).not.toMatch(/<script[^>]+https?:/i);
    }
  });
});
