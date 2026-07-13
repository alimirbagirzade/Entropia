import { describe, expect, it } from "vitest";

import { buildTradeLogPayloadTemplate, mappingHashFromSummary, parseColumnMapping } from "@/lib/tradeLog";
import { buildSignalPayloadTemplate } from "@/lib/tradingSignal";

describe("parseColumnMapping", () => {
  it("parses canonical=source lines, trimming whitespace", () => {
    expect(parseColumnMapping("entry_time = Open Time\nexit_time=Close Time")).toEqual({
      entry_time: "Open Time",
      exit_time: "Close Time",
    });
  });

  it("ignores blank lines and lines without '='", () => {
    expect(parseColumnMapping("\ndirection = side\njust a comment\n  \n")).toEqual({
      direction: "side",
    });
  });

  it("skips entries with an empty canonical or source", () => {
    expect(parseColumnMapping(" = x\ndirection = \n")).toEqual({});
  });

  it("keeps '=' inside the source value (splits on the first only)", () => {
    expect(parseColumnMapping("pnl = a=b")).toEqual({ pnl: "a=b" });
  });
});

describe("mappingHashFromSummary", () => {
  it("returns the string mapping_hash when present", () => {
    expect(mappingHashFromSummary({ mapping_hash: "sha256:abc" })).toBe("sha256:abc");
  });

  it("returns undefined for null / missing / non-string", () => {
    expect(mappingHashFromSummary(null)).toBeUndefined();
    expect(mappingHashFromSummary({})).toBeUndefined();
    expect(mappingHashFromSummary({ mapping_hash: 123 })).toBeUndefined();
  });
});

describe("payload templates thread mapping_revision_id", () => {
  it("omits mapping_revision_id when absent (trade log)", () => {
    const t = buildTradeLogPayloadTemplate({
      sourceAssetId: "s",
      recordBatchRevisionId: "b",
      instrumentId: "BTC",
      sourceTimezone: "UTC",
    });
    expect((t.import_binding as Record<string, unknown>).mapping_revision_id).toBeUndefined();
  });

  it("sets mapping_revision_id when provided (trade log)", () => {
    const t = buildTradeLogPayloadTemplate({
      sourceAssetId: "s",
      recordBatchRevisionId: "b",
      instrumentId: "BTC",
      sourceTimezone: "UTC",
      mappingRevisionId: "sha256:m",
    });
    expect((t.import_binding as Record<string, unknown>).mapping_revision_id).toBe("sha256:m");
  });

  it("sets mapping_revision_id when provided (trading signal)", () => {
    const t = buildSignalPayloadTemplate({
      sourceAssetId: "s",
      normalizedEventRevisionId: "n",
      instrumentId: "BTC",
      sourceTimezone: "UTC",
      mappingRevisionId: "sha256:m",
    });
    expect((t.import_binding as Record<string, unknown>).mapping_revision_id).toBe("sha256:m");
  });
});
