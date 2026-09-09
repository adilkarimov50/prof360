import { describe, expect, it } from "vitest";
import { canAccess } from "./nav";

describe("canAccess", () => {
  it("allows admin to admin routes", () => {
    expect(canAccess("admin", ["admin"])).toBe(true);
  });

  it("denies district prosecutor from admin", () => {
    expect(canAccess("district_prosecutor", ["admin"])).toBe(false);
  });

  it("allows analyst to upload", () => {
    expect(canAccess("analyst", ["admin", "analyst"])).toBe(true);
  });
});
