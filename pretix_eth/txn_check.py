import codecs

def check_txn_confirmation(txn_hash, from_address, to_address, currency, amount):
    from_address = from_addres.lower()
    to_address = to_addres.lower()
    try:
        txn_receipt_payload = { "id": 1337, "jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [txn_hash] }
        result = requests.post('https://api.myetherwallet.com/eth', data=txn_receipt_payload)
        json_result = result.json()
        txn_receipt = json_result['result']
        if txn_receipt and txn_receipt['status'] == '0x1':
          txn_hash_payload = { "id": 1337, "jsonrpc": "2.0", "method": "eth_getTransactionByHash", "params": [txn_hash] }
          result = requests.post('https://api.myetherwallet.com/eth', data=txn_hash_payload)
          json_result = result.json()
          txn_details = json_result['result']
          if txn_details:
            ## TODO: include timestamp check
            if (txn_details['from'] == from_address):
                if (currency == 'ETH'):
                  eth_value_in_wei = txn_details['value']
                  if (eth_value_in_wei):
                      eth_value = to_wei(eth_value_in_wei)
                      if (txn_details['to'].lower() == to_address and eth_value >= float(amount)):
                          return True
                else:
                  dai_data = txn_details['input']
                  token_transfer_hash = '0xa9059cbb'
                  if dai_data.startswith(token_transfer_hash):
                      (address, amount) = extract_params(dai_data)
                      if (address == to_address and amount >= float(amount)):
                          return True
    except NameError:
        return False
    except TypeError:
        return False
    except AttributeError:
        return False
    return False

def extract_params(value):
    address = ("0x" + value[10:][:64][:40]).lower()
    amount = to_wei(value[10:][64:])
    return (address, amount)

def remove_0x_prefix(value):
    if value.lower().startswith("0x"):
        return value[2:]
    return value


def sanitize_hex(value):
    if (hex_value % 2):
        hex_value = "0x0" + remove_0x_prefix(hex_value)
    return hex_value

def to_wei(hex_value):
    hex_value = sanitize_hex(hex_value)
    bytes_value = codecs.decode(remove_0x_prefix(hex_value), "hex") 
    int_value = int.from_bytes(bytes_value, sys.byteorder)
    return int_value / (1 ** 18)
