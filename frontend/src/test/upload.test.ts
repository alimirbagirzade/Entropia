import { afterEach, describe, expect, it } from "vitest";
import { vi } from "vitest";

import { uploadFile } from "@/lib/upload";

import { stubUpload } from "./helpers/xhrStub";

describe("uploadFile (F-01 shared upload primitive)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves with the parsed JSON body and reports progress", async () => {
    stubUpload({ "POST /widgets": { ok: true, id: "w1" } });
    const progress: Array<{ loaded: number; total: number }> = [];
    const file = new File(["hello"], "a.csv", { type: "text/csv" });

    const handle = uploadFile("/widgets", file, { onProgress: (p) => progress.push(p) });
    const result = await handle.promise;

    expect(result).toEqual({ ok: true, id: "w1" });
    expect(progress.length).toBeGreaterThan(0);
    expect(progress[0]).toEqual({ loaded: file.size, total: file.size });
  });

  it("rejects with the canonical error envelope on a non-2xx response", async () => {
    stubUpload({ "POST /widgets": { status: 422, error: { code: "BAD", message: "nope" } } });
    const file = new File(["hello"], "a.csv");

    await expect(uploadFile("/widgets", file).promise).rejects.toMatchObject({
      code: "BAD",
      message: "nope",
    });
  });

  it("cancel() rejects with UPLOAD_CANCELLED before the response resolves", async () => {
    stubUpload({ "POST /widgets": { ok: true } });
    const file = new File(["hello"], "a.csv");

    const handle = uploadFile("/widgets", file);
    handle.cancel();

    await expect(handle.promise).rejects.toMatchObject({ code: "UPLOAD_CANCELLED" });
  });
});
