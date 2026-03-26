import { describe, expect, it, vi } from "vitest";
import { dispatchSsePayload } from "./useSSEStream";

describe("dispatchSsePayload", () => {
  it("calls onCompletion for type completion", () => {
    const onCompletion = vi.fn();
    dispatchSsePayload(
      {
        type: "completion",
        reason: "timeline_reached_arc_end",
        summary: "尾声",
        narrative_status: "completed",
      },
      { onCompletion }
    );
    expect(onCompletion).toHaveBeenCalledWith({
      reason: "timeline_reached_arc_end",
      summary: "尾声",
      narrative_status: "completed",
    });
  });

  it("defaults narrative_status when missing", () => {
    const onCompletion = vi.fn();
    dispatchSsePayload({ type: "completion", reason: "r", summary: "s" }, { onCompletion });
    expect(onCompletion).toHaveBeenCalledWith(
      expect.objectContaining({ narrative_status: "completed" })
    );
  });

  it("still dispatches choices and state_update", () => {
    const onChoices = vi.fn();
    const onStateUpdate = vi.fn();
    dispatchSsePayload({ type: "choices", choices: ["a", "b"] }, { onChoices, onStateUpdate });
    dispatchSsePayload(
      { type: "state_update", state: { active_goal: "g" } },
      { onChoices, onStateUpdate }
    );
    expect(onChoices).toHaveBeenCalledWith(["a", "b"]);
    expect(onStateUpdate).toHaveBeenCalledWith({ active_goal: "g" });
  });
});
