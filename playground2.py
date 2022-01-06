import algosdk
from pyteal import *
from algosdk.encoding import checksum, encode_address
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from pyteal.ast import app
from utils.tealhelpher import create_app, delete_app, update_app, read_global_state, get_private_key_from_mnemonic, intToBytes, default_algod_api_token, default_algod_api_address
from utils.tealhelpher import *
from SatanApp import app_ready_to_go, min_cost_for_app
import base64
import time
import hashlib

asaId1 = 56335894
asaId2 = 56335957
req_fees = 4000
app_id = 56519739

def main():
    # initialize an algodClient
    algod_client = algod.AlgodClient(default_algod_api_token(), default_algod_api_address(), headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(default_algod_api_token(), default_indexer_api_address(), headers={'User-Agent': 'py-algorand-sdk'})

    payer_address = '37UGYG6N2W4WO3GWASOLY4AFVYJTT5MQYPYEJHNQ5H2FZYW5ORIQAS6I2M'
    payer_mnem = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
    payer_private_key = get_private_key_from_mnemonic(payer_mnem)


    app_id = 56905340
    delete_app(algod_client, algod_indexer_client, app_id, payer_private_key)

    app_id = app_ready_to_go(algod_client, algod_indexer_client, payer_private_key, decode_address(payer_address))

    app_address = algosdk.encoding.encode_address(checksum(b'appID'+(app_id).to_bytes(8, 'big')))
    print(app_address)
    print(app_id)

    fee_payment_provider(algod_client, algod_indexer_client,101000,payer_private_key,app_address, True)
    app_args = ["OptIn"]
    call_app(algod_client, payer_private_key, app_id, app_args)

    txs = fee_payment_provider_tx(algod_client, algod_indexer_client, 1000, 56335894, payer_private_key, app_address)
    for tx in txs:
        stx = tx.sign(payer_private_key)
        tx_id = algod_client.send_transaction(stx)
        # wait for confirmation
        wait_for_confirmation(algod_client, tx_id, 5) 

    app_args = ["ITxn"]
    call_app(algod_client, payer_private_key, app_id, app_args)

    delete_app(algod_client, algod_indexer_client, app_id, payer_private_key)

    
if __name__ == "__main__":
    main()