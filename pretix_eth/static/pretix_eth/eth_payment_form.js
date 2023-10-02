$(document).ready(function () {
    $("#id_payment_ethereum-currency_type")[0].style = 'display: inline-block; margin-left: 8px; width: auto; cursor: pointer;'

    // Get currencies and their networks from the hidden select
    const extractCurrenciesAndNetworks = () => {
        // Initialize an empty array to store the result
        const currenciesAndNetworks = [];

        // Loop through each option in the select element
        $("#id_payment_ethereum-currency_type option").each(function () {
            // Get the value of the option
            const optionValue = $(this).val();

            // Check if the option is not empty and contains "-" as separator
            if (optionValue !== "" && optionValue.includes(" - ")) {
                // Split the option value into currency and network
                const parts = optionValue.split(" - ");

                // Extract currency and network
                const currency = parts[0]; // Currency
                const network = parts[1]; // Network

                // Find the entry in currenciesAndNetworks array for the currency
                let currencyEntry = currenciesAndNetworks.find(function (entry) {
                    return entry.currency === currency;
                });

                // If the currency entry doesn't exist, create it
                if (!currencyEntry) {
                    currencyEntry = { currency: currency, networks: [] };
                    currenciesAndNetworks.push(currencyEntry);
                }

                // Add the network to the networks array
                currencyEntry.networks.push(network);
            }
        });

        return currenciesAndNetworks;
    }

    // Filters down the main select to only have the networks available for the given currency
    const syncMainSelectOptions = (selectedCurrency, value) => {
        const { currency, networks } = selectedCurrency;

        const mainSelect = $('#id_payment_ethereum-currency_type');

        // Clear options
        mainSelect.empty();

        networks.forEach(function (network) {
            const reconstructedSelectValue = `${currency} - ${network}`;

            mainSelect.append($('<option></option>').attr('value', reconstructedSelectValue).text(network));
        });

        const forcedValue = value || `${currency} - ${networks[0]}`;

        mainSelect.val(forcedValue);
    }

    const createCustomSelects = (networksByCurrency) => {
        const currencySelect = $('<select class="form-control" style="width:auto;display:inline-block;margin-right:5px;cursor: pointer;" id="currencySelector"></select>');
        const mainSelect = $('#id_payment_ethereum-currency_type');

        // Set available networks upon currency change, and sync the hidden select
        currencySelect.change(function () {
            const selectedCurrency = $(this).val();
            const selectedCurrencyEntry = networksByCurrency.find(function (entry) {
                return entry.currency === selectedCurrency;
            });


            const currentNetwork = mainSelect.val().split(' - ').pop();
            const networkExistsForNextCurrency = selectedCurrencyEntry.networks.some(network => network === currentNetwork);

            // If network exists on the next selected currency, force the network to stay the same
            if (networkExistsForNextCurrency) {
                syncMainSelectOptions(selectedCurrencyEntry, `${selectedCurrencyEntry.currency} - ${currentNetwork}`);
            } else {
                syncMainSelectOptions(selectedCurrencyEntry);
            }
        });

        // Add currency options to the currency select
        networksByCurrency.forEach(function (entry) {
            currencySelect.append($('<option></option>').attr('value', entry.currency).text(entry.currency));
        });

        // Force initialize with first currency and first network 
        syncMainSelectOptions(networksByCurrency[0]);

        $('#id_payment_ethereum-currency_type').before(currencySelect);
    }

    const networksByCurrency = extractCurrenciesAndNetworks();
    createCustomSelects(networksByCurrency);
});