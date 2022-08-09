import {runPeriodicCheck} from "./periodic_check.js";
import {GlobalPretixEthState} from "./utils.js";


window.addEventListener('load', async () => {
    // run periodic status check if possible
    if (GlobalPretixEthState.elements.submittedTransactionHash !== null) {
        /*
        Page loads with transaction hash present,
        this inidicates a reload in pending state.
        We have to run periodic status change checker on page load.
         */
        await runPeriodicCheck();
    }
});
