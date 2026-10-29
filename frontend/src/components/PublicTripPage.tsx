import { useEffect, useState } from "react";
import { altText, imageSrc, tripsApi, type PublicTrip } from "../api/client";
import { WeatherCard } from "./TripPage";
import "./Trips.css";

const fmt = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

/** Public, read-only trip page: no sign-in, no names or personal info. */
export function PublicTripPage({ slug }: { slug: string }) {
  const [trip, setTrip] = useState<PublicTrip | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    tripsApi.publicTrip(slug).then(setTrip).catch((e: Error) => setError(e.message));
  }, [slug]);

  if (error) return <p role="alert" className="mb-notice">{error}</p>;
  if (!trip) return <p className="mb-notice">Loading…</p>;
  return (
    <article className="mb-public-trip">
      <h1>{trip.name}</h1>
      <p className="mb-trip-meta">
        {trip.place} · {fmt(trip.start_date)} – {fmt(trip.end_date)} · {trip.travelers} traveler{trip.travelers === 1 ? "" : "s"}
      </p>
      <WeatherCard weather={trip.weather} />
      <h2>Outfit lineup</h2>
      {trip.lineup.map((s) => (
        <section key={`${s.day}-${s.label}`} className="mb-trip-card">
          <h3>
            {fmt(s.day)} · {s.label}
          </h3>
          {s.items.length === 0 ? (
            <p className="mb-trip-source">No picks yet.</p>
          ) : (
            <ul className="mb-slot-items">
              {s.items.map((item) => (
                <li key={item.id}>
                  <img src={imageSrc(item)} alt={altText(item)} loading="lazy" />
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      {trip.notes.length > 0 && (
        <>
          <h2>Notes</h2>
          <ul className="mb-notes">
            {trip.notes.map((n, i) => (
              <li key={i}>
                <strong>{fmt(n.day)}</strong> {n.ai_suggestion ? <span className="mb-ai-tag">AI suggestion</span> : null}
                <p>{n.text}</p>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="mb-trip-source">Shared from MoodBoards, a read-only page with no sign-in.</p>
    </article>
  );
}
