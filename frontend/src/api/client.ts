/** Typed client for the MoodBoards API. In dev, Vite proxies /api to FastAPI on :8000. */

const BASE = "/api";

export interface Item {
  id: string;
  category: string;
  image_url: string;
  kids: boolean;
  width: number;
  height: number;
}

export interface ScoredItem extends Item {
  score: number;
}

export interface ItemPage {
  items: Item[];
  total: number;
  offset: number;
}

export interface SearchResults {
  query: string | null;
  results: ScoredItem[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const imageSrc = (item: Item) => `${BASE}${item.image_url}`;

export const altText = (item: Item) => `Photo of ${item.kids ? "kids' " : ""}${item.category.toLowerCase()}`;

export const api = {
  listItems: (offset = 0, limit = 50) => request<ItemPage>(`/items?offset=${offset}&limit=${limit}`),
  getItem: (id: string) => request<Item>(`/items/${encodeURIComponent(id)}`),
  similar: (id: string, k = 30) => request<SearchResults>(`/items/${encodeURIComponent(id)}/similar?k=${k}`),
  searchText: (q: string, k = 50) => request<SearchResults>(`/search/text?q=${encodeURIComponent(q)}&k=${k}`),
  searchImage: (file: File, k = 50) => {
    const body = new FormData();
    body.append("image", file);
    return request<SearchResults>(`/search/image?k=${k}`, { method: "POST", body });
  },
};
