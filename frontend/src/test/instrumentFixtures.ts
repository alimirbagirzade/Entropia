// Test fixtures/re-exports for the Instrument Registry page tests (GAP-16).
export { parseAliases } from "@/lib/instrument";

import { parseAliases as _pa } from "@/lib/instrument";

// A trivial invariant used by the unit test to prove the parser + fixtures line up.
export function resolutionExpectations(): boolean {
  return _pa("a\n b ").length === 2;
}
