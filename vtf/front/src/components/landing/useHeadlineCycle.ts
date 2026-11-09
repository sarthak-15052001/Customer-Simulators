import { useEffect, useState } from "react";
import {
  HEADLINE_ANIM_MS,
  HEADLINE_PAUSE_MS,
  HEADLINE_STAGGER_MS,
  HEADLINE_TITLE2_CYCLE_DELAY_MS,
} from "../../utils/landing.constants";

function charCount(text: string): number {
  return Array.from(text).length;
}

export function useHeadlineCycle(title1: string, title2: string) {
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    const end1 = charCount(title1) * HEADLINE_STAGGER_MS + HEADLINE_ANIM_MS;
    const end2 =
      HEADLINE_TITLE2_CYCLE_DELAY_MS +
      charCount(title2) * HEADLINE_STAGGER_MS +
      HEADLINE_ANIM_MS;
    const total = Math.max(end1, end2) + HEADLINE_PAUSE_MS;
    const id = window.setTimeout(() => setCycle((c) => c + 1), total);
    return () => window.clearTimeout(id);
  }, [cycle, title1, title2]);

  return cycle;
}
