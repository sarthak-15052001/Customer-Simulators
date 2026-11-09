export const ENDPOINTS = {
  HEADER_BANNER: "/api/v5/header-banner",
  VILLAGES: {
    BASE: "/villages",
    DETAILS: (id: string | number) => `/villages/${id}`,
  },
  REGIONS: {
    BASE: "/regions",
    ACTIVITIES: (regionKey: string) =>
      `/regions/${encodeURIComponent(regionKey)}/activities`,
  },
  PRICING: {
    FAMILY_QF: "/family/qf",
    ESTIMATE_STAY: "/estimate/stay",
  },
  /** Catalog singleton — active tariff rules blob. */
  PRICING_RULES: "/pricing-rules",
  ATTRACTIONS: {
    BASE: "/attractions",
  },
  MEALS: "/meals",
  FUELS: "/fuels",
  TRANSPORT: {
    CAR: "/transport/car",
    TRAIN: "/transport/train",
  },
  SEASON: {
    RETRIEVE: "/season",
  },
  MARKETING_SEASONS: "/marketing-seasons",
  ENVIRONMENTS: "/environments",
  PROMOS: {
    CATALOG: "/promos/catalog",
    AVAILABLE: "/promos/available",
  },
  FORMULES: "/formules",
  ANIMATIONS: "/animations",
  MAILER: {
    SEND_SIMULATION: "/mailer/send-simulation",
  },
  LANDING: {
    MAP: "/landing/map",
  },
  SIMULATIONS: {
    PDF: "/simulations/pdf",
  },
} as const;

export default ENDPOINTS;
