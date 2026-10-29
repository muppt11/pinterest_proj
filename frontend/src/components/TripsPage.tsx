import { useEffect, useState, type FormEvent } from "react";
import { tripsApi, type Place, type TripSummary } from "../api/client";
import { FeatureTip } from "./FeatureTip";
import { PageTitle } from "./PageTitle";
import "./Trips.css";

const fmt = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

/** Your trips, plus a form to start a new one (destination via Open-Meteo geocoding). */
export function TripsPage({ signedIn, onNavigate }: { signedIn: boolean; onNavigate: (to: string) => void }) {
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (signedIn) tripsApi.list().then(setTrips).catch((e: Error) => setError(e.message));
  }, [signedIn]);

  if (!signedIn) {
    return (
      <div className="mb-trips">
        <PageTitle>Group trips</PageTitle>
        <p className="mb-notice">
          Plan coordinated outfits with friends. Trips need a name so friends know who's who.{" "}
          <button type="button" className="mb-link-button" onClick={() => onNavigate("/welcome")}>
            Sign up (just a name)
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="mb-trips">
      <PageTitle>Group trips</PageTitle>
      {error && <p role="alert" className="mb-notice">{error}</p>}
      {trips.length > 0 && (
        <ul className="mb-trip-list">
          {trips.map((t) => (
            <li key={t.id}>
              <button type="button" onClick={() => onNavigate(`/trips/${t.id}`)}>
                <strong>{t.name}</strong>
                <span>
                  {t.place_name} · {fmt(t.start_date)}–{fmt(t.end_date)} · {t.role}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <FeatureTip tipId="trips">
        <NewTripForm onCreated={(id) => onNavigate(`/trips/${id}`)} />
      </FeatureTip>
    </div>
  );
}

function NewTripForm({ onCreated }: { onCreated: (id: number) => void }) {
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [places, setPlaces] = useState<Place[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [slots, setSlots] = useState<{ day: string; label: string }[]>([]);
  const [slotDay, setSlotDay] = useState("");
  const [slotLabel, setSlotLabel] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPlaces([]);
    if (place || query.trim().length < 2) return;
    let cancelled = false;
    const t = window.setTimeout(() => tripsApi.geocode(query.trim())
      .then((results) => !cancelled && setPlaces(results))
      .catch(() => !cancelled && setPlaces([])), 300);
    return () => { cancelled = true; window.clearTimeout(t); };
  }, [query, place]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!place) return setError("Pick a destination from the list.");
    try {
      const { id } = await tripsApi.create({ name, place, start_date: start, end_date: end, slots });
      onCreated(id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="mb-trip-form" onSubmit={submit}>
      <h2>Start a trip</h2>
      <label>
        Trip name
        <input value={name} maxLength={80} required placeholder="Lisbon girls trip" onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Destination
        <input
          value={place ? `${place.name}${place.country ? `, ${place.country}` : ""}` : query}
          placeholder="Search a city"
          onChange={(e) => {
            setPlace(null);
            setQuery(e.target.value);
          }}
        />
      </label>
      {places.length > 0 && (
        <ul className="mb-place-options" aria-label="Destinations">
          {places.map((p) => (
            <li key={`${p.latitude},${p.longitude}`}>
              <button type="button" onClick={() => setPlace(p)}>
                {p.name}
                {p.admin ? `, ${p.admin}` : ""}
                {p.country ? `, ${p.country}` : ""}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mb-trip-dates">
        <label>
          From
          <input type="date" value={start} required onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={end} min={start} required onChange={(e) => setEnd(e.target.value)} />
        </label>
      </div>
      <fieldset>
        <legend>Days and events (optional, add more later)</legend>
        <ul className="mb-tags">
          {slots.map((s, i) => (
            <li key={i}>
              {fmt(s.day)} · {s.label}
            </li>
          ))}
        </ul>
        <div className="mb-trip-dates">
          <input type="date" aria-label="Event day" value={slotDay} min={start} max={end} onChange={(e) => setSlotDay(e.target.value)} />
          <input aria-label="Event" value={slotLabel} maxLength={60} placeholder="beach dinner" onChange={(e) => setSlotLabel(e.target.value)} />
          <button
            type="button"
            className="mb-link-button"
            disabled={!slotDay || !slotLabel.trim()}
            onClick={() => {
              setSlots([...slots, { day: slotDay, label: slotLabel.trim() }]);
              setSlotLabel("");
            }}
          >
            Add
          </button>
        </div>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      <button type="submit" className="mb-button-primary">
        Create trip
      </button>
    </form>
  );
}
