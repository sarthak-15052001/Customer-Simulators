export function buildSimulationPdfFileName(
  villageName?: string | null,
  dateStart?: string | null,
  dateEnd?: string | null,
): string {
  const village = (villageName?.trim() || "VTF").replace(/\s+/g, "-");
  const dates = dateStart && dateEnd ? `_${dateStart}_${dateEnd}` : "";
  return `VTF-${village}${dates}`;
}

