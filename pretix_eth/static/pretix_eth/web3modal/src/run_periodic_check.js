import { runPeriodicCheck } from "./periodic_check.js";
import {
    GlobalPretixEthState,
    convertHashToExplorerLink
} from "./interface.js";

window.addEventListener('load', async () => {
    // run periodic status check if possible
    const transaction_hash_el = GlobalPretixEthState.elements.submittedTransactionHash
    if (transaction_hash_el !== null) {
        /*
        Page loads with transaction hash present,
        this inidicates a reload in pending state.
        We have to run periodic status change checker on page load.
         */
        const chain_id = GlobalPretixEthState.elements.aNetworkData.getAttribute("data-chain-id")
        const hash = transaction_hash_el.innerText;
        transaction_hash_el.innerHTML = convertHashToExplorerLink(chain_id, hash);
        await runPeriodicCheck();
    }
});
