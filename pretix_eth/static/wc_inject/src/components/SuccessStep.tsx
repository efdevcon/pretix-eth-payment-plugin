import { useEffect } from 'react'
import type { Quote } from '../WCPaymentApp'
import { readConfig } from '../config'

export function SuccessStep({ quote: _quote, txHash }: { quote: Quote; txHash: string }) {
  useEffect(() => {
    // Redirect to the order detail page, not the payment confirm page
    const config = readConfig()
    const match = window.location.pathname.match(/^\/([^/]+)\/([^/]+)/)
    if (match) {
      const [, organizer, event] = match
      const orderUrl = `/${organizer}/${event}/order/${config.orderCode}/${config.orderSecret}/`
      const t = setTimeout(() => { window.location.href = orderUrl }, 2000)
      return () => clearTimeout(t)
    }
    // Fallback: just reload
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
