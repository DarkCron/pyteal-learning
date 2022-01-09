import algosdk
from ledger import *
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
from pairing import pair, depair

asaId1 = 56335894
asaId2 = 56335957
req_fees = 4000
app_id = 56519739

def b64len(b64str):
    """
    Calculate the length in bytes of a base64 string.
    This function could decode the base64 string to a binary blob and count its
    number of bytes with len(). But, that's inefficient and requires more
    memory that really needed.
    Base64 encodes three bytes to four characters. Sometimes, padding is added
    in the form of one or two '=' characters.
    So, the following formula allows to know the number of bytes of a base64
    string without decoding it::
        (3 * (length_in_chars / 4)) - (number_of_padding_chars)
    :param str b64str: A base64 encoded string.
    :return: Length, in bytes, of the binary blob encoded in base64.
    :rtype: int
    """
    return (3 * (len(b64str) / 4)) - b64str[-2:].count('=')


def main():
    # initialize an algodClient
    algod_client = algod.AlgodClient(default_algod_api_token(), default_algod_api_address(), headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(default_algod_api_token(), default_indexer_api_address(), headers={'User-Agent': 'py-algorand-sdk'})

    create_marker(algod_client, algod_indexer_client, asaId1, asaId2)
    get_pair_marker_id(algod_indexer_client, asaId1, asaId2)
    marker_id = get_pair_marker_id(algod_indexer_client, asaId1, asaId2)

    payer_address = 'KTNKJPJHLBTVLHMPPR5GXJ37SCMGZQ3TTFAVVGVAU6IPEQRPUJO57T736Y'
    payer_mnem = 'void hobby pyramid illness orphan arena blur service energy ranch welcome diesel behind become plastic only core audit rookie cage swap extra milk above mass'
    payer_private_key = get_private_key_from_mnemonic(payer_mnem)

    # unfreeze(algod_client, algod_indexer_client, id, payer_address)
    # txs = fee_payment_provider_tx(algod_client, algod_indexer_client, 1, id, get_private_key_from_mnemonic(MARKER_MNEM), payer_address)
    
    # for tx in txs  :
    #     stx = tx.sign(get_private_key_from_mnemonic(MARKER_MNEM))
    #     tx_id = algod_client.send_transaction(stx)
    #     # wait for confirmation
    #     wait_for_confirmation(algod_client, tx_id, 5) 

    # app_id = 57571269
    # app_args = ["OptIn"]
    # call_app(algod_client, payer_private_key, app_id, app_args)
    # delete_app(algod_client, algod_indexer_client, app_id, payer_private_key)
    args = {}
    args['ASA1'] = asaId1
    args['ASA2'] = asaId2
    args['MARKER'] = marker_id

    app_id = app_ready_to_go(algod_client, algod_indexer_client, payer_private_key, decode_address(payer_address), args)

    app_address = algosdk.encoding.encode_address(checksum(b'appID'+(app_id).to_bytes(8, 'big')))
    print(app_address)
    print(app_id)

    fee_payment_provider(algod_client, algod_indexer_client,105000,payer_private_key,app_address, True)
    app_args = ["Test"]
    call_app(algod_client, payer_private_key, app_id, app_args)
    app_args = ["OptIn"]
    call_app(algod_client, payer_private_key, app_id, app_args)

    #app_args = ["ITxn"]
    #call_app(algod_client, payer_private_key, app_id, app_args)
    #delete_app(algod_client, algod_indexer_client, app_id, payer_private_key)

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