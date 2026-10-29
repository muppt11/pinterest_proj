import type { ReactNode } from "react";
import "./PageTitle.css";

/** Bold centered page heading with optional actions on the right. */
export function PageTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-page-title">
      <span className="mb-page-title-spacer" />
      <h1>{children}</h1>
      <div className="mb-page-title-actions">{actions}</div>
    </div>
  );
}
