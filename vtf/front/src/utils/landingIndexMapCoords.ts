import type { LandingMapVillage } from "../types/landingMap";

/** France index map SVG viewBox (must match france-index-map.svg). */
export const LANDING_INDEX_MAP_VIEWBOX = {
  width: 600,
  height: 573,
} as const;

/** Pin graphic is 20×24; tip is bottom-center relative to `translate(x y)` groups. */
const MARKER_PIN_TIP_OFFSET = { x: 10, y: 24 } as const;

export type MapPoint = { x: number; y: number };

/**
 * Read authoritative marker positions baked into the SVG (`data-id-town` groups).
 */
export function extractTownCoordsFromSvg(
  svgRoot: ParentNode,
): Map<number, MapPoint> {
  const coords = new Map<number, MapPoint>();

  svgRoot.querySelectorAll<SVGGElement>("[data-id-town]").forEach((el) => {
    const id = Number(el.getAttribute("data-id-town"));
    if (Number.isNaN(id)) return;

    const transform = el.getAttribute("transform") ?? "";
    const match = transform.match(
      /translate\(\s*([\d.]+)[\s,]+([\d.]+)\s*\)/,
    );
    if (!match) return;

    const tx = Number.parseFloat(match[1]);
    const ty = Number.parseFloat(match[2]);
    coords.set(id, {
      x: tx + MARKER_PIN_TIP_OFFSET.x,
      y: ty + MARKER_PIN_TIP_OFFSET.y,
    });
  });

  return coords;
}

/** Prefer SVG artwork coords; fall back to API when a town is not in the SVG. */
export function mergeVillageCoords(
  villages: LandingMapVillage[],
  svgCoords: Map<number, MapPoint>,
): LandingMapVillage[] {
  if (svgCoords.size === 0) return villages;

  return villages.map((village) => {
    const fromSvg = svgCoords.get(village.id);
    if (!fromSvg) return village;
    return { ...village, coords: fromSvg };
  });
}
