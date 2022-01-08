import algosdk
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
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

def main():
    print(pair(asaId1, asaId2))
    print(depair(pair(asaId1, asaId2)))
    4294967296
    Sha256(Int(6347473116554983))
    # initialize an algodClient
    algod_client = algod.AlgodClient(default_algod_api_token(), default_algod_api_address(), headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(default_algod_api_token(), default_indexer_api_address(), headers={'User-Agent': 'py-algorand-sdk'})

    pk, a = generate_algorand_keypair()

    temp_address = 'FR7MXJ65N2F654VGLIQMOTSUDMNPLR4ZGPPL4O7IGBJ36F5BSQ7LQ25FHM'
    payer_address = '37UGYG6N2W4WO3GWASOLY4AFVYJTT5MQYPYEJHNQ5H2FZYW5ORIQAS6I2M'

    temp_mnem = 'hurry zebra brush boy shoulder scan salmon parent gloom december slice six tunnel unveil direct slice express sample draft wave mad unhappy ginger ability seminar'
    payer_mnem = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
    

    temp_private_key = get_private_key_from_mnemonic(temp_mnem)
    #h = decode_address('66YMAS3O7C5BD3RDOQLCDGZ7EIYUQS7QAKQ2AXI74T6P3FJZWAYZE6HTVM')
    #v = base64.b64decode('Y7cARyLxrN41LTfquxMFfEmwQpBNGzP35NCdprv76Fw=').decode('utf-8')
    #hhh = h.hexdigest()
    #ha = Sha512_256(56699746)
    a = algod_indexer_client.applications(56701582)

    payer_private_key = get_private_key_from_mnemonic(payer_mnem)
    payer_address = account.address_from_private_key(payer_private_key)

    print("Global state:", read_global_state(algod_indexer_client ,account.address_from_private_key(temp_private_key), 56530113))
    #delete_app(algod_client, algod_indexer_client, 56701582, payer_private_key)

    #fee_payment_provider(algod_client, algod_indexer_client,4000,payer_private_key,temp_address, True)

    min_amt = min_cost_for_app()
    missing_amt = make_sure_act_has_min_cost_plus(algod_indexer_client, min_amt, temp_address,req_fees)
    if missing_amt > 0:
        fee_payment_provider(algod_client, algod_indexer_client,missing_amt + req_fees,payer_private_key,temp_address, False)
    
    app_id = app_ready_to_go(algod_client, algod_indexer_client, temp_private_key, decode_address(payer_address))

    print(app_id)
    print("Global state:", read_global_state(algod_indexer_client ,account.address_from_private_key(temp_private_key), app_id))
    app_args = ["ITxn"]
    call_app(algod_client, payer_private_key, app_id, app_args)
    delete_app(algod_client, algod_indexer_client, app_id, payer_private_key)
    #delete_app(algod_client, algod_indexer_client, 56527153, temp_private_key)


    return 0

if __name__ == "__main__":
    main()