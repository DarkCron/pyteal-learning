import base64
import samplecontract

from algosdk.future import transaction
from algosdk import account, mnemonic, logic
from algosdk.v2client import algod
from pyteal import *


# user declared account mnemonics
creator_mnemonic = "soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal"
# user declared algod connection parameters. 
# Node must have EnableDeveloperAPI set to true in its config
algod_address = 'https://node.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_token = ""

algod_indexer_address = 'https://algoindexer.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_indexer_token = ""

app_id = 56268871

# call application
def call_app(client, private_key, index, app_args) : 
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = transaction.ApplicationNoOpTxn(sender, params, index, app_args)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    samplecontract.wait_for_confirmation(client, tx_id, 5)

    print("Application called")

def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address, headers={'User-Agent': 'py-algorand-sdk'})
    # define private keys
    creator_private_key = samplecontract.get_private_key_from_mnemonic(creator_mnemonic)

    print("--------------------------------------------")
    print("Calling Counter application......")
    app_args = ["Add"]
    call_app(algod_client, creator_private_key, app_id, app_args)

    # read global state of application
    print("Global state:", samplecontract.read_global_state(account.address_from_private_key(creator_private_key), app_id))

if __name__ == "__main__":
    main()