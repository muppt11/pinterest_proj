import { useContext, useState } from "react";
import { boardsApi, type Item } from "../api/client";
import { SavesContextOptional } from "../saves";

/** One click: a new board containing every item of a look, with Undo (deletes that board). */
export function SaveLookButton({ name, items }: { name: string; items: Item[] }) {
  const saves = useContext(SavesContextOptional);
  const [busy, setBusy] = useState(false);
  if (!saves || items.length === 0) return null;

  async function save() {
    setBusy(true);
    try {
      const board = await boardsApi.fromItems(name, items.map((i) => i.id));
      await saves!.refreshBoards();
      saves!.notify({
        message: `Saved ${items.length} items to “${board.name}”`,
        undo: async () => {
          await boardsApi.remove(board.id);
          await saves!.refreshBoards();
          saves!.notify({ message: "Undone" });
        },
      });
    } catch (e) {
      saves!.notify({ message: `Couldn't save: ${(e as Error).message}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" className="mb-link-button mb-save-look" onClick={save} disabled={busy}>
      {busy ? "Saving…" : "Save as board"}
    </button>
  );
}
