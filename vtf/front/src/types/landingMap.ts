import type { LandingIndexMapRegion } from "../data/landingIndexMap";

export interface LandingMapVillage {
  id: number;
  zoneId: number;
  href: string;
  title: string;
  place: string;
  department?: string;
  coords: {
    x: number;
    y: number;
  };
}

export interface LandingMapData {
  regions: LandingIndexMapRegion[];
  villages: LandingMapVillage[];
}
