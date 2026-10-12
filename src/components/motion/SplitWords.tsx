import { Fragment } from "react";

/**
 * Splits a headline into masked words for data-reveal="words". The split is in
 * the server HTML, so the text reads the same with or without JS; the masks
 * keep descenders by padding the clip box and pulling it back with a margin.
 */
export function SplitWords({ text }: { text: string }) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <>
      {words.map((w, i) => (
        <Fragment key={i}>
          <span className="rv-mask">
            <span className="rv-word">{w}</span>
          </span>
          {i < words.length - 1 && " "}
        </Fragment>
      ))}
    </>
  );
}
