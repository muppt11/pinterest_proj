import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { boardsApi, type Board, type Item } from "./api/client";
import { SaveMenu } from "./components/SaveMenu";
import { Toast } from "./components/Toast";

const LAST_BOARD_KEY = "mb-last-board";
const UNDO_MS = 5000;

interface ToastState {
  message: string;
  undo?: () => void;
}

interface SavesValue {
  boards: Board[];
  lastBoard: Board | null;
  refreshBoards: () => Promise<void>;
  /** Hover "Save": save to the last-used board, or open the picker if there isn't one. */
  quickSave: (item: Item, anchor: HTMLElement) => void;
  /** "Select ⌄": open the multi-board checklist. */
  openPicker: (item: Item, anchor: HTMLElement) => void;
  notify: (toast: ToastState) => void;
}

const SavesContext = createContext<SavesValue | null>(null);

/** For components that also render outside the provider (e.g. in isolated tests). */
export const SavesContextOptional = SavesContext;

export function useSaves(): SavesValue {
  const value = useContext(SavesContext);
  if (!value) throw new Error("useSaves must be used inside <SavesProvider>");
  return value;
}

function readLastBoard(): number | null {
  try {
    const v = Number(localStorage.getItem(LAST_BOARD_KEY));
    return Number.isInteger(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

function writeLastBoard(id: number) {
  try {
    localStorage.setItem(LAST_BOARD_KEY, String(id));
  } catch {
    // not critical
  }
}

export const boardPath = (boards: Board[], board: Board): string => {
  const names = [board.name];
  let parent = board.parent_id;
  while (parent !== null) {
    const p = boards.find((b) => b.id === parent);
    if (!p) break;
    names.unshift(p.name);
    parent = p.parent_id;
  }
  return names.join(" › ");
};

/** Owns boards, the save picker, and the undo toast. No modal dialogs: everything is a popover or toast. */
export function SavesProvider({ children }: { children: ReactNode }) {
  const [boards, setBoards] = useState<Board[]>([]);
  const [lastBoardId, setLastBoardId] = useState<number | null>(readLastBoard);
  const [picker, setPicker] = useState<{ item: Item; anchor: HTMLElement } | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const refreshBoards = useCallback(async () => {
    try {
      setBoards(await boardsApi.list());
    } catch {
      // API down: saving UI will show errors when used
    }
  }, []);

  useEffect(() => {
    refreshBoards();
  }, [refreshBoards]);

  const notify = useCallback((next: ToastState) => {
    window.clearTimeout(timer.current);
    setToast(next);
    timer.current = window.setTimeout(() => setToast(null), UNDO_MS);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const saveTo = useCallback(
    async (item: Item, boardIds: number[], removeIds: number[] = []) => {
      try {
        const added = boardIds.length ? (await boardsApi.save(item.id, boardIds)).added_to : [];
        const removed = removeIds.length ? (await boardsApi.unsave(item.id, removeIds)).already_in : [];
        if (boardIds.length) {
          setLastBoardId(boardIds[0]);
          writeLastBoard(boardIds[0]);
        }
        await refreshBoards();
        const names = (ids: number[]) => ids.map((id) => boards.find((b) => b.id === id)?.name ?? "board").join(", ");
        if (added.length === 0 && removed.length === 0) {
          notify({ message: "Already saved there" });
          return;
        }
        notify({
          message: added.length ? `Saved to ${names(added)}` : `Removed from ${names(removed)}`,
          undo: async () => {
            if (added.length) await boardsApi.unsave(item.id, added);
            if (removed.length) await boardsApi.save(item.id, removed);
            await refreshBoards();
            notify({ message: "Undone" });
          },
        });
      } catch (e) {
        notify({ message: `Couldn't save: ${(e as Error).message}` });
      }
    },
    [boards, notify, refreshBoards],
  );

  const lastBoard = boards.find((b) => b.id === lastBoardId) ?? null;

  const value: SavesValue = {
    boards,
    lastBoard,
    refreshBoards,
    quickSave: (item, anchor) => (lastBoard ? saveTo(item, [lastBoard.id]) : setPicker({ item, anchor })),
    openPicker: (item, anchor) => setPicker({ item, anchor }),
    notify,
  };

  return (
    <SavesContext.Provider value={value}>
      {children}
      {picker && (
        <SaveMenu
          item={picker.item}
          anchor={picker.anchor}
          boards={boards}
          onCreateBoard={async (name, parentId) => {
            const board = await boardsApi.create(name, parentId);
            await refreshBoards();
            return board;
          }}
          onApply={(add, remove) => {
            setPicker(null);
            saveTo(picker.item, add, remove);
          }}
          onClose={() => setPicker(null)}
        />
      )}
      {toast && <Toast message={toast.message} onUndo={toast.undo} onDismiss={() => setToast(null)} />}
    </SavesContext.Provider>
  );
}
