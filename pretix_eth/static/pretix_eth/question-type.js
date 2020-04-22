// payment_eth_html_add_question_type_javascript
$(function () {
    // there is `payment_eth_info` hidden input with list of IDs
    // of the other fields we want to change functionality
    var question_ids = document.getElementById('payment_eth_info').value.split(',');
    question_ids.forEach( function(q_id) {
        document.getElementById(q_id).style.background = "pink";
    } );
} );
