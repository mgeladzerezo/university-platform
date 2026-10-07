import { describe, expect, it } from "vitest";

import { availableActions } from "./workflow";

describe("availableActions", () => {
  it("offers publishing only for content in review", () => {
    expect(availableActions("draft")).not.toContain("publish");
    expect(availableActions("in_review")).toEqual(["publish", "request_changes"]);
    expect(availableActions("published")).toEqual(["unpublish", "archive"]);
    expect(availableActions("archived")).toEqual(["restore"]);
  });
});
