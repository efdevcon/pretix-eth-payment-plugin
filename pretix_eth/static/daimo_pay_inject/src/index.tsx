import { useEffect } from "react";
import * as React from "react";
import { createRoot } from "react-dom/client";
import { Providers } from "./Providers";
import { useDaimoPayStatus, usePayContext } from "@daimo/pay";

inject();

function inject() {
  console.log("Pretix Daimo Pay plugin injecting...");

  const root = document.querySelector("#daimo-pay-inject-root");
  const newRoot = createRoot(root as HTMLElement);
  newRoot.render(<PayInject />);
}

function PayInject() {
  return <Providers children={<Injector />} />;
}

function Injector() {
  const context = usePayContext();

  useEffect(() => {
    // Set payment ID immediately
    context.paymentState.setPayId(window["payment_id"] as any);

    // On click, show the payment modal
    const placeOrderButton = document.querySelector(
      'button.btn-primary[type="submit"]'
    ) as HTMLButtonElement;
    placeOrderButton.disabled = false;
    placeOrderButton.onclick = (e) => {
      e.preventDefault(); // Prevent submit
      context.showPayment({});
    };
  }, []);

  // Once payment succeeds, submit the form.
  const payStatus = useDaimoPayStatus();
  useEffect(() => {
    if (payStatus?.status === "payment_completed") {
      console.log("Payment completed, submitting form");
      window.setTimeout(() => {
        document.forms[0].submit();
      }, 1000);
    }
  }, [payStatus?.status]);

  return null;
}
