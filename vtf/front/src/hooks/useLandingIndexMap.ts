import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";

import franceMapSvg from "../assets/landing/france-index-map.svg?raw";
import landingMapApi from "../api/landingMap.api";
import {
  extractTownCoordsFromSvg,
  mergeVillageCoords,
} from "../utils/landingIndexMapCoords";
import { useTranslation } from "../contexts/LanguageContext";

function syncMapSelection(svgHost: HTMLElement, zoneId: number | null) {
  svgHost.querySelectorAll("[data-id-zone]").forEach((el) => {
    const id = Number(el.getAttribute("data-id-zone"));

    if (zoneId === id) {
      el.setAttribute("data-selected", "true");
    } else {
      el.removeAttribute("data-selected");
    }
  });

  // We no longer sync towns in the SVG because they will be rendered as React components
  svgHost.querySelectorAll("[data-id-town]").forEach((el) => {
    (el as HTMLElement).style.display = "none";
  });
}

export function useLandingIndexMap(selectRegionLabel: string) {
  const { language } = useTranslation();
  const mapAreaRef = useRef<HTMLDivElement>(null);
  const svgHostRef = useRef<HTMLDivElement>(null);
  const [zoneId, setZoneId] = useState<number | null>(null);
  const [townId, setTownId] = useState<number | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({
    x: 0,
    y: 0,
  });

  const [svgTownCoords, setSvgTownCoords] = useState(
    () => new Map<number, { x: number; y: number }>(),
  );

  const {
    data: mapData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["landing-map", language],
    queryFn: () => landingMapApi.getMapData(language),
    staleTime: 30 * 60 * 1000, // 30 minutes
  });

  const regions = useMemo(() => mapData?.regions ?? [], [mapData?.regions]);
  const villages = useMemo(
    () => mergeVillageCoords(mapData?.villages ?? [], svgTownCoords),
    [mapData?.villages, svgTownCoords],
  );

  const townsById = useMemo(
    () => new Map(villages.map((t) => [t.id, t])),
    [villages],
  );

  const activeTown = townId != null ? (townsById.get(townId) ?? null) : null;

  const dropdownLabel =
    zoneId == null
      ? selectRegionLabel
      : (regions.find((r) => r.id === zoneId)?.name ?? selectRegionLabel);

  useEffect(() => {
    const host = svgHostRef.current;
    if (!host) return;
    if (host.dataset.initialized === "true") return;

    // Create a temporary container to manipulate the SVG
    const parser = new DOMParser();
    const doc = parser.parseFromString(franceMapSvg, "image/svg+xml");
    const svg = doc.querySelector("svg");

    if (svg) {
      // Hide all hardcoded markers in the SVG
      svg.querySelectorAll("[data-id-town]").forEach((el) => {
        (el as SVGElement).style.display = "none";
      });
      host.innerHTML = svg.outerHTML;
    } else {
      host.innerHTML = franceMapSvg;
    }

    const svgEl = host.querySelector("svg");
    if (svgEl) {
      setSvgTownCoords(extractTownCoordsFromSvg(svgEl));
    }

    host.dataset.initialized = "true";
  }, []);

  useEffect(() => {
    const host = svgHostRef.current;
    if (!host) return;

    syncMapSelection(host, zoneId);
  }, [zoneId]);

  const selectRegion = useCallback((id: number) => {
    setZoneId(id);
    setTownId(null);
    setDropdownOpen(false);
  }, []);

  const selectTown = useCallback(
    (id: number, clientX?: number, clientY?: number) => {
      const town = townsById.get(id);
      if (!town) return;
      setTownId(id);
      setZoneId(town.zoneId);

      if (clientX != null && clientY != null && mapAreaRef.current) {
        const rect = mapAreaRef.current.getBoundingClientRect();

        setTooltipPos({
          x: clientX - rect.left + 16,
          y: clientY - rect.top - 20,
        });
      }
    },
    [townsById],
  );

  const handleMapClick = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      const host = svgHostRef.current;
      if (!host) return;
      const target = event.target as Element;

      // If clicking inside the host (on a region path)
      if (host.contains(target)) {
        const zoneEl = target.closest("[data-id-zone]");
        if (zoneEl) {
          const id = Number(zoneEl.getAttribute("data-id-zone"));
          if (!Number.isNaN(id)) {
            selectRegion(id);
          }
        }
      }
    },
    [selectRegion],
  );

  return {
    mapAreaRef,
    svgHostRef,
    zoneId,
    activeTown,
    tooltipPos,
    dropdownOpen,
    dropdownLabel,
    regions,
    villages,
    isLoading,
    isError,
    selectRegion,
    selectTown,
    handleMapClick,
    setTownId,
    toggleDropdown: () => setDropdownOpen((o) => !o),
  };
}
