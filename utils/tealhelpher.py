from algosdk import future
from algosdk.encoding import decode_address, encode_address
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
import base64
import time

from pyteal.ast import addr

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
    return amt + amt_for_tx_fees - act_amt

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
    txn = transaction.ApplicationNoOpTxn(sender, params, index, app_args)

    # sign transaction
    signed_txn = txn.sign(private_key)
    t = Txn.sender()
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id, 5)

    print("Application called")

# create new application
def create_app(client : algod.AlgodClient, indexer: indexer.IndexerClient, private_key, approval_program, clear_program, global_schema, local_schema, app_args = []):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationCreateTxn(sender, params, on_complete, \
                                            approval_program, clear_program, \
                                            global_schema, local_schema, app_args)
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
            time.sleep(0.1)

    app_id = transaction_response['transaction']['created-application-index']
    print("Created new app-id:", app_id)

    return app_id

# create new application
def create_app_grouped(client : algod.AlgodClient, indexer: indexer.IndexerClient, private_key, approval_program, clear_program, global_schema, local_schema):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = transaction.OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationCreateTxn(sender, params, on_complete, \
                                            approval_program, clear_program, \
                                            global_schema, local_schema)

    ########### CALL APP PAIRED? #################
    # create unsigned transaction
    txn2 = transaction.ApplicationNoOpTxn(sender, params, _, [])
    # get group id and assign it to transactions
    gid = transaction.calculate_group_id([txn, txn2])


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
def delete_app(client : algod.AlgodClient, indexer : indexer.IndexerClient, appid, private_key):
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

    print("deleted app-id:", appid)

    return appid