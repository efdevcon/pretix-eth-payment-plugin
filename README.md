# Pretix Ethereum Payment Provider

**[Demo](https://www.loom.com/share/8c71876a9d5348f6a07a8d7e687368b6?sid=5b19c2a2-7502-4cf2-9afe-a865fd04e003)**

## What is this

This is a payment plugin for [Pretix](https://github.com/pretix/pretix) to accept crypto payments from any chain and any coin.

Key features:
- Accept payments in all liquid tokens on major chains, using Daimo Pay.
- Clean 1:1 pricing for stablecoin payments. If a ticket costs $100, user transfers exactly 100.00 USDC, USDT, or DAI on any efficient chain.
- Support for all major EVM rollups + Polygon.
- Automatic bridging and forwarding to a single destination address.
- Built-in refund support, using Peanut Protocol.

## Event Setup Instructions

1. Under the event, go to Settings > Plugins > Payment Providers, enable provider.

2. Under Settings > Payments, enable payment method.

3. Configure the following required settings:
   - `DAIMO_PAY_API_KEY` - API key from pay.daimo.com
   - `DAIMO_PAY_WEBHOOK_SECRET` - Webhook secret for verifying callbacks
   - `DAIMO_PAY_RECIPIENT_ADDRESS` - Address to receive payments (in DAI on Optimism)
   - `DAIMO_PAY_REFUND_EOA_PRIVATE_KEY` - Private key for automated refunds (must be funded with ETH and DAI on Optimism)

## Development Setup

You'll need Python 3.10 and Node >20.

1. Clone this repository
2. Create and activate a virtual environment
3. Run `pip install -e .[dev]` 
4. Setup database: `make devmigrate`
5. Start dev server: `make devserver`
6. Build Daimo Pay checkout: `cd pretix_eth/static/daimo_pay_inject && npm i && npm run build`

You can also use `npm run dev` on that last step to run a watcher.

Finally, go to `http://localhost:8000`. Use `admin@localhost`, password `admin`. Create an org, an event, and follow the event setup instructions above.

You should now have a working development Pretix instance.


## History

It started with [ligi](https://github.com/ligi) suggesting [pretix for Ethereum
Magicians](https://ethereum-magicians.org/t/charging-for-tickets-participant-numbers-event-ticketing-for-council-of-paris-2019/2321/2).

Then it was used for Ethereum Magicians in Paris (shout out to
[boris](https://github.com/bmann) for making this possible) - but accepting ETH
or DAI was a fully manual process there.

Afterwards boris [put up some funds for a gitcoin
bounty](https://github.com/spadebuilders/community/issues/30) to make a plugin
that automates this process. And [nanexcool](https://github.com/nanexcool)
increased the funds and added the requirement for DAI.

The initial version was developed by [vic-en](https://github.com/vic-en) but he
vanished from the project after cashing in the bounty money and left the plugin
in a non-working state.

Then the idea came up to use this plugin for DevCon5 and the plugin was forked
to this repo and [david sanders](https://github.com/davesque), [piper
merriam](https://github.com/pipermerriam), [rami](https://github.com/raphaelm),
[Pedro Gomes](https://github.com/pedrouid), and [Jamie
Pitts](https://github.com/jpitts) brought it to a state where it is usable for
DevCon5 (still a lot of work to be done to make this a good plugin). Currently,
it is semi-automatic. But it now has ERC-681 and Web3Modal
support. If you want to dig a bit into the problems that emerged short before
the launch you can have a look at [this
issue](https://github.com/esPass/pretix-eth-payment-plugin/pull/49)

For DEVcon6 the plugin was extended with some more features like [Layer2 support by Rahul](https://github.com/rahul-kothari). Layer2 will play a significant [role in Ethereum](https://ethereum-magicians.org/t/a-rollup-centric-ethereum-roadmap/4698). Unfortunately DEVcon6 was delayed due to covid - but we where able to use and this way test via the [LisCon](https://liscon.org) ticket sale. As far as we know this was the first event ever offering a Layer2 payment option.
In the process tooling like [Web3Modal](https://github.com/Web3Modal/web3modal/) / [Checkout](https://github.com/Web3Modal/web3modal-checkout) that we depend on was improved.

For Devconnect IST an effort was made to improve the plugin in a variety of ways: WalletConnect support, single receiver mode (accept payments using just one wallet), more networks, automatic ETH rate fetching, improved UI and messaging, and smart contract wallet support. All of these features made it into this version of the plugin, except for smart contract wallet support - issues processing transactions stemming from sc wallets meant that we ultimately had to turn away sc wallet payments altogether.

Finally, for Devconnect 2025, the plugin was rewritten to use [Daimo Pay](https://pay.daimo.com), providing any-chain checkout and automatic refunds. See [DIP-64](https://forum.devcon.org/t/dip-64-universal-checkout-for-devcon-nect/5346).