# Pretix Ethereum Payment Provider

## **Warning**

**!! This plugin is not ready for 3rd party production use *yet*.  If you want
to use it you must really understand the code !!  PRs to make it production
ready and more eyes on this code are most welcome!**

## What is this

This is a plugin for [pretix](https://github.com/pretix/pretix). This plugin
supports both Ethereum and DAI.

## History

It started with [ligi](https://ligi) suggesting [pretix for Ethereum
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
to this repo and [ligi](https://ligi.de), [david
sanders](https://github.com/davesque), [piper
meriam](https://github.com/pipermerriam), [rami](https://github.com/raphaelm),
[Pedro Gomes](https://github.com/pedrouid), and [Jamie
Pitts](https://github.com/jpitts) brought it to a state where it is usable for
DevCon5 (still a lot of work to be done to make this a good plugin). Currently,
it is semi-automatic. But it now has ERC-681 and Web3Modal
support. If you want to dig a bit into the problems that emerged short before
the launch you can have a look at [this
issue](https://github.com/esPass/pretix-eth-payment-plugin/pull/49)

For DEVcon6 the plugin was extended with some more features like [Layer2 support by Rahul](https://github.com/rahul-kothari). Layer2 will play a significant [role in Ethereum](https://ethereum-magicians.org/t/a-rollup-centric-ethereum-roadmap/4698). Unfortunately DEVcon6 was delayed due to covid - but we where able to use and this way test via the [LisCon](https://liscon.org) ticket sale. As far as we know this was the first event ever offering a Layer2 payment option.
In the process tooling like [Web3Modal](https://github.com/Web3Modal/web3modal/) / [Checkout](https://github.com/Web3Modal/web3modal-checkout) that we depend on was improved.

### Recently added features

* A panel was added in the web admin interface to upload a list of addresses to
  be associated with each ticket order.
* During the checkout process, an address is chosen for each order from the
  list of remaining addresses created by the address upload process.
* A payment confirmation management command was added that confirms pending
  payments based on the address assigned to them during checkout.  See the
  `confirm_payments` section below for details.

## Development setup

1. Clone this repository, e.g. to `local/pretix-eth-payment-plugin`.
1. Create and activate a virtual environment.
1. Execute `pip install -e .[dev]` within the `pretix-eth-payment-plugin` repo
   directory.
1. Setup a local database by running `make devmigrate`.
1. Fire up a local dev server by running `make devserver`.
1. Visit http://localhost:8000/control/login in a browser windows and enter
   username `admin@localhost` and password `admin` to log in.
1. Enter "Admin mode" by clicking the "Admin mode" text in the upper-right
   corner of the admin interface to create a test organization and event.
1. Follow instructions in [Event Setup Instructions](#event-setup-instructions)

## Event Setup Instructions
1. Under the event, go to Settings -> Plugins -> Payment Providers -> click on Enable under "Pretix Ethereum Payment Provider" 
2. Next, under Settings, go to Payments -> "ETH or DAI" -> Settings -> click on "enable payment option". 
3. Next, scroll down and set the values for the following:
  - "TOKEN_RATE" - This is a JSON e.g. 
    ```
    {"ETH_RATE": 4000, "DAI_RATE": 1}
    ```
    i.e. `KEY` = `<CRYPTO_SMBOL>_RATE` and `VALUE` = value of 1 unit in USD. Above example is for 1 ETH = 4000$
  - Select the networks you want under the "Networks" option - Choose from Ethereum Mainnet, Optimism, Arbitrum and their testnets.
  - "NETWORK_RPC_URLS" - This is a JSON e.g.
    ```
    {
      "L1_RPC_URL": "https://mainnet.infura.io/v3/somekeyhere",
      "Rinkeby_RPC_URL": "...",
      "RinkebyArbitrum_RPC_URL": "..."  
    }
    ```
    i.e. `KEY` = `<Network ID>_RPC_URL` and `VALUE` = RPC URL. Network IDs can be found [in tokens.py](pretix_eth/network/tokens.py)
4. Under Event, go to Settings -> Upload Wallet Addresses - upload some ethereum addresses 


You can now play with the event by clicking on the "Go to Shop" button at the top left (next to the event name)

## Automatic payment confirmation with the `confirm_payments` command

This plugin includes a [django management
command](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/#module-django.core.management)
that can be used to automatically confirm orders from the Ethereum address
associated with each order.  By default, this command will perform a dry run
which only displays payment records that would be modified and why but without
actually modifying them.  Here's an example invocation of this command:
```bash
python -mpretix confirm_payments \
    --event-slug=devcon-5 \
    --no-dry-run
```
Above, the `confirm_payments` command uses the `--event-slug` argument to
determine the list of unconfirmed payments to check (those associated with that
event).  It then inspects the address that was associated with each order (at
the time the ticket was reserved) to determine if sufficient payments were made
for the order.  It may check for an ethereum payment or some kind of token
payment depending on what was chosen during the checkout process.  Token
payments will be checked using the given token address provided via the
`--token-address` CLI flag.  The `--no-dry-run` flag directs the command to
update order statuses based on the checks that are performed.  Without this
flag, the command will only display how records would be modified.  All
interactions with the blockchain are performed via web3.py and the node
identified by the web3 provider URI given in by the `--web3-provider-uri` CLI
flag.  For more information on the format of web3 provider URIs, see
[here](https://web3py.readthedocs.io/en/stable/providers.html#provider-via-environment-variable).

For more details about the `confirm_payments` command and its options, the
command may be invoked with `--help`:
```bash
python -mpretix confirm_payments --help
```

## License

Copyright 2019 Victor (https://github.com/vic-en)

Released under the terms of the Apache License 2.0
