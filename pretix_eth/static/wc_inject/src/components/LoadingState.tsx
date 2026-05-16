/**
 * In-frame loading placeholder. Renders inside the same `wc-root` wrapper
 * as every other React-rendered state, so the surrounding Pretix page
 * doesn't reflow when we crossfade between (boot → React, disconnect →
 * loader → connect, initial options fetch).
 *
 * Uses the shared `.wc-spinner--lg` ring + ghost-track from styles.css —
 * identical to the boot loader and the status card pending state, so the
 * full plugin has one loading vocabulary.
 */
export function LoadingState({ message }: { message: string }) {
  return (
    <div className="wc-root wc-loading-state">
      <div className="wc-spinner wc-spinner--lg" aria-hidden="true" />
      <p className="wc-loading-state-message" aria-live="polite">{message}</p>
    </div>
  )
}
