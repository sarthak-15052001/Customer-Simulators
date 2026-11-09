import { vtfUrl } from "../../config/site";

/** Keys match `footer.col1.*` translation keys (order = live site). */
export const FOOTER_COL1_LINKS: { key: string; href: string }[] = [
  { key: "who", href: vtfUrl("qui-sommes-nous") },
  { key: "villages", href: vtfUrl("decouvrir-villages-vacances-vtf") },
  { key: "commitments", href: vtfUrl("nos-engagements") },
  { key: "agencies", href: vtfUrl("contactez-nous") },
  { key: "partners", href: vtfUrl("nos-partenaires") },
  { key: "press", href: vtfUrl("espace-presse") },
];

export const FOOTER_COL2_LINKS: { key: string; href: string; external?: boolean }[] = [
  { key: "blog", href: "https://blog.vtf-vacances.com/", external: true },
  { key: "brochures", href: vtfUrl("brochures") },
  { key: "app", href: vtfUrl("application-mobile") },
];

export const FOOTER_COL3_LINKS: { key: string; href: string }[] = [
  { key: "schoolDates", href: vtfUrl("dates-des-vacances-scolaires") },
  { key: "faq", href: vtfUrl("foire-aux-questions") },
  { key: "prepare", href: vtfUrl("partir-en-vacances-avec-vtf/preparer-mes-vacances") },
];



export const FOOTER_LEGAL_LINKS: { key: string; href: string }[] = [
  { key: "cookies", href: vtfUrl("politique-de-cookie") },
  { key: "insurance", href: vtfUrl("plan-annulation-et-assurances") },
  { key: "terms", href: vtfUrl("conditions-generales-de-ventes") },
  { key: "legal", href: vtfUrl("mentions-legales") },
];

export const FOOTER_CONTACT_URL = vtfUrl("contactez-nous");
