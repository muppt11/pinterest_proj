import { useEffect, useState, type FormEvent } from "react";
import { profileApi, type Me, type Prefs, type QuizOptions } from "../api/client";
import { FOCUS_LABELS, setFocus, type Focus } from "../focus";
import "./StyleQuiz.css";

interface Props {
  me: Me | null;
  /** Called after saving (or skipping) so the app can refresh the profile and move on. */
  onDone: (me: Me | null) => void;
  /** Editing from "Your style" shows every section at once; first-time onboarding goes step by step. */
  mode: "onboarding" | "edit";
}

const SKIP_KEY = "mb-onboarding-skipped";

export function markOnboardingSkipped() {
  try {
    localStorage.setItem(SKIP_KEY, "1");
  } catch {
    // ignore
  }
}

export function onboardingSkipped(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) === "1";
  } catch {
    return false;
  }
}

const STEPS = ["name", "aesthetics", "colors", "eras", "focus"] as const;
type Step = (typeof STEPS)[number];

const TITLES: Record<Step, string> = {
  name: "What should we call you?",
  aesthetics: "Which aesthetics feel like you?",
  colors: "Which colors do you reach for?",
  eras: "Any eras you love?",
  focus: "What should we show you?",
};

function toggle(list: string[], value: string, max = Infinity): string[] {
  if (list.includes(value)) return list.filter((v) => v !== value);
  return list.length >= max ? list : [...list, value];
}

/** Sign-up + style quiz. Every step can be skipped; answers are saved to your profile and editable later. */
export function StyleQuiz({ me, onDone, mode }: Props) {
  const [options, setOptions] = useState<QuizOptions | null>(null);
  const [name, setName] = useState(me?.display_name ?? "");
  const [prefs, setPrefs] = useState<Prefs>(me?.prefs ?? { aesthetics: [], colors: [], eras: [], focus: "all" });
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    profileApi.quiz().then(setOptions).catch((e: Error) => setError(e.message));
  }, []);

  async function save(e?: FormEvent) {
    e?.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (!me || name.trim() !== me.display_name) await profileApi.signUp(name.trim() || "Friend");
      const saved = await profileApi.savePrefs(prefs);
      setFocus(prefs.focus as Focus);
      onDone(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function skipAll() {
    markOnboardingSkipped();
    onDone(me);
  }

  if (!options) return <p className="mb-notice">{error ?? "Loading the quiz…"}</p>;

  const section = (s: Step) => {
    switch (s) {
      case "name":
        return (
          <label className="mb-quiz-name">
            <span className="visually-hidden">Display name</span>
            <input value={name} maxLength={40} placeholder="Your first name" onChange={(e) => setName(e.target.value)} autoFocus={mode === "onboarding"} />
          </label>
        );
      case "aesthetics":
        return (
          <div className="mb-quiz-chips" role="group" aria-label={`Aesthetics, pick up to ${options.max_picks}`}>
            {options.aesthetics.map((a) => (
              <button key={a} type="button" aria-pressed={prefs.aesthetics.includes(a)} onClick={() => setPrefs({ ...prefs, aesthetics: toggle(prefs.aesthetics, a, options.max_picks) })}>
                {a}
              </button>
            ))}
          </div>
        );
      case "colors":
        return (
          <div className="mb-quiz-colors" role="group" aria-label="Color families">
            {Object.entries(options.colors).map(([family, swatches]) => (
              <button key={family} type="button" aria-pressed={prefs.colors.includes(family)} onClick={() => setPrefs({ ...prefs, colors: toggle(prefs.colors, family) })}>
                <span className="mb-quiz-swatches" aria-hidden="true">
                  {swatches.map((h) => (
                    <span key={h} style={{ background: h }} />
                  ))}
                </span>
                {family}
              </button>
            ))}
          </div>
        );
      case "eras":
        return (
          <div className="mb-quiz-chips" role="group" aria-label="Eras">
            {options.eras.map((era) => (
              <button key={era} type="button" aria-pressed={prefs.eras.includes(era)} onClick={() => setPrefs({ ...prefs, eras: toggle(prefs.eras, era) })}>
                {era}
              </button>
            ))}
          </div>
        );
      case "focus":
        return (
          <div className="mb-quiz-chips" role="radiogroup" aria-label="Show me">
            {(Object.keys(FOCUS_LABELS) as Focus[]).map((f) => (
              <button key={f} type="button" role="radio" aria-checked={prefs.focus === f} onClick={() => setPrefs({ ...prefs, focus: f })}>
                {FOCUS_LABELS[f]}
              </button>
            ))}
            <p className="mb-quiz-hint">Estimated from each image. Unisex pieces always show.</p>
          </div>
        );
    }
  };

  if (mode === "edit") {
    return (
      <form className="mb-quiz is-edit" onSubmit={save}>
        {STEPS.map((s) => (
          <section key={s}>
            <h2>{TITLES[s]}</h2>
            {section(s)}
          </section>
        ))}
        {error && <p role="alert">{error}</p>}
        <div className="mb-quiz-nav">
          <button type="submit" className="mb-button-primary" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    );
  }

  const current = STEPS[step];
  const last = step === STEPS.length - 1;
  return (
    <form className="mb-quiz" onSubmit={(e) => (e.preventDefault(), last ? save() : setStep(step + 1))}>
      <p className="mb-quiz-progress" aria-live="polite">
        Step {step + 1} of {STEPS.length}
      </p>
      <h1>{TITLES[current]}</h1>
      {section(current)}
      {error && <p role="alert">{error}</p>}
      <div className="mb-quiz-nav">
        {step > 0 && (
          <button type="button" className="mb-link-button" onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
        <button type="button" className="mb-link-button" onClick={() => (last ? save() : setStep(step + 1))}>
          Skip this question
        </button>
        <button type="submit" className="mb-button-primary" disabled={saving}>
          {last ? (saving ? "Saving…" : "Finish") : "Next"}
        </button>
      </div>
      <button type="button" className="mb-quiz-skipall" onClick={skipAll}>
        Skip setup for now
      </button>
    </form>
  );
}
