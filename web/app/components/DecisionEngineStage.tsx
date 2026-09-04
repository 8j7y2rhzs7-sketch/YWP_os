import Image from "next/image";

const TICKER = [
  "DISCIPLINE. DATA. EDGE.",
  "WE DON'T GUESS, WE ANALYZE.",
  "PASS IS AN OFFICIAL ANSWER.",
  "GRIND EVERYDAY. LONGTERM PAYDAY.",
  "LOCK CHECK BEFORE PLACEMENT.",
];

export function DecisionEngineStage({
  experienceId,
  productId,
  hasAccess,
  checkoutUrl,
}: {
  experienceId: string;
  productId: string;
  hasAccess: boolean;
  checkoutUrl?: string;
}) {
  const ticker = [...TICKER, ...TICKER];
  const primaryHref = hasAccess ? "ywpos://slate" : checkoutUrl || "#";
  const primaryLabel = hasAccess ? "Open the app slate" : "Get Daily Access";

  return (
    <div className="shell">
      <div className="sweep" aria-hidden />
      <main className="hero">
        <div className="brandRow">
          <div className="crestWrap">
            <Image
              className="crest"
              src="/brand/crest.png"
              alt="YWP OS crest"
              width={168}
              height={168}
              priority
            />
          </div>
          <div className="brandCopy">
            <p className="eyebrow">The Underdog Strategist</p>
            <h1 className="brandName">YWP OS</h1>
          </div>
        </div>

        <h2 className="headline">Decision Engine</h2>
        <p className="support">
          Live protocol sweeps, honest PASS calls, and lock-checked tickets —
          not a tip sheet. Daily Access is {hasAccess ? "active" : "required"}{" "}
          for product {productId}.
        </p>

        <div className="ctaRow">
          <a className="cta" href={primaryHref}>
            {primaryLabel}
          </a>
          <a className="cta ctaGhost" href={`#experience-${experienceId}`}>
            Experience {experienceId.slice(0, 8)}
          </a>
        </div>

        <div className="statusStrip" id={`experience-${experienceId}`}>
          <div className={`pill ${hasAccess ? "" : "pillWarn"}`}>
            <span className="pillDot" />
            {hasAccess ? "Access cleared" : "Access pending"}
          </div>
          <div className="pill">
            <span className="pillDot" />
            Protocol 2026.09.03
          </div>
          <div className="pill">
            <span className="pillDot" />
            Lock check live
          </div>
        </div>
      </main>

      <div className="tickerWrap" aria-hidden>
        <div className="tickerTrack">
          {ticker.map((line, index) => (
            <span key={`${line}-${index}`}>{line}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
