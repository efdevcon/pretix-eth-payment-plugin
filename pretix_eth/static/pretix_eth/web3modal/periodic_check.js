import {getCookie, GlobalPretixEthState} from "./utils.js";

async function periodicCheck() {
    let url = GlobalPretixEthState.elements.aOrderDetailURL.getAttribute("data-order-detail-url");
    const csrf_cookie = getCookie('pretix_csrftoken')

    let response = await fetch(url, {
        headers: {
            'X-CSRF-TOKEN': csrf_cookie,
            'HTTP-X-CSRFTOKEN': csrf_cookie,
        }});

    if (response.ok) {
        let data = await response.json()
        if (GlobalPretixEthState.lastOrderStatus === '') {
            GlobalPretixEthState.lastOrderStatus = data.status;
        } else if (GlobalPretixEthState.lastOrderStatus !== data.status) {
            // status has changed to PAID
            if (data.status === 'p') {
                location.reload();
            }
        }
    }
}

async function runPeriodicCheck() {
  while (true) {
    await periodicCheck();
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}

export {runPeriodicCheck};