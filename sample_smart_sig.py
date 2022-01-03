#sample_smart_sig.py
from algosdk import future
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
import base64
import time
from utils.tealhelpher import *

"""Basic Donation Escrow"""
def donation_escrow(benefactor):
    Fee = Int(1000)

    #Only the benefactor account can withdraw from this escrow
    program = And(
        Txn.type_enum() == TxnType.Payment,
        Txn.fee() <= Fee,
        Txn.receiver() == Addr(benefactor),
        Global.group_size() == Int(1),
        Txn.rekey_to() == Global.zero_address()
    )
    # Mode.Signature specifies that this is a smart signature
    return compileTeal(program, Mode.Signature, version=5)

test_benefactor = "37UGYG6N2W4WO3GWASOLY4AFVYJTT5MQYPYEJHNQ5H2FZYW5ORIQAS6I2M"
print( donation_escrow(test_benefactor))

def payment_transaction(creator_mnemonic, amt, rcv, algod_client : algod.AlgodClient)->dict:
    params = algod_client.suggested_params()
    add = mnemonic.to_public_key(creator_mnemonic)
    key = mnemonic.to_private_key(creator_mnemonic)
    unsigned_txn = transaction.PaymentTxn(add, params, rcv, amt)
    signed = unsigned_txn.sign(key)
    txid = algod_client.send_transaction(signed)
    pmtx = wait_for_confirmation(algod_client, txid , 5)
    return pmtx

def lsig_payment_txn(escrowProg, escrow_address, amt, rcv, algod_client : algod.AlgodClient):
    params = algod_client.suggested_params()
    unsigned_txn = transaction.PaymentTxn(escrow_address, params, rcv, amt)
    encodedProg = escrowProg.encode()
    program = base64.decodebytes(encodedProg)
    lsig = transaction.LogicSig(program)
    stxn = transaction.LogicSigTransaction(unsigned_txn, lsig)
    tx_id = algod_client.send_transaction(stxn)
    pmtx = wait_for_confirmation(algod_client, tx_id, 10)
    return pmtx 

benefactor_mnemonic = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
sender_mnemonic = 'girl goddess high potato mad nominee now wise lesson ugly undo always infant ordinary snow embrace you nephew ball clinic coral brave diesel above into'

def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(default_algod_api_token(), default_algod_api_address(), headers={'User-Agent': 'py-algorand-sdk'})

    # define private keys
    receiver_public_key = mnemonic.to_public_key(benefactor_mnemonic)

    print("--------------------------------------------")
    print("Compiling Donation Smart Signature......")

    stateless_program_teal = donation_escrow(receiver_public_key)
    escrow_result, escrow_address= compile_smart_signature(algod_client, stateless_program_teal)

    print("Program:", escrow_result)
    print("hash: ", escrow_address)

    print("--------------------------------------------")
    print("Activating Donation Smart Signature......")

    # Activate escrow contract by sending 2 algo and 1000 microalgo for transaction fee from creator
    amt = 2001000
    payment_transaction(sender_mnemonic, amt, escrow_address, algod_client)

    print("--------------------------------------------")
    print("Withdraw from Donation Smart Signature......")

    # Withdraws 1 ALGO from smart signature using logic signature.
    withdrawal_amt = 2001000 - 1000
    lsig_payment_txn(escrow_result, escrow_address, withdrawal_amt, receiver_public_key, algod_client)

if __name__ == "__main__":
    main()