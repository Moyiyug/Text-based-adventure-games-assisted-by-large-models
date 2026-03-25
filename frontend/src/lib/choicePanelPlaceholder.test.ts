import { describe, expect, it } from "vitest";
import {
  STREAMING_NARRATIVE_THRESHOLD_CHARS,
  choicePanelStreamHint,
} from "./choicePanelPlaceholder";

describe("choicePanelStreamHint", () => {
  it("returns null when not streaming", () => {
    expect(choicePanelStreamHint(false, 0)).toBeNull();
    expect(choicePanelStreamHint(false, 999)).toBeNull();
  });

  it("returns narrative before threshold", () => {
    expect(choicePanelStreamHint(true, 0)).toBe("narrative");
    expect(choicePanelStreamHint(true, STREAMING_NARRATIVE_THRESHOLD_CHARS - 1)).toBe(
      "narrative"
    );
  });

  it("returns awaiting_choices at or after threshold", () => {
    expect(choicePanelStreamHint(true, STREAMING_NARRATIVE_THRESHOLD_CHARS)).toBe(
      "awaiting_choices"
    );
    expect(choicePanelStreamHint(true, 500)).toBe("awaiting_choices");
  });
});
