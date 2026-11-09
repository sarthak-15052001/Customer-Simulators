import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import LandingVtfPage from "../pages/LandingVtfPage";
import { RouteFallback } from "../components/shared/RouteFallback";
import { BackToTop } from "../components/shared/BackToTop/BackToTop";

const SimulateurVtfPage = lazy(() => import("../pages/SimulateurVtfPage"));

export default function AppRoutes() {
  return (
    <>
      <Routes>
        <Route path="/" element={<LandingVtfPage />} />

        <Route
          path="/simulateur-vtf/:step?"
          element={
            <Suspense fallback={<RouteFallback />}>
              <SimulateurVtfPage />
            </Suspense>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <BackToTop />
    </>
  );
}
