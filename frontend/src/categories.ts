/** Friendlier names for the dataset's raw labels ("Outwear" is a typo in the source data). */
const LABELS: Record<string, string> = {
  Outwear: "Outerwear",
  Longsleeve: "Long-sleeve top",
  Body: "Bodysuit",
  Undershirt: "Tank top",
  "T-Shirt": "T-shirt",
  Other: "Other",
};

export function categoryLabel(category: string): string {
  return LABELS[category] ?? category;
}

/** Garment-type filters (match the backend's GROUPS). */
export const GARMENT_GROUPS = [
  { id: "tops", label: "Tops" },
  { id: "bottoms", label: "Bottoms" },
  { id: "one-piece", label: "Dresses" },
  { id: "outerwear", label: "Outerwear" },
  { id: "shoes", label: "Shoes" },
  { id: "hats", label: "Hats" },
] as const;

export type GarmentGroup = (typeof GARMENT_GROUPS)[number]["id"];
