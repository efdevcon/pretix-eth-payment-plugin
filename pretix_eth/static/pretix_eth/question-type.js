/*
 * payment_eth_html_add_question_type_javascript
 */

// from our marked fields obtain all ids of desired questions
function get_payment_eth_question_ids(class_name) {
    var info_elements = document.getElementsByClassName(class_name);
    var payment_eth_question_ids = [];
    for (var i = 0; i < info_elements.length; i++) {
        payment_eth_question_ids = payment_eth_question_ids.concat(
            info_elements[i].value.split(',')
        )
    }
    return payment_eth_question_ids;
}

// try to get question element and do desired changes on it
function change_element(element_id) {
    var element = document.getElementById(element_id);
    if (!element) {
        return;
    }
    // do the actual change of an element
    element.style.background = "pink";
}

$(function () {
    // there are `payment_eth_info` hidden inputs with list of IDs
    // of the other fields we want to change functionality
    var payment_eth_question_ids = get_payment_eth_question_ids('payment_eth_info');
    for (var i = 0; i < payment_eth_question_ids.length; i++) {
        change_element(payment_eth_question_ids[i]);
    }
} );
