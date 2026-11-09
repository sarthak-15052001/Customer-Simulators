export function formatDateDDMMYYYY(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (!d || Number.isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export function formatDateRangeDDMMYYYY(
  startIso?: string | null,
  endIso?: string | null,
): string | null {
  if (!startIso) return null;
  const s = formatDateDDMMYYYY(startIso);
  const e = endIso ? formatDateDDMMYYYY(endIso) : null;
  return e ? `${s} — ${e}` : s;
}
