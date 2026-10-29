/**
 * What the wallet actually answered, for the phase=error beacon. viem
 * wraps a wallet's reply (TransactionExecutionError → UnknownRpcError →
 * the provider's own error), and the outer shortMessage is often just
 * "An unknown RPC error occurred."; the numeric code and the wallet's
 * message sit deeper in the `cause` chain.
 *
 * Runs inside handlePay's catch, so it must never throw: wallets can throw
 * anything (an object as `message`, a bare string), and every field is
 * coerced to a string. The message is clipped to MAX_MESSAGE so the beacon
 * URL stays short (the server clips to the same length).
 */
const MAX_MESSAGE = 400

function text(v: unknown): string {
  if (typeof v === 'string') return v
  if (v == null) return ''
  try {
    return typeof v === 'object' ? JSON.stringify(v) : String(v)
  } catch {
    return ''
  }
}

export function walletErrorDetails(e: unknown): { name: string; code: string; message: string } {
  const chain: Array<{ name?: string; code?: unknown; shortMessage?: string; details?: string; message?: string; cause?: unknown }> = []
  let cur: unknown = e
  for (let depth = 0; cur && typeof cur === 'object' && depth < 8; depth++) {
    const c = cur as (typeof chain)[number]
    chain.push(c)
    cur = c.cause
  }
  const outer = chain[0] ?? {}
  // Innermost first: the wallet's own code sits below viem's wrappers
  // (UnknownRpcError carries a generic -1 of its own).
  const inward = [...chain].reverse()
  const withCode = inward.find(c => typeof c.code === 'number' || (typeof c.code === 'string' && c.code !== ''))
  const innermost = chain[chain.length - 1] ?? outer
  // Most specific class name: a provider's plain `Error` says less than
  // the viem class wrapping it (UnknownRpcError, UserRejectedRequestError).
  const named = inward.find(c => typeof c.name === 'string' && c.name && c.name !== 'Error')
  const outerText = text(outer.shortMessage) || text(outer.message) || text(e) || String(e)
  // viem keeps the provider's raw message in `details`; fall back to the
  // innermost error's message when the outer one is only a wrapper.
  const walletText = text(outer.details) || (innermost !== outer ? text(innermost.message) : '')
  const message = walletText && !outerText.includes(walletText) ? `${outerText} Details: ${walletText}` : outerText
  return {
    name: named?.name || text(innermost.name) || 'Error',
    code: withCode ? String(withCode.code) : '',
    message: message.slice(0, MAX_MESSAGE),
  }
}
