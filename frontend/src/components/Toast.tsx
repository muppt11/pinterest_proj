import "./Toast.css";

interface ToastProps {
  message: string;
  onUndo?: () => void;
  onDismiss: () => void;
}

/** Small bottom toast. Announced politely to screen readers; never steals focus or blocks the page. */
export function Toast({ message, onUndo, onDismiss }: ToastProps) {
  return (
    <div className="mb-toast" role="status" aria-live="polite">
      <span>{message}</span>
      {onUndo && (
        <button
          type="button"
          onClick={() => {
            onDismiss();
            onUndo();
          }}
        >
          Undo
        </button>
      )}
    </div>
  );
}
