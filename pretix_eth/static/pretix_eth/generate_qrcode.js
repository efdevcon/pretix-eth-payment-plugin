(function () {
    var qrContent = $("a#pretix-eth-qr-anchor").attr("href");

    if (qrContent.length > 0) {
        $("#pretix-eth-qr-div").qrcode(qrContent);
    }
})();
