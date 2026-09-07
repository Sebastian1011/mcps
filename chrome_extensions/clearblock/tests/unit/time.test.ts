import {describe, expect, it} from "vitest";
import {dateFromEpochSeconds} from "../../src/shared/time";

describe("filter subscription timestamps", () => {
  it("converts Unix seconds to JavaScript milliseconds", () => {
    expect(dateFromEpochSeconds(1_788_220_800).toISOString()).toBe("2026-09-01T00:00:00.000Z");
  });
});
