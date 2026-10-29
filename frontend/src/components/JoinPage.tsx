import { useEffect, useState } from "react";
import { tripsApi } from "../api/client";

/** Opens an invite link: joins the trip (after sign-up) and goes to it. */
export function JoinPage({ token, signedIn, onNavigate }: { token: string; signedIn: boolean | null; onNavigate: (to: string) => void }) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (signedIn !== true) return;
    tripsApi
      .join(token)
      .then((r) => onNavigate(`/trips/${r.trip_id}`))
      .catch((e: Error) => setError(e.message));
  }, [token, signedIn, onNavigate]);

  if (signedIn === false) {
    try {
      sessionStorage.setItem("mb-pending-invite", token);
    } catch {
      // fine: they can open the link again after signing up
    }
    return (
      <p className="mb-notice">
        You've been invited to a trip. Sign up with just a name first, then you'll be taken straight to it.{" "}
        <button type="button" className="mb-link-button" onClick={() => onNavigate("/welcome")}>
          Sign up
        </button>
      </p>
    );
  }
  return <p className="mb-notice" role={error ? "alert" : undefined}>{error ?? "Joining the trip…"}</p>;
}
