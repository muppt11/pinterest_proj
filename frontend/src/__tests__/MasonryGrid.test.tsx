import { fireEvent, render, screen } from "@testing-library/react";
import { ItemCard } from "../components/ItemCard";
import { columnsForWidth, distribute, type MasonryItem } from "../components/MasonryGrid";

const item = (key: string, aspectRatio: number): MasonryItem => ({ key, aspectRatio, node: null });

describe("distribute", () => {
  it("places each item in the currently shortest column, ties going left", () => {
    const cols = distribute([item("a", 2), item("b", 1), item("c", 1), item("d", 1), item("e", 1)], 2);
    expect(cols.map((c) => c.map((i) => i.key))).toEqual([["a", "d"], ["b", "c", "e"]]);
  });

  it("uses 2 columns at phone width and 6 on wide screens", () => {
    expect(columnsForWidth(375)).toBe(2);
    expect(columnsForWidth(1920)).toBe(6);
  });
});

describe("ItemCard", () => {
  it("has alt text, a keyboard-reachable Save, and a title", () => {
    const onSave = vi.fn();
    render(<ItemCard imageUrl="/x.jpg" alt="Denim jacket" title="Denim jacket" aspectRatio={1.3} onSave={onSave} />);
    expect(screen.getByRole("img", { name: "Denim jacket" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledOnce();
    expect(screen.getByText("Denim jacket", { selector: "p" })).toBeInTheDocument();
  });
});
