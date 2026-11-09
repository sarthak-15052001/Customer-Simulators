import * as React from "react";
import { Box } from "../components/ui";
import { Header } from "../components/layout/Header";
import { Footer } from "../components/layout/Footer";

type Props = {
  children: React.ReactNode;
};

export default function AppLayout({ children }: Props) {
  return (
    <Box sx={{ minHeight: "100svh", display: "flex", flexDirection: "column" }}>
      <Header />
      <Box
        component="main"
        sx={{
          flex: 1,
          pt: 0,
          minHeight: "100%",
        }}
        key={
          typeof window !== "undefined" ? window.location.pathname : undefined
        }
      >
        {children}
      </Box>
      <Footer />
    </Box>
  );
}
