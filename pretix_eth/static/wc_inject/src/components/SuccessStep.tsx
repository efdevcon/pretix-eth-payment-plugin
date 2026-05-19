import { useEffect } from 'react'
import type { Quote } from '../WCPaymentApp'
import { readConfig } from '../config'

export function SuccessStep({ quote: _quote, txHash }: { quote: Quote; txHash: string }) {
  useEffect(() => {
    // Redirect to the order detail page, not the payment confirm page.
    //
    // Priority:
    //   1. `frontendOrderUrlTemplate` (admin setting, same one that
    //      overrides the email `{url}` placeholder) — sends the buyer to
    //      the FE order page so the post-payment destination matches the
    //      confirmation email link. Substitutes `{code}` + `{secret}`.
    //   2. Pretix's native order page — fallback when the admin hasn't
    //      configured an FE override.
    const config = readConfig()
    const fe = (config.frontendOrderUrlTemplate || '').trim()
    let target: string | null = null
    if (fe) {
      target = fe
        .replace(/\{code\}/g, encodeURIComponent(config.orderCode))
        .replace(/\{secret\}/g, encodeURIComponent(config.orderSecret))
    } else if (config.pretixOrderUrl) {
      // Pretix-native order URL, computed server-side via build_absolute_uri
      // — already respects the event's custom-domain config, so this works
      // for both /{org}/{event}/... and root-mounted custom domains.
      target = config.pretixOrderUrl
    }
    if (target) {
      const dest = target  // capture for the closure
      const t = setTimeout(() => { window.location.href = dest }, 2000)
      return () => clearTimeout(t)
    }
    // Last-ditch fallback: just reload.
    const t = setTimeout(() => { window.location.reload() }, 2000)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="wc-root">
      <h3 style={{ marginTop: 0, color: '#2e7d32' }}>Payment confirmed</h3>
      <p className="wc-small">
        Transaction: <code style={{ wordBreak: 'break-all' }}>{txHash}</code>
      </p>
      <p>Redirecting to your order...</p>
    </div>
  )
}
