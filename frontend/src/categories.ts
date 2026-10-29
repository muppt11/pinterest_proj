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

export const CATEGORY_GROUPS: Record<string, GarmentGroup | null> = {
  "T-Shirt": "tops", Longsleeve: "tops", Shirt: "tops", Polo: "tops", Top: "tops", Blouse: "tops",
  Undershirt: "tops", Hoodie: "tops", Body: "tops", Pants: "bottoms", Shorts: "bottoms", Skirt: "bottoms",
  Dress: "one-piece", Outwear: "outerwear", Blazer: "outerwear", Shoes: "shoes", Hat: "hats", Other: null,
};

export interface CatalogFilters {
  group: GarmentGroup | null;
  category: string | null;
  audience: "all" | "adults" | "kids";
  colorFamily: string | null;
  style: string | null;
}

export const DEFAULT_FILTERS: CatalogFilters = { group: null, category: null, audience: "all", colorFamily: null, style: null };

/** Only attributes that are recorded in the catalog or derived from its main color. */
export function filterQuery(filters: Partial<CatalogFilters> = {}): string {
  const params = new URLSearchParams();
  if (filters.group) params.set("group", filters.group);
  if (filters.category) params.set("category", filters.category);
  if (filters.audience) params.set("audience", filters.audience);
  if (filters.colorFamily) params.set("color_family", filters.colorFamily);
  const query = params.toString();
  return query ? `&${query}` : "";
}
