/**
 * The Money Map preview on the landing page.
 *
 * Static, and marked EXAMPLE in three separate places: the header band, a badge
 * on every row, and the caption. The organisation names are obviously invented,
 * and the figures are the ones the real product would render for that
 * data - including an opportunity whose pay is *not published*, because a
 * preview that shows only tidy numbers misrepresents what the product actually
 * looks like on real listings.
 */

const ROWS = [
  {
    title: "Expert network — data & AI practitioners",
    org: "Northlight Expert Circle",
    score: 91,
    band: "Highly actionable",
    pay: "€120–€250/hour",
    verified: false,
  },
  {
    title: "Freelance data platform review",
    org: "Hansa Logistik Werke",
    score: 88,
    band: "Highly actionable",
    pay: "€850–€1,100/day gross",
    verified: true,
  },
  {
    title: "Paid workshop facilitator",
    org: "Civic Skills Werkstatt",
    score: 83,
    band: "Actionable",
    pay: "€700–€900/day gross",
    verified: true,
  },
  {
    title: "Part-time founder programme",
    org: "Ostwind Founder Lab",
    score: 78,
    band: "Review first",
    pay: null,
    verified: false,
  },
];

export function MoneyMapPreview() {
  return (
    <figure className="overflow-hidden rounded-[--radius-card] border border-rule bg-paper-raised shadow-[0_1px_2px_rgba(20,22,26,0.04),0_12px_32px_-16px_rgba(20,22,26,0.18)]">
      <div className="flex items-center justify-between border-b border-rule bg-demo-wash px-5 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-demo">
          Example — fictional data
        </span>
        <span className="text-[11px] text-demo">Not live offers</span>
      </div>

      <div className="border-b border-rule px-5 py-5">
        <p className="eyebrow mb-1">Your Money Map</p>
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
          <span className="tnum text-2xl font-semibold">+€1,500</span>
          <span className="text-sm text-ink-muted">monthly goal</span>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4 border-t border-rule pt-4">
          <div>
            <p className="eyebrow mb-0.5">Secured</p>
            <p className="tnum text-lg font-semibold">€0</p>
          </div>
          <div>
            <p className="eyebrow mb-0.5">Earned</p>
            <p className="tnum text-lg font-semibold">€0</p>
          </div>
          <div>
            <p className="eyebrow mb-0.5">Potential</p>
            <p className="tnum text-lg font-semibold text-ink-muted">4 found</p>
          </div>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">
          Secured and earned are separate from potential, always. The progress bar moves only
          when money is actually committed.
        </p>
      </div>

      <ul className="divide-y divide-rule">
        {ROWS.map((row) => (
          <li key={row.title} className="flex items-start gap-4 px-5 py-3.5">
            <span className="tnum mt-0.5 w-9 shrink-0 text-right text-lg font-semibold">
              {row.score}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{row.title}</p>
              <p className="truncate text-xs text-ink-faint">
                {row.org} · {row.band}
              </p>
            </div>
            <span className="mt-0.5 shrink-0 text-right text-xs">
              {row.pay ? (
                <>
                  <span className="tnum">{row.pay}</span>
                  {!row.verified ? (
                    <span className="block text-[10px] text-ink-faint">unconfirmed</span>
                  ) : null}
                </>
              ) : (
                <span className="italic text-ink-faint">Not published</span>
              )}
            </span>
          </li>
        ))}
      </ul>

      <figcaption className="border-t border-rule bg-paper-sunk px-5 py-3 text-[11px] leading-relaxed text-ink-faint">
        An illustration of the real interface using fictional organisations. One of these four
        publishes no compensation at all — which is the normal case for grants and programmes,
        and why the product counts them separately instead of guessing.
      </figcaption>
    </figure>
  );
}
