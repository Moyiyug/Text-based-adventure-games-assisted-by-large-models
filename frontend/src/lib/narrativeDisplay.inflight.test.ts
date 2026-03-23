import { describe, expect, it } from "vitest";
import {
  stripHrJsonTailForDisplay,
  stripInflightChoiceMarkdownDisplay,
  stripMetaSuffixForDisplay,
} from "./narrativeDisplay";

describe("stripInflightChoiceMarkdownDisplay", () => {
  it("hides **choices:** block and list after narrative", () => {
    const raw =
      "春希走过操场。\n\n**choices:**\n- 立刻离开\n- 留下\n";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("春希走过操场。");
  });

  it("hides incomplete last line **cho", () => {
    const raw = "叙事一段。\n\n**cho";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("叙事一段。");
  });

  it("cuts from --- when followed by pseudo field", () => {
    const raw = "正文。\n\n---\n\n**choices:**\n- a\n";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("正文。");
  });

  it("hides **choices** (no colon) block after ---", () => {
    const raw =
      "春希喃喃道。\n\n---\n**choices**\n- 笑着承认\n- 转移话题\n";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("春希喃喃道。");
  });

  it("does not cut normal narrative without stars", () => {
    const raw = "他说道：请从 choices 里选。\n\n再见。";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe(raw);
  });

  it("hides --- + **META** block while streaming", () => {
    const raw = "旁白一段。\n\n---\n**META**\n说明文字\n";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("旁白一段。");
  });

  it("hides partial last line **ME during stream", () => {
    const raw = "旁白。\n\n**ME";
    expect(stripInflightChoiceMarkdownDisplay(raw)).toBe("旁白。");
  });
});

describe("stripHrJsonTailForDisplay", () => {
  it("removes --- + multiline JSON tail (同构 meta_parse)", () => {
    const raw =
      "河风微凉。\n\n---\n{\n  \"choices\": [\"a\",\"b\"],\n  \"state_update\": {\"current_location\":\"x\"}\n}\n";
    expect(stripHrJsonTailForDisplay(raw)).toBe("河风微凉。");
  });

  it("stripMetaSuffixForDisplay chains HR+json strip", () => {
    const raw =
      "正文。\n\n-----\n\n{\"choices\":[\"1\",\"2\"],\"state_update\":{},\"internal_notes\":\"\"}";
    expect(
      stripMetaSuffixForDisplay(raw, { stripNumberedTail: false })
    ).toBe("正文。");
  });
});

describe("stripMetaSuffixForDisplay non-streaming **choices**", () => {
  it("strips --- + **choices** + list (opening / 非流式)", () => {
    const raw =
      "叙事正文。\n\n---\n**choices**\n- A\n- B\n";
    expect(
      stripMetaSuffixForDisplay(raw, { streaming: false, stripNumberedTail: false })
    ).toBe("叙事正文。");
  });

  it("strips --- + **META** (非流式)", () => {
    const raw = "班长递来课本。\n\n---\n**META**\n垃圾行\n";
    expect(
      stripMetaSuffixForDisplay(raw, { streaming: false, stripNumberedTail: false })
    ).toBe("班长递来课本。");
  });
});

describe("stripMetaSuffixForDisplay streaming", () => {
  it("applies inflight strip when streaming is true", () => {
    const raw = "旁白。\n\n**choices:**\n- x\n";
    const out = stripMetaSuffixForDisplay(raw, {
      streaming: true,
      stripNumberedTail: false,
    });
    expect(out).toBe("旁白。");
  });

  it("streaming strips partial **cho; non-streaming keeps incomplete line", () => {
    const raw = "旁白。\n\n**cho";
    expect(
      stripMetaSuffixForDisplay(raw, {
        streaming: true,
        stripNumberedTail: false,
      })
    ).toBe("旁白。");
    expect(
      stripMetaSuffixForDisplay(raw, {
        streaming: false,
        stripNumberedTail: false,
      })
    ).toBe(raw);
  });
});
