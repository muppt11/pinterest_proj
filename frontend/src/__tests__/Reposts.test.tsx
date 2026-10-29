import { repostLabel, type Item } from "../api/client";

const base: Item = { id: "a", category: "Dress", image_url: "/images/a.jpg", kids: false, width: 1, height: 1 };

describe("repostLabel", () => {
  it("is empty for items without duplicates", () => {
    expect(repostLabel(base)).toBeNull();
  });

  it("says 'original unclear' instead of guessing", () => {
    const item = { ...base, repost: { status: "unclear" as const, original_id: null, first_seen: null, date_source: null, reason: "", hidden: 1, member_ids: ["a", "b"] } };
    expect(repostLabel(item)).toBe("Original unclear · 1 copy hidden");
  });

  it("credits the original with its date source", () => {
    const item = { ...base, repost: { status: "original" as const, original_id: "a", first_seen: "2020-05-01T00:00:00", date_source: "EXIF DateTimeOriginal", reason: "", hidden: 2, member_ids: ["a", "b", "c"] } };
    expect(repostLabel(item)).toMatch(/^Original · first seen .+ \(EXIF DateTimeOriginal\) · 2 copies hidden$/);
  });
});
