import { useEffect, useState } from "react";
import { api, imageSrc, type CharacterBoard, type CharacterInfo, type Item } from "../api/client";
import { FeatureTip } from "./FeatureTip";
import { ItemGrid } from "./ItemGrid";
import { PageTitle } from "./PageTitle";
import "./CharactersPage.css";

interface Props {
  characterId: string | null;
  onNavigate: (to: string) => void;
  onOpen: (item: Item) => void;
}

/** Film/TV character style boards: pick a character, get catalog items in their signature style. */
export function CharactersPage({ characterId, onNavigate, onOpen }: Props) {
  const [characters, setCharacters] = useState<(CharacterInfo & { covers: Item[] })[]>([]);
  const [board, setBoard] = useState<CharacterBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.characters().then(setCharacters).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    setBoard(null);
    if (!characterId) return;
    api
      .characterBoard(characterId)
      .then(setBoard)
      .catch((e: Error) => setError(e.message));
  }, [characterId]);

  if (error) return <p role="alert" className="mb-notice">{error}</p>;

  if (!characterId) {
    return (
      <div className="mb-chars">
        <PageTitle>Character style boards</PageTitle>
        <FeatureTip tipId="characters">
          <p className="mb-chars-intro">Dress like your favorite film and TV characters. Pick one to see similar pieces from the catalog.</p>
        </FeatureTip>
        <ul className="mb-chars-grid">
          {characters.map((c) => (
            <li key={c.id}>
              <button type="button" className="mb-char-card" onClick={() => onNavigate(`/characters/${c.id}`)}>
                <span className="mb-char-collage" aria-hidden="true">
                  {c.covers.slice(0, 4).map((item) => (
                    <img key={item.id} src={imageSrc(item)} alt="" loading="lazy" />
                  ))}
                </span>
                <span className="mb-char-name">{c.name}</span>
                <span className="mb-char-source">{c.source}</span>
                <span className="mb-char-summary">{c.summary}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (!board) return <p className="mb-notice">Building the board…</p>;

  return (
    <div className="mb-chars">
      <nav aria-label="Breadcrumb" className="mb-breadcrumb">
        <ol>
          <li>
            <a href="/characters" onClick={(e) => (e.preventDefault(), onNavigate("/characters"))}>
              Characters
            </a>
          </li>
          <li aria-current="page">{board.name}</li>
        </ol>
      </nav>
      <PageTitle>{board.name}</PageTitle>
      <p className="mb-chars-meta">
        {board.source} · {board.summary}
      </p>
      <p className="mb-chars-disclaimer">{board.disclaimer}</p>
      {board.looks.map((look) => (
        <section key={look.name} className="mb-chars-look" aria-labelledby={`look-${look.name}`}>
          <h2 id={`look-${look.name}`}>{look.name}</h2>
          <ul className="mb-tags mb-chars-phrases" aria-label={`Pieces in ${look.name}`}>
            {look.phrases.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          {look.results.length === 0 ? (
            <p className="mb-notice">No close matches in the catalog for this look.</p>
          ) : (
            <ItemGrid items={look.results} label={`${board.name}: ${look.name}`} onOpen={onOpen} />
          )}
        </section>
      ))}
    </div>
  );
}
