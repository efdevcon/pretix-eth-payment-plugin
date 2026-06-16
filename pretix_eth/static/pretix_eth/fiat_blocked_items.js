/**
 * Mirrors a checkbox group's selected values into a sibling hidden input
 * as a comma-separated list of IDs. Used by the Pretix admin "Items that
 * block fiat payment" setting so the operator gets a checklist UI while
 * Pretix's HierarkeyForm still sees a plain string field (round-trips
 * reliably, unlike MultipleChoiceField in this context).
 *
 * Pairing convention:
 *   <input type="hidden" id="id_payment_walletconnect_fiat_blocked_items" ...>
 *   <div data-fiat-cb-group="id_payment_walletconnect_fiat_blocked_items">
 *     <input type="checkbox" value="145"> ...
 *     ...
 *   </div>
 *
 * The script wires every matching pair on DOMContentLoaded — no per-page
 * configuration required.
 */
(function () {
  function syncFromGroup(group, hidden) {
    var ids = []
    group.querySelectorAll('input[type="checkbox"]:checked').forEach(function (cb) {
      ids.push(cb.value)
    })
    hidden.value = ids.join(', ')
  }

  function wire() {
    document.querySelectorAll('[data-fiat-cb-group]').forEach(function (group) {
      // Idempotency: the widget includes the <script src> inline, so on
      // some Pretix template paths this file could load twice. Mark each
      // group on first wiring and skip subsequent passes.
      if (group.dataset.fiatWired === '1') return
      group.dataset.fiatWired = '1'

      var hiddenId = group.getAttribute('data-fiat-cb-group')
      var hidden = document.getElementById(hiddenId)
      if (!hidden) return
      group.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
        cb.addEventListener('change', function () { syncFromGroup(group, hidden) })
      })
      // Also sync once at load so a manually-edited hidden value (rare,
      // but possible during migration) stays consistent with the boxes.
      syncFromGroup(group, hidden)
    })
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire)
  } else {
    wire()
  }
})()
