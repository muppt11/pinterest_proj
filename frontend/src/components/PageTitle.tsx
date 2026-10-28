import type { ReactNode } from "react";

/** Bold centered page heading with optional actions on the right. */
export function PageTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto 1fr",
        alignItems: "center",
        margin: "4px 0 20px",
      }}
    >
      <span />
      <h1 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700 }}>{children}</h1>
      <div style={{ justifySelf: "end", display: "flex", gap: 8 }}>{actions}</div>
    </div>
  );
}
