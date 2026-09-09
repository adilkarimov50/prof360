import { describe, it, expect } from "vitest";
import { canAccess, navForRole } from "../lib/nav";

describe("nav", () => {
  it("hides admin for analyst", () => {
    const items = navForRole("analyst");
    expect(items.some((i) => i.to === "/admin")).toBe(false);
    expect(items.some((i) => i.to === "/upload")).toBe(true);
  });

  it("shows admin for admin role", () => {
    expect(canAccess("admin", ["admin"])).toBe(true);
    expect(navForRole("admin").some((i) => i.to === "/admin")).toBe(true);
  });
});
