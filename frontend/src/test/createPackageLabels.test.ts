import { describe, expect, it } from "vitest";

import {
  CREATE_PACKAGE_KINDS,
  CREATE_PACKAGE_KIND_LABELS,
  CREATION_MODES,
  CREATION_MODE_LABELS,
  OUTPUT_KIND_LABELS,
  OUTPUT_KINDS_BY_KIND,
  SOURCE_LANGUAGES,
  SOURCE_LANGUAGE_LABELS,
  createPackageEnumLabel,
} from "@/lib/createPackage";

// D-2 (audit P-03): the Create Package form must never present an underscore
// machine enum as a user-facing label, while the enum stays the payload value.
describe("Create Package display labels (D-2)", () => {
  it("maps every package kind / creation mode / source language to a human label", () => {
    for (const k of CREATE_PACKAGE_KINDS) {
      expect(CREATE_PACKAGE_KIND_LABELS[k]).toBeDefined();
      expect(CREATE_PACKAGE_KIND_LABELS[k]).not.toMatch(/_/);
    }
    for (const m of CREATION_MODES) {
      expect(CREATION_MODE_LABELS[m]).toBeDefined();
      expect(CREATION_MODE_LABELS[m]).not.toMatch(/_/);
    }
    for (const l of SOURCE_LANGUAGES) {
      expect(SOURCE_LANGUAGE_LABELS[l]).toBeDefined();
      expect(SOURCE_LANGUAGE_LABELS[l]).not.toMatch(/_/);
    }
  });

  it("maps every output kind used by any package type to a human label", () => {
    const allOutputKinds = new Set(Object.values(OUTPUT_KINDS_BY_KIND).flat());
    for (const kind of allOutputKinds) {
      expect(OUTPUT_KIND_LABELS[kind], `missing label for output kind ${kind}`).toBeDefined();
      expect(OUTPUT_KIND_LABELS[kind]).not.toMatch(/_/);
    }
  });

  it("uses the canonical PineScript / C++ casing", () => {
    expect(SOURCE_LANGUAGE_LABELS.pinescript).toBe("PineScript");
    expect(SOURCE_LANGUAGE_LABELS.cpp).toBe("C++");
    expect(CREATION_MODE_LABELS.translate_existing_code).toBe("Translate Existing Code");
    expect(OUTPUT_KIND_LABELS.directional_signal).toBe("Directional Signal");
  });

  it("title-cases an unknown enum value instead of rendering it raw", () => {
    expect(createPackageEnumLabel({}, "some_new_kind")).toBe("Some New Kind");
    expect(createPackageEnumLabel(CREATE_PACKAGE_KIND_LABELS, "indicator")).toBe(
      "Indicator Package",
    );
  });
});
