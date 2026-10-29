import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { boardsApi, type Board, type Item } from "../api/client";
import { usePopoverPosition } from "../usePopoverPosition";
import "./SaveMenu.css";

interface Props {
  item: Item;
  anchor: HTMLElement;
  boards: Board[];
  onCreateBoard: (name: string, parentId: number | null) => Promise<Board>;
  onApply: (add: number[], remove: number[]) => void;
  onClose: () => void;
}

function depthOf(boards: Board[], board: Board): number {
  let depth = 0;
  let parent = board.parent_id;
  while (parent !== null && depth < 20) {
    depth += 1;
    parent = boards.find((b) => b.id === parent)?.parent_id ?? null;
  }
  return depth;
}

/** Checklist popover for saving one item to several boards (and sub-boards) at once. */
export function SaveMenu({ item, anchor, boards, onCreateBoard, onApply, onClose }: Props) {
  const [initial, setInitial] = useState<Set<number>>(new Set());
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [newName, setNewName] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const position = usePopoverPosition(true, anchor, panel, { margin: 16 });

  useEffect(() => {
    boardsApi
      .savedIn(item.id)
      .then((ids) => {
        setInitial(new Set(ids));
        setChecked(new Set(ids));
      })
      .catch(() => {});
  }, [item.id]);

  useLayoutEffect(() => {
    panel.current?.querySelector<HTMLElement>("input")?.focus();
  }, [anchor]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onClick = (e: MouseEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node) && !anchor.contains(e.target as Node)) onClose();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [anchor, onClose]);

  function toggle(id: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    const board = await onCreateBoard(newName, null);
    setNewName("");
    setChecked((prev) => new Set(prev).add(board.id));
  }

  const add = [...checked].filter((id) => !initial.has(id));
  const remove = [...initial].filter((id) => !checked.has(id));

  return createPortal(
    <div
      ref={panel}
      className="mb-savemenu"
      role="dialog"
      aria-modal="false"
      aria-label="Save to boards"
      style={position}
    >
      <p className="mb-savemenu-title">Save to boards</p>
      {boards.length === 0 ? (
        <p className="mb-savemenu-empty">No boards yet. Create one below.</p>
      ) : (
        <ul className="mb-savemenu-list">
          {boards.map((b) => (
            <li key={b.id} style={{ paddingLeft: Math.min(depthOf(boards, b), 4) * 12 }}>
              <label>
                <input type="checkbox" checked={checked.has(b.id)} onChange={() => toggle(b.id)} />
                {b.cover ? <img src={`/api${b.cover.image_url}`} alt="" /> : <span className="mb-savemenu-blank" />}
                <span>{b.name}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <form className="mb-savemenu-create" onSubmit={create}>
        <label htmlFor="mb-new-board" className="visually-hidden">
          New board name
        </label>
        <input id="mb-new-board" value={newName} maxLength={50} placeholder="Create board" onChange={(e) => setNewName(e.target.value)} />
        <button type="submit" disabled={!newName.trim()}>
          Create
        </button>
      </form>
      <button
        type="button"
        className="mb-button-primary mb-savemenu-apply"
        disabled={add.length === 0 && remove.length === 0}
        onClick={() => onApply(add, remove)}
      >
        {add.length > 0 ? `Save to ${add.length} board${add.length > 1 ? "s" : ""}` : remove.length > 0 ? "Update" : "Save"}
      </button>
    </div>,
    document.body,
  );
}
