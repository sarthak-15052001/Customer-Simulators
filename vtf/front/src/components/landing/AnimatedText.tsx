import { useMemo } from "react";

type Props = {
  text: string;
  className?: string;
  startDelayMs?: number;
  staggerMs?: number;
  cycleKey: number;
};

export function AnimatedText({
  text,
  className,
  startDelayMs = 0,
  staggerMs = 45,
  cycleKey,
}: Props) {
  const tokens = useMemo(() => text.split(/(\s+)/), [text]);

  return (
    <span key={cycleKey} className={className} aria-label={text}>
      {tokens.map((tok, tokenIdx) => {
        if (/^\s+$/.test(tok)) {
          return (
            <span key={`${cycleKey}-ws-${tokenIdx}`} aria-hidden="true">
              {tok}
            </span>
          );
        }

        const chars = Array.from(tok);
        const baseDelay = startDelayMs + tokenIdx * 10;
        return (
          <span
            key={`${cycleKey}-w-${tokenIdx}`}
            aria-hidden="true"
            style={{ display: "inline-block", whiteSpace: "nowrap" }}
          >
            {chars.map((ch, i) => (
              <span
                key={`${cycleKey}-${tokenIdx}-${i}`}
                className="char-animation"
                style={{
                  animationDelay: `${(baseDelay + i * staggerMs) / 1000}s`,
                }}
                aria-hidden="true"
              >
                {ch}
              </span>
            ))}
          </span>
        );
      })}
    </span>
  );
}
