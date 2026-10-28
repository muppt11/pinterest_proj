import { useEffect, useState, type FormEvent } from "react";
import { boardsApi, imageSrc, type Board, type BoardDetail, type Item } from "../api/client";
import { useSaves } from "../saves";
import { FeatureTip } from "./FeatureTip";
import { ItemGrid } from "./ItemGrid";
import { PageTitle } from "./PageTitle";
import "./BoardsPage.css";

interface Props {
  boardId: number | null; // null = all top-level boards
  onNavigate: (to: string) => void;
  onOpen: (item: Item) => void;
}

function BoardTile({ board, onClick }: { board: Board; onClick: () => void }) {
  return (
    <li>
      <button type="button" className="mb-boardtile" onClick={onClick}>
        <span className="mb-boardtile-cover">
          {board.cover ? <img src={imageSrc(board.cover)} alt="" /> : null}
        </span>
        <span className="mb-boardtile-name">{board.name}</span>
        <span className="mb-boardtile-count">
          {board.item_count} item{board.item_count === 1 ? "" : "s"}
        </span>
      </button>
    </li>
  );
}

function NewBoardForm({ parentId, label, onCreated }: { parentId: number | null; label: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await boardsApi.create(name, parentId);
      setName("");
      setError(null);
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <form className="mb-newboard" onSubmit={submit}>
      <label htmlFor={`new-board-${parentId ?? "root"}`} className="visually-hidden">
        {label}
      </label>
      <input
        id={`new-board-${parentId ?? "root"}`}
        value={name}
        maxLength={50}
        placeholder={label}
        onChange={(e) => setName(e.target.value)}
      />
      <button type="submit" className="mb-button-primary" disabled={!name.trim()}>
        Create
      </button>
      {error && <span role="alert">{error}</span>}
    </form>
  );
}

/** "Your boards" (top level) or one board with its breadcrumb, sub-boards, and saved items. */
export function BoardsPage({ boardId, onNavigate, onOpen }: Props) {
  const { boards, refreshBoards, notify } = useSaves();
  const [detail, setDetail] = useState<BoardDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    await refreshBoards();
    if (boardId === null) return;
    try {
      setDetail(await boardsApi.get(boardId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    setDetail(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardId]);

  if (boardId === null) {
    const top = boards.filter((b) => b.parent_id === null);
    return (
      <div className="mb-boards">
        <PageTitle>Your boards</PageTitle>
        <FeatureTip tipId="boards">
          <NewBoardForm parentId={null} label="New board name" onCreated={load} />
        </FeatureTip>
        {top.length === 0 ? (
          <p className="mb-notice">No boards yet. Create one, or tap Save on any item.</p>
        ) : (
          <ul className="mb-boardtiles">
            {top.map((b) => (
              <BoardTile key={b.id} board={b} onClick={() => onNavigate(`/boards/${b.id}`)} />
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (error) return <p role="alert" className="mb-notice">{error}</p>;
  if (!detail) return <p className="mb-notice">Loading…</p>;

  async function remove() {
    await boardsApi.remove(detail!.id);
    notify({ message: `Deleted ${detail!.name}` });
    onNavigate(detail!.parent_id ? `/boards/${detail!.parent_id}` : "/boards");
  }

  return (
    <div className="mb-boards">
      <nav aria-label="Breadcrumb" className="mb-breadcrumb">
        <ol>
          <li>
            <a href="/boards" onClick={(e) => (e.preventDefault(), onNavigate("/boards"))}>
              Boards
            </a>
          </li>
          {detail.breadcrumb.map((b) => (
            <li key={b.id}>
              <a href={`/boards/${b.id}`} onClick={(e) => (e.preventDefault(), onNavigate(`/boards/${b.id}`))}>
                {b.name}
              </a>
            </li>
          ))}
          <li aria-current="page">{detail.name}</li>
        </ol>
      </nav>
      <PageTitle actions={<button type="button" className="mb-link-button" onClick={remove}>Delete board</button>}>
        {detail.name}
      </PageTitle>

      <section aria-labelledby="subboards">
        <h2 id="subboards" className="mb-boards-h2">
          Sub-boards
        </h2>
        {detail.children.length > 0 && (
          <ul className="mb-boardtiles is-small">
            {detail.children.map((b) => (
              <BoardTile key={b.id} board={b} onClick={() => onNavigate(`/boards/${b.id}`)} />
            ))}
          </ul>
        )}
        <NewBoardForm parentId={detail.id} label={`New sub-board in ${detail.name}`} onCreated={load} />
      </section>

      <section aria-labelledby="saved-items">
        <h2 id="saved-items" className="mb-boards-h2">
          Saved items
        </h2>
        {detail.items.length === 0 ? (
          <p className="mb-notice">Nothing saved here yet.</p>
        ) : (
          <ItemGrid items={detail.items} label={`Saved in ${detail.name}`} onOpen={onOpen} />
        )}
      </section>
    </div>
  );
}
