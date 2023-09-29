$(document).ready(function(){
    // TODO:
    // * generate token list in the first Select dynamically based on the main Select (there might be more than just ETH and DAI)
    // * based on selected token (eg.: ETH or DAI) dynamically filter options in the main Select
    // * change the description in the main Select from "Choose Network and Token" to just "Choose Network" (in this code - via JS)
    // * style the two Select fields to sit next to each other: left and right
    var currency_select = "<select class='form-control'><option selected>Choose Token</option><option value='ETH'>ETH</option><option value='DAI'>DAI</option></select>";
    $("#id_payment_ethereum-currency_type").before(currency_select);
});
