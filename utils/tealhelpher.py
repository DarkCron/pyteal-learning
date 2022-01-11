from ledger import *
from algosdk import future
from algosdk.encoding import decode_address, encode_address, checksum
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from typing import List
import algosdk
import base64
import time

from pyteal.ast import addr

ACT_FEE = 100000
OPT_IN_FEE = 100000
TX_FEE = 1000

def tx_fee_payment(client : algod.AlgodClient, sender_addr, receiver_addr, fee_amt : int):
    params = client.suggested_params()
    txn = transaction.PaymentTxn(sender_addr, params, receiver_addr, fee_amt)
    return txn

def fee_amt_for_send_data(args : dict):
    cost = TX_FEE + ACT_FEE
    if args['ASA1'] != 1:
        cost += OPT_IN_FEE
    if args['ASA2'] != 1:
        cost += OPT_IN_FEE
        cost += TX_FEE
    return cost

def get_address_from_app_id(app_id):
    return algosdk.encoding.encode_address(checksum(b'appID'+(app_id).to_bytes(8, 'big')))

def generate_algorand_keypair():
    private_key, address = account.generate_account()
    print("My address: {}".format(address))
    print("My passphrase: {}".format(mnemonic.from_private_key(private_key)))
    return private_key, address

def fee_payment_provider(client : algod.AlgodClient, indexer : indexer.IndexerClient, amt : int, payer_key, receiver, allowFirstTxs : bool = False):
    isFirstTx = False

    try:
        indexer.account_info(receiver)
    except Exception:
        isFirstTx = True
        if not allowFirstTxs:
            raise Exception('First tx not allowed here')
        else:
            amt += 100000 #min amount to create account

    # declare sender
    sender = account.address_from_private_key(payer_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.PaymentTxn(sender, params, receiver, amt)

    # sign transaction
    signed_txn = txn.sign(payer_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(0.1)

    print("Payment confirmed!")
    return

def make_sure_act_has_min_cost_plus(indexer : indexer.IndexerClient, amt : int, receiver, amt_for_tx_fees : int):
    info = indexer.account_info(receiver)
    act_amt = info['account']['amount']
    return amt + amt_for_tx_fees - act_amt + 4000

# convert 64 bit integer i to byte string
def intToBytes(i):
    return i.to_bytes(8, "big")

def default_algod_api_address():
    return 'https://node.testnet.algoexplorerapi.io'

def default_algod_api_token():
    return ''

def default_indexer_api_address():
    return 'https://algoindexer.testnet.algoexplorerapi.io'

def default_indexer_api_token():
    return ''

# helper function to compile program source
def compile_smart_signature(client : algod.AlgodClient, source_code):
    compile_response = client.compile(source_code)
    return compile_response['result'], compile_response['hash']


# helper function to compile program source
def compile_program(client : algod.AlgodClient, source_code):
    compile_response = client.compile(source_code)
    return base64.b64decode(compile_response['result'])

# helper function that converts a mnemonic passphrase into a private signing key
def get_private_key_from_mnemonic(mn) :
    private_key = mnemonic.to_private_key(mn)
    return private_key


# helper function that waits for a given txid to be confirmed by the network
def wait_for_confirmation(client: algod.AlgodClient, transaction_id, timeout):
    """
    Wait until the transaction is confirmed or rejected, or until 'timeout'
    number of rounds have passed.
    Args:
        transaction_id (str): the transaction to wait for
        timeout (int): maximum number of rounds to wait    
    Returns:
        dict: pending transaction information, or throws an error if the transaction
            is not confirmed or rejected in the next timeout rounds
    """
    start_round = client.status()["last-round"] + 1
    current_round = start_round

    while current_round < start_round + timeout:
        try:
            pending_txn = client.pending_transaction_info(transaction_id)
        except Exception:
            return 
        if pending_txn.get("confirmed-round", 0) > 0:
            return pending_txn
        elif pending_txn["pool-error"]:  
            raise Exception(
                'pool error: {}'.format(pending_txn["pool-error"]))
        client.status_after_block(current_round)                   
        current_round += 1
    raise Exception(
        'pending tx not found in timeout rounds, timeout value = : {}'.format(timeout))

# helper function that formats global state for printing
def format_state(state):
    formatted = {}
    for item in state:
        key = item['key']
        value = item['value']
        formatted_key = base64.b64decode(key).decode('utf-8')
        if value['type'] == 1:
            # byte string
            if formatted_key == 'voted':
                formatted_value = base64.b64decode(value['bytes']).decode('utf-8')
            elif formatted_key == 'EscAddr':
                formatted_value = value['bytes']
                #formatted_value = base64.b64decode(value['bytes']).decode('utf-8')
                #formatted_value = encode_address(base64.b64decode(value['bytes']))
            else:
                formatted_value = value['bytes']
            formatted[formatted_key] = formatted_value
        else:
            # integer
            formatted[formatted_key] = value['uint']
    return formatted

# helper function to read app global state
def read_global_state(client :indexer.IndexerClient, addr, app_id):
    results = client.account_info(addr)
    apps_created = results['account']['created-apps']
    for app in apps_created:
        if app['id'] == app_id:
            return format_state(app['params']['global-state'])
    return {}

# call application
def call_app(client :algod.AlgodClient, private_key, index, app_args) : 
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationNoOpTxn(sender, params, index, app_args, foreign_assets=[56335894, 56335957])

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    print("Application called")

# create new application
def create_app(client : algod.AlgodClient, indexer: indexer.IndexerClient, private_key, approval_program, clear_program, global_schema, local_schema, app_args = [], args : dict = {}):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real
    on_complete = transaction.OnComplete.OptInOC.real

    # get node suggested parameters
    params = client.suggested_params()
    
    # create unsigned transaction
    txn = transaction.ApplicationCreateTxn(sender, params, on_complete, \
                                            approval_program, clear_program, \
                                            global_schema, local_schema, app_args, foreign_assets=[args['ASA1'], args['ASA2'], args['MARKER']])

    tx_marker_xfer = tx_send_marker_asset_with_clawback(client, indexer, get_pair_marker_id(client, args['ASA1'], args['ASA2']), sender, MARKER_PK())
    tx_fee = tx_fee_payment(client, sender, MARKER_ADDR, TX_FEE)

    txs = [txn, tx_marker_xfer, tx_fee]

    gid = transaction.calculate_group_id(txs)
    for tx in txs:
        tx.group = gid
    
    stxns = [txs[0].sign(private_key), txs[1].sign(MARKER_PK()), txs[2].sign(private_key)]

    tx_id = client.send_transactions(stxns)

    # wait for confirmation
    wait_for_confirmation(client, tx_id, 5) 

    # # sign transaction
    # signed_txn = txn.sign(private_key)
    # tx_id = signed_txn.transaction.get_txid()
    
    # # send transaction
    # client.send_transactions([signed_txn])

    # # await confirmation
    # wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(0.1)

    app_id = transaction_response['transaction']['created-application-index']
    print("Created new app-id:", app_id)

    return app_id

# update application
def update_app(client : algod.AlgodClient, indexer : indexer.IndexerClient, appid, private_key, approval_program, clear_program):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationUpdateTxn(sender, params, appid, approval_program, clear_program)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(1)

    print("updated app-id:", appid)

    return appid

# delete application
def close_out_app(client : algod.AlgodClient, indexer : indexer.IndexerClient, appid, private_key):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.AssetCloseOutTxn(sender, params, appid, 0)
    
    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(1)

    print("deleted app-id:", appid)

    return appid

# delete application
def close_app(client : algod.AlgodClient, indexer : indexer.IndexerClient, appid, private_key):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationDeleteTxn(sender, params, appid)
    
    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(1)

    print("closed out app-id:", appid)

    return appid

# delete application
def delete_app(client : algod.AlgodClient, indexer : indexer.IndexerClient, appid, private_key):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationDeleteTxn(sender, params, appid, foreign_assets=[56335894, 56335957])
    
    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            transaction_response = indexer.transaction(tx_id)
            break
        except Exception:
            pass
        finally:
            time.sleep(1)

    print("deleted app-id:", appid)

    return appid

def has_asa_amt(indexer : indexer.IndexerClient, asset_id : int, amt : int, sender_addr : str) -> bool:

    a = indexer.account_info(sender_addr)
    asas = a['account']['assets']
    for asa in asas:
        if asa['asset-id'] == asset_id:
            if asa['amount'] >= amt:
                return True
    
    return False

def fee_payment_provider_tx(client : algod.AlgodClient, indexer : indexer.IndexerClient, amt : int, asset_id : int, payer_key, receiver, allowFirstTxs : bool = True):    
    if asset_id != 0:
        b = has_asa_amt(indexer, asset_id, amt, account.address_from_private_key(payer_key))
        if not b:
            raise Exception("You don't own enough of asa ", asset_id, " to make tx ", account.address_from_private_key(payer_key))

    isFirstTx = False
    algoTxn = None
    asaOptInTxn = None
    txns = []

    # declare sender
    sender = account.address_from_private_key(payer_key)
    # get node suggested parameters
    params = client.suggested_params()
    if asset_id == 0 : #Algorand or not
        # create unsigned transaction
        txn = transaction.PaymentTxn(sender, params, receiver, amt)
        txns.append(txn)
    else: #ASA
        txn = transaction.AssetTransferTxn(sender, params, receiver, amt, asset_id)
        txns.append(txn)

    if asset_id != 0:
        b = has_asa_amt(indexer, asset_id, 0, receiver)
        if not b:
            txn = transaction.AssetOptInTxn(sender, params, asset_id)
            txns.insert(0,txn)

    try:
        indexer.account_info(receiver)
    except Exception:
        isFirstTx = True
        if not allowFirstTxs:
            raise Exception('First tx not allowed here')
        else:
            algoTxn = transaction.PaymentTxn(sender, params, receiver, 100000)
            txns.append(algoTxn)

    return txns

# call application
def call_app_tx(client :algod.AlgodClient, private_key, index, app_args) -> Txn: 
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationNoOpTxn(sender, params, index, app_args)
    return txn

def create_payment_noop_group(client : algod.AlgodClient, indexer : indexer.IndexerClient, amt : int, asset_id : int, payer_pk , receiver_addr : str, app_args):
    txns = fee_payment_provider_tx(client, indexer, amt, asset_id, payer_pk, receiver_addr)
    txns.append(call_app_tx(client, payer_pk, app_args))

    gid = transaction.calculate_group_id(txns)
    for tx in txns:
        tx.group = gid
    
    stxns = []
    for tx in txns:
        stxns.append(tx.sign(payer_pk))

    tx_id = client.send_transactions(stxns)

    # wait for confirmation
    wait_for_confirmation(client, tx_id, 5) 

    return []

def send_marker_asset_with_clawback(client : algod.AlgodClient, indexer : indexer.IndexerClient, asset_id, receiver, clawback_pk):
    params = client.suggested_params()
    
    txn = transaction.AssetTransferTxn(account.address_from_private_key(clawback_pk), params, receiver, 1, asset_id, revocation_target=account.address_from_private_key(clawback_pk))
    stxn = txn.sign(clawback_pk)
    tx_id = client.send_transaction(stxn)
    # wait for confirmation
    wait_for_confirmation(client, tx_id, 5) 

    return

def tx_send_marker_asset_with_clawback(client : algod.AlgodClient, indexer : indexer.IndexerClient, asset_id, receiver, clawback_pk):
    params = client.suggested_params()
    
    txn = transaction.AssetTransferTxn(account.address_from_private_key(clawback_pk), params, receiver, 1, asset_id, revocation_target=account.address_from_private_key(clawback_pk))
    return txn

def tx_retrieve_marker_asset_with_clawback(client : algod.AlgodClient, indexer : indexer.IndexerClient, asset_id, take_asset_from_addr, clawback_pk):
    params = client.suggested_params()
    
    txn = transaction.AssetTransferTxn(account.address_from_private_key(clawback_pk), params, account.address_from_private_key(clawback_pk), 1, asset_id, revocation_target=take_asset_from_addr)
    return txn