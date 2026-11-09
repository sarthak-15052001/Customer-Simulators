import { AppBar } from "../ui";
import { HeaderTopBar } from "./HeaderTopBar";
import { HeaderMainBar } from "./HeaderMainBar";

export function Header() {
  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        bgcolor: "var(--vtf-white)",
        borderBottom: "1px solid rgba(var(--vtf-navy-rgb), 0.08)",
        boxShadow: "0 4px 20px rgba(var(--vtf-navy-rgb), 0.08)",
      }}
    >
      <HeaderTopBar />
      <HeaderMainBar />
    </AppBar>
  );
}
