from web3 import Web3
from eth_typing import HexStr
import secrets
from eth_abi import encode
from decimal import Decimal
import sys
from decimal import Decimal

# Constants
RPC_URL = "https://mainnet.optimism.io"
CHAIN_ID = 10  # Optimism mainnet
DAI_ADDRESS = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"
DAI_DECIMALS = 18
PEANUT_CONTRACT = "0xb75B6e4007795e84a0f9Db97EB19C6Fc13c84A5E"  # Optimism, Peanut v4.3

def create_peanut_link(tokenAmount: Decimal, refundEoaPrivateKey: str) -> str:
    w3 = get_web3_instance()    
    account = w3.eth.account.from_key(refundEoaPrivateKey)
    print(f"PAY: account created from private key: {account.address}")
    
    # Setup contracts
    token_contract = get_token_contract(w3)
    print("PAY: token contract setup complete.")
    
    peanut_contract = get_peanut_contract(w3)
    print("PAY: peanut contract setup complete.")
    
    # Generate password and hash
    password = secrets.token_hex(12) # 96 bits
    private_key = w3.keccak(text=password).hex()
    key_account = w3.eth.account.from_key(private_key)
    print(f"PAY: generated key: {key_account.address}")
    
    # Convert amount to wei
    amount_wei = int(tokenAmount * 10**DAI_DECIMALS)
    print(f"PAY: amount converted to wei: {amount_wei}")
    
    # Approve tokens
    nonce = w3.eth.get_transaction_count(account.address)
    approve_receipt = approve_token(w3, account, token_contract, amount_wei, nonce)
    if approve_receipt.status != 1:
        raise Exception("token approval failed")
    print(f"PAY: tokens approved. transaction receipt: {approve_receipt.transactionHash.hex()}")
    
    # Make deposit
    nonce = nonce + 1
    deposit_receipt = make_deposit(w3, account, peanut_contract, amount_wei, key_account.address, nonce)
    if deposit_receipt.status != 1:
        raise Exception(f"deposit failed. low balance? tried sending ${tokenAmount} DAI from {account.address}")
    print(f"PAY: deposit made. transaction receipt: {deposit_receipt.transactionHash.hex()}")
    
    # Create link
    deposit_idx = int(deposit_receipt.logs[1].topics[1].hex(), 16) # log 0 = Transfer, log 1 = DepositEvent
    link = f"https://peanut.to/claim?c={CHAIN_ID}&v=v4.3&i={deposit_idx}#p={password}"
    print(f"PAY: peanut claim link created: {link}")
    
    return link

def get_web3_instance():
    return Web3(Web3.HTTPProvider(RPC_URL))

def get_token_contract(w3):
    # Minimal ERC20 ABI
    abi = [
        {
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [
                {"name": "", "type": "bool"}
            ],
            "stateMutability": "nonpayable",
            "type": "function"
        },
    ]
    return w3.eth.contract(address=DAI_ADDRESS, abi=abi)

def get_peanut_contract(w3):
    # Minimal Peanut ABI
    abi = [
        {
            "inputs": [
                {"name": "_tokenAddress", "type": "address"},
                {"name": "_contractType", "type": "uint8"},
                {"name": "_amount", "type": "uint256"},
                {"name": "_tokenId", "type": "uint256"},
                {"name": "_pubKey20", "type": "address"}
            ],
            "name": "makeDeposit",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        }
    ]
    return w3.eth.contract(address=PEANUT_CONTRACT, abi=abi)

def approve_token(w3, account, token_contract, amount_wei, nonce):
    approve_tx = token_contract.functions.approve(
        PEANUT_CONTRACT,
        amount_wei
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(approve_tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)

def make_deposit(w3, account, peanut_contract, amount_wei, pub_key_20, nonce):
    deposit_tx = peanut_contract.functions.makeDeposit(
        DAI_ADDRESS,
        1,  # tokenType (1 = ERC20)
        amount_wei,
        0,  # tokenId (not used for ERC20)
        pub_key_20
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': w3.eth.gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(deposit_tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def main():
    if len(sys.argv) < 3:
        print("Usage: create-link.py <amount> <privKey>")
        sys.exit(1)

    amount = Decimal(sys.argv[1])
    privKey = sys.argv[2]
    link = create_peanut_link(amount, privKey)
    print(f"Generated Peanut claim link: {link}")

if __name__ == '__main__':
    main()