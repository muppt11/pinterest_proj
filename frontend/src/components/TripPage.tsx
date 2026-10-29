import { useCallback, useEffect, useState, type FormEvent } from "react";
import { altText, imageSrc, tripsApi, type Item, type SlotSuggestions, type TripDetail, type TripNote, type TripWeather } from "../api/client";
import { PageTitle } from "./PageTitle";
import "./Trips.css";

const fmt = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

export function WeatherCard({ weather }: { weather: TripWeather }) {
  if (weather.source === "unavailable") return <p className="mb-notice">{weather.source_detail}</p>;
  return (
    <section className="mb-trip-card" aria-labelledby="weather-h">
      <h2 id="weather-h">Weather</h2>
      <p className="mb-trip-source">
        <strong>{weather.source === "forecast" ? "Forecast" : "Historical average"}</strong>: {weather.source_detail}
      </p>
      <ul className="mb-weather-days">
        {weather.days.map((d) => (
          <li key={d.date}>
            <span>{fmt(d.date)}</span>
            <strong>
              {d.high_c ?? "?"}° / {d.low_c ?? "?"}°
            </strong>
            <span>{d.rain_chance == null ? "" : `${Math.round(d.rain_chance * 100)}% rain`}</span>
          </li>
        ))}
      </ul>
      <p className="mb-trip-source">{weather.attribution}</p>
    </section>
  );
}

/** One trip: members and invites, shared taste, weather, day-by-day outfits with votes, packing, notes, activity. */
export function TripPage({ tripId, onOpen, onNavigate }: { tripId: number; onOpen: (item: Item) => void; onNavigate: (to: string) => void }) {
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => tripsApi.get(tripId).then(setTrip).catch((e: Error) => setError(e.message)), [tripId]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (error) return <p role="alert" className="mb-notice">{error}</p>;
  if (!trip) return <p className="mb-notice">Loading the trip…</p>;
  const canEdit = trip.your_role !== "viewer";

  return (
    <div className="mb-trip">
      <nav aria-label="Breadcrumb" className="mb-breadcrumb">
        <ol>
          <li>
            <a href="/trips" onClick={(e) => (e.preventDefault(), onNavigate("/trips"))}>
              Trips
            </a>
          </li>
          <li aria-current="page">{trip.name}</li>
        </ol>
      </nav>
      <PageTitle>{trip.name}</PageTitle>
      <p className="mb-trip-meta">
        {trip.place} · {fmt(trip.start_date)} – {fmt(trip.end_date)} · you're {trip.your_role === "owner" ? "the owner" : `a${trip.your_role === "editor" ? "n" : ""} ${trip.your_role}`}
      </p>

      <div className="mb-trip-grid">
        <div className="mb-trip-main">
          <WeatherCard weather={trip.weather} />
          <TasteCard trip={trip} canEdit={canEdit} onChange={reload} />
          {trip.slots.length === 0 && <p className="mb-notice">No days or events yet.</p>}
          {trip.slots.map((s) => (
            <SlotCard key={s.id} tripId={tripId} slot={s} canEdit={canEdit} onOpen={onOpen} coordinate={trip.coordinate} />
          ))}
          {canEdit && <AddSlot trip={trip} onAdded={reload} />}
          <NotesCard trip={trip} canEdit={canEdit} />
        </div>
        <aside className="mb-trip-side">
          <MembersCard trip={trip} onChange={reload} />
          <PackingCard tripId={tripId} />
          <ActivityCard tripId={tripId} />
        </aside>
      </div>
    </div>
  );
}

function MembersCard({ trip, onChange }: { trip: TripDetail; onChange: () => void }) {
  const [link, setLink] = useState<string | null>(null);
  const [invites, setInvites] = useState<{ id: number; role: string; expires_at: string; revoked: number }[]>([]);
  const owner = trip.your_role === "owner";

  useEffect(() => {
    if (owner) tripsApi.invites(trip.id).then(setInvites).catch(() => {});
  }, [owner, trip.id, link]);

  async function invite(role: "editor" | "viewer") {
    const r = await tripsApi.createInvite(trip.id, role);
    setLink(`${window.location.origin}/join/${r.token}`);
  }

  async function togglePublish() {
    if (trip.published) await tripsApi.unpublish(trip.id);
    else await tripsApi.publish(trip.id);
    onChange();
  }

  return (
    <section className="mb-trip-card" aria-labelledby="members-h">
      <h2 id="members-h">Who's going</h2>
      <ul className="mb-trip-members">
        {trip.members.map((m) => (
          <li key={m.user_id}>
            <span className="mb-avatar" aria-hidden="true">
              {m.name[0]?.toUpperCase()}
            </span>
            {m.name}
            {m.is_you ? " (you)" : ""} · {m.role}
          </li>
        ))}
      </ul>
      {owner && (
        <>
          <div className="mb-trip-actions">
            <button type="button" className="mb-link-button" onClick={() => invite("editor")}>
              Invite (can edit)
            </button>
            <button type="button" className="mb-link-button" onClick={() => invite("viewer")}>
              Invite (view only)
            </button>
          </div>
          {link && (
            <p className="mb-trip-link">
              <input readOnly value={link} aria-label="Invite link" onFocus={(e) => e.target.select()} />
              <button type="button" className="mb-link-button" onClick={() => navigator.clipboard?.writeText(link)}>
                Copy
              </button>
            </p>
          )}
          {invites.filter((i) => !i.revoked).length > 0 && (
            <ul className="mb-trip-invites" aria-label="Active invite links">
              {invites
                .filter((i) => !i.revoked)
                .map((i) => (
                  <li key={i.id}>
                    {i.role} link · expires {new Date(i.expires_at).toLocaleDateString()}{" "}
                    <button
                      type="button"
                      className="mb-link-button"
                      onClick={async () => {
                        await tripsApi.revokeInvite(trip.id, i.id);
                        setInvites(await tripsApi.invites(trip.id));
                      }}
                    >
                      Revoke
                    </button>
                  </li>
                ))}
            </ul>
          )}
          <div className="mb-trip-publish">
            <button type="button" className={trip.published ? "mb-link-button" : "mb-button-primary"} onClick={togglePublish}>
              {trip.published ? "Unpublish trip page" : "Publish read-only trip page"}
            </button>
            {trip.published && trip.public_slug && (
              <a href={`/t/${trip.public_slug}`} target="_blank" rel="noopener noreferrer">
                Open public page
              </a>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function TasteCard({ trip, canEdit, onChange }: { trip: TripDetail; canEdit: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const t = trip.taste;

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setError(null);
    try {
      await tripsApi.addInspiration(trip.id, Array.from(files).slice(0, 10));
      onChange();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-trip-card" aria-labelledby="taste-h">
      <h2 id="taste-h">The group's style</h2>
      {t.inspiration_count === 0 ? (
        <p>Everyone adds a few outfit photos they love; MoodBoards blends the group's taste (each person counts equally).</p>
      ) : (
        <>
          <p>
            Blended style: <strong>{t.group_style.join(", ") || "n/a"}</strong> · from {t.inspiration_count} photo{t.inspiration_count > 1 ? "s" : ""}
          </p>
          <ul className="mb-trip-styles">
            {t.members.map((m) => (
              <li key={m.user_id}>
                {m.name}: {m.style.join(", ")}
              </li>
            ))}
          </ul>
          {t.overlap.length > 0 && (
            <ul className="mb-trip-overlap" aria-label="Where tastes overlap or clash">
              {t.overlap.map((o) => (
                <li key={`${o.a}-${o.b}`} className={`is-${o.reading.replace(" ", "-")}`}>
                  {o.a} & {o.b}: <strong>{o.reading}</strong> ({o.similarity.toFixed(2)})
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {canEdit && (
        <div className="mb-trip-actions">
          <label className="mb-link-button">
            {busy ? "Adding…" : "Add my inspiration photos"}
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={(e) => upload(e.target.files)} />
          </label>
          <label className="mb-trip-toggle">
            <input
              type="checkbox"
              checked={trip.coordinate}
              onChange={async (e) => {
                await tripsApi.setCoordinate(trip.id, e.target.checked);
                onChange();
              }}
            />
            Coordinate for photos
          </label>
        </div>
      )}
      {trip.coordinate && trip.palette.length > 0 && (
        <p className="mb-trip-palette">
          Shared palette:{" "}
          {trip.palette.map((p) => (
            <span key={p.hex} className="mb-color-dot" style={{ background: p.hex, width: 22, height: 22 }} title={p.hex} />
          ))}
        </p>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

function SlotCard({ tripId, slot, canEdit, onOpen, coordinate }: { tripId: number; slot: { id: number; day: string; label: string }; canEdit: boolean; onOpen: (item: Item) => void; coordinate: boolean }) {
  const [open, setOpen] = useState(false);
  const [sort, setSort] = useState<"relevance" | "votes">("relevance");
  const [data, setData] = useState<SlotSuggestions | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () => tripsApi.suggestions(tripId, slot.id, sort).then(setData).catch((e: Error) => setError(e.message)),
    [tripId, slot.id, sort],
  );

  useEffect(() => {
    if (open) load();
  }, [open, load, coordinate]);

  async function vote(itemId: string, value: -1 | 1, mine: number) {
    await tripsApi.vote(tripId, slot.id, itemId, mine === value ? 0 : value);
    load();
  }

  const w = data?.weather;
  return (
    <section className="mb-trip-card">
      <button type="button" className="mb-slot-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>
          <strong>{fmt(slot.day)}</strong> · {slot.label}
        </span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <>
          {w && w.high_c != null && (
            <p className="mb-trip-source">
              {w.high_c}°/{w.low_c}° {w.rain_chance != null ? `· ${Math.round(w.rain_chance * 100)}% rain` : ""} ({data?.weather_source}): outfits follow the weather
            </p>
          )}
          <div className="mb-feed-toggle" role="radiogroup" aria-label="Sort suggestions">
            <button type="button" role="radio" aria-checked={sort === "relevance"} onClick={() => setSort("relevance")}>
              Best match
            </button>
            <button type="button" role="radio" aria-checked={sort === "votes"} onClick={() => setSort("votes")}>
              Most votes
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
          <ul className="mb-slot-items">
            {data?.items.map(({ role, item, votes }) => (
              <li key={item.id}>
                <button type="button" className="mb-slot-img" onClick={() => onOpen(item)} aria-label={`Open ${item.category}`}>
                  <img src={imageSrc(item)} alt={altText(item)} loading="lazy" />
                </button>
                <span className="mb-slot-role">{role}</span>
                <span className="mb-slot-votes">
                  <button type="button" disabled={!canEdit} aria-pressed={votes.mine === 1} aria-label={`Like this ${item.category.toLowerCase()}`} onClick={() => vote(item.id, 1, votes.mine)}>
                    👍 {votes.up}
                  </button>
                  <button type="button" disabled={!canEdit} aria-pressed={votes.mine === -1} aria-label={`Pass on this ${item.category.toLowerCase()}`} onClick={() => vote(item.id, -1, votes.mine)}>
                    👎 {votes.down}
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function AddSlot({ trip, onAdded }: { trip: TripDetail; onAdded: () => void }) {
  const [day, setDay] = useState(trip.start_date);
  const [label, setLabel] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    await tripsApi.addSlot(trip.id, day, label);
    setLabel("");
    onAdded();
  }
  return (
    <form className="mb-trip-card mb-trip-dates" onSubmit={submit}>
      <input type="date" aria-label="Day" value={day} min={trip.start_date} max={trip.end_date} onChange={(e) => setDay(e.target.value)} />
      <input aria-label="Event" value={label} maxLength={60} placeholder="Add an event, e.g. museum day" onChange={(e) => setLabel(e.target.value)} />
      <button type="submit" className="mb-link-button" disabled={!label.trim()}>
        Add
      </button>
    </form>
  );
}

function PackingCard({ tripId }: { tripId: number }) {
  const [items, setItems] = useState<{ kind: string; label: string; item_id?: string; why?: string }[]>([]);
  const key = `mb-packed-${tripId}`;
  const [packed, setPacked] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(key) ?? "[]"));
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    tripsApi.packing(tripId).then((r) => setItems(r.items)).catch(() => {});
  }, [tripId]);

  function toggle(id: string) {
    const next = new Set(packed);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setPacked(next);
    try {
      localStorage.setItem(key, JSON.stringify([...next]));
    } catch {
      // checklist state is a convenience
    }
  }

  return (
    <section className="mb-trip-card" aria-labelledby="packing-h">
      <h2 id="packing-h">Your packing list</h2>
      {items.length === 0 ? (
        <p>Like (👍) outfit pieces in the days on the left and they'll show up here, plus weather essentials.</p>
      ) : (
        <ul className="mb-packing">
          {items.map((i, n) => {
            const id = i.item_id ?? `${i.label}-${n}`;
            return (
              <li key={id}>
                <label>
                  <input type="checkbox" checked={packed.has(id)} onChange={() => toggle(id)} />
                  {i.label}
                  {i.why && <span className="mb-trip-source"> ({i.why})</span>}
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function NotesCard({ trip, canEdit }: { trip: TripDetail; canEdit: boolean }) {
  const [notes, setNotes] = useState<TripNote[]>([]);
  const [day, setDay] = useState(trip.start_date);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => tripsApi.notes(trip.id).then(setNotes).catch(() => {}), [trip.id]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="mb-trip-card" aria-labelledby="notes-h">
      <h2 id="notes-h">Day-by-day notes</h2>
      <ul className="mb-notes">
        {notes.map((n) => (
          <li key={n.id}>
            <strong>{fmt(n.day)}</strong> {n.ai_suggestion ? <span className="mb-ai-tag">AI suggestion</span> : <span>· {n.author}</span>}
            <p>{n.text}</p>
          </li>
        ))}
      </ul>
      {canEdit && (
        <form
          className="mb-trip-dates"
          onSubmit={async (e) => {
            e.preventDefault();
            await tripsApi.addNote(trip.id, day, text);
            setText("");
            load();
          }}
        >
          <input type="date" aria-label="Note day" value={day} min={trip.start_date} max={trip.end_date} onChange={(e) => setDay(e.target.value)} />
          <input aria-label="Note" value={text} maxLength={1000} placeholder="e.g. pack the linen set for the boat" onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="mb-link-button" disabled={!text.trim()}>
            Add
          </button>
          <button
            type="button"
            className="mb-link-button"
            onClick={async () => {
              setError(null);
              try {
                await tripsApi.draftNote(trip.id, day);
                load();
              } catch (err) {
                setError((err as Error).message);
              }
            }}
          >
            Draft with AI
          </button>
        </form>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

function ActivityCard({ tripId }: { tripId: number }) {
  const [events, setEvents] = useState<{ id: number; actor: string; text: string }[]>([]);

  useEffect(() => {
    tripsApi.activity(tripId).then(setEvents).catch(() => {});
    if (typeof EventSource === "undefined") return;
    const source = new EventSource(tripsApi.eventsUrl(tripId));
    source.addEventListener("activity", (e) => {
      const ev = JSON.parse((e as MessageEvent).data);
      setEvents((prev) => (prev.some((p) => p.id === ev.id) ? prev : [ev, ...prev].slice(0, 50)));
    });
    return () => source.close();
  }, [tripId]);

  return (
    <section className="mb-trip-card" aria-labelledby="activity-h">
      <h2 id="activity-h">Activity</h2>
      <ul className="mb-activity" aria-live="polite">
        {events.map((e) => (
          <li key={e.id}>
            <strong>{e.actor}</strong> {e.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
