from algosdk import future
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
import base64
import time

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


# create new application
def create_app(client : algod.AlgodClient, indexer: indexer.IndexerClient, private_key, approval_program, clear_program, global_schema, local_schema):
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


# create new application
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

    app_id = transaction_response['transaction']['created-application-index']
    print("Created new app-id:", app_id)

    return app_id