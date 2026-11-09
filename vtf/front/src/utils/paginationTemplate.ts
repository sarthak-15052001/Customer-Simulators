/** Replaces `{{key}}` placeholders (e.g. i18n pagination strings). */
export function fillPaginationTemplate(
  template: string,
  vars: Record<string, string | number>,
): string {
  let acc = template;
  for (const [k, v] of Object.entries(vars)) {
    acc = acc.split(`{{${k}}}`).join(String(v));
  }
  return acc;
}
