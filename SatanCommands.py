from algosdk import future
from utils.tealhelpher import get_address_from_app_id, intToBytes, wait_for_confirmation
from algosdk.encoding import decode_address, encode_address
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from typing import List
import base64
import time

from pyteal.ast import arg

ACT_FEE = 100000
OPT_IN_FEE = 100000
TX_FEE = 1000

NOOP_INDICES = {'SetData':5, 'ITxn':0, 'OptIn':0, 'Transact':0}

def tx_transfer_asset(client : algod.AlgodClient, sender_addr, receiver_addr, args : dict):
    params = client.suggested_params()
    txn = transaction.AssetTransferTxn(sender_addr, params, receiver_addr, args['PAIR'][0], args['ASA1'])
    return txn

def tx_transact_asset(client : algod.AlgodClient, sender_addr, receiver_addr, args : dict):
    params = client.suggested_params()
    txn = transaction.AssetTransferTxn(sender_addr, params, receiver_addr, args['TRANSACT'], args['ASA2'])
    return txn

def tx_transfer_algo(client : algod.AlgodClient, sender_addr, receiver_addr, args : dict):
    params = client.suggested_params()
    txn = transaction.PaymentTxn(sender_addr, params, receiver_addr, args['PAIR'][0])
    return txn

def tx_transact_algo(client : algod.AlgodClient, sender_addr, receiver_addr, args : dict):
    params = client.suggested_params()
    txn = transaction.PaymentTxn(sender_addr, params, receiver_addr, args['TRANSACT'])
    return txn

def tx_fee_payment(client : algod.AlgodClient, sender_addr, receiver_addr, fee_amt : int):
    params = client.suggested_params()
    txn = transaction.PaymentTxn(sender_addr, params, receiver_addr, fee_amt)
    return txn

def tx_application_call(client : algod.AlgodClient, sender_addr,app_id : int, args : dict):
    params = client.suggested_params()
    app_args = [
        intToBytes(args['PAIR'][0]),
        intToBytes(args['PAIR'][1]),
        intToBytes(args['PAIR'][2]),
        intToBytes(args['PAIR'][3]),
        args['NOOP']
    ]
    txn = transaction.ApplicationNoOpTxn(sender_addr, params, app_id, app_args, foreign_assets=[args['ASA1'], args['ASA2'],args['MARKER']])
    return txn

def fee_amt_for_send_data(args : dict):
    cost = TX_FEE + ACT_FEE
    if args['ASA1'] != 1:
        cost += OPT_IN_FEE
    if args['ASA2'] != 1:
        cost += OPT_IN_FEE
        cost += TX_FEE
    return cost

def send_command(client : algod.AlgodClient,txs, sender_pk):
    gid = transaction.calculate_group_id(txs)
    for tx in txs:
        tx.group = gid
    
    stxns = []
    for tx in txs:
        stxns.append(tx.sign(sender_pk))

    tx_id = client.send_transactions(stxns)

    # wait for confirmation
    wait_for_confirmation(client, tx_id, 5) 
    return

def opt_in_command(client : algod.AlgodClient, indexer : indexer.IndexerClient, app_id, sender_addr, args : dict, sender_pk):
    receiver_addr = get_address_from_app_id(app_id)
    args['NOOP'] = 'OptIn'
    args['NOOP_INDEX'] = NOOP_INDICES[args['NOOP']]
    txs = []

    txs.append(tx_fee_payment(client, sender_addr, receiver_addr, fee_amt_for_send_data(args)))
    txs.append(tx_application_call(client, sender_addr,app_id, args))

    send_command(client, txs, sender_pk)
    return

def data_set_command(client : algod.AlgodClient, indexer : indexer.IndexerClient, app_id, sender_addr, args : dict, sender_pk):
    receiver_addr = get_address_from_app_id(app_id)
    args['NOOP'] = 'SetData'
    args['NOOP_INDEX'] = NOOP_INDICES[args['NOOP']]
    txs = []

    if args['ASA1'] != 1:
        txs.append(tx_transfer_asset(client, sender_addr, receiver_addr, args))
    elif args['ASA1'] == 1:
        txs.append(tx_transfer_algo(client, sender_addr, receiver_addr, args))
    else:
        raise Exception() 
    txs.append(tx_application_call(client, sender_addr,app_id, args))

    send_command(client, txs, sender_pk)
    return

def transact_command(client : algod.AlgodClient, indexer : indexer.IndexerClient, app_id, sender_addr, args : dict, sender_pk):
    receiver_addr = get_address_from_app_id(app_id)
    args['NOOP'] = 'Transact'
    args['NOOP_INDEX'] = NOOP_INDICES[args['NOOP']]
    txs = []

    if args['ASA2'] != 1:
        txs.append(tx_transact_asset(client, sender_addr, receiver_addr, args))
    elif args['ASA2'] == 1:
        txs.append(tx_transact_algo(client, sender_addr, receiver_addr, args))
    else:
        raise Exception() 

    txs.append(tx_fee_payment(client, sender_addr,receiver_addr, TX_FEE))
    txs.append(tx_application_call(client, sender_addr,app_id, args))

    send_command(client, txs, sender_pk)
    return

def delete_app_command(client : algod.AlgodClient, indexer : indexer.IndexerClient, app_id, sender_addr, receiver_addr, args : dict, sender_pk):
    args['NOOP'] = 'ITxn'
    args['NOOP_INDEX'] = NOOP_INDICES[args['NOOP']]
    txs = []
    txs.append(tx_fee_payment(client, sender_addr, receiver_addr, TX_FEE * 3))
    txs.append(tx_application_call(client, sender_addr,app_id, args))

    send_command(client, txs, sender_pk)
    return