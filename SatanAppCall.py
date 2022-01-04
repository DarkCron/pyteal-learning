import base64
import samplecontract

from algosdk.future import transaction
from algosdk import account, mnemonic, logic
from algosdk.v2client import algod, indexer
from utils.tealhelpher import create_app, update_app, read_global_state, get_private_key_from_mnemonic, wait_for_confirmation, call_app
from pyteal import *
import SatanApp

# user declared account mnemonics
creator_mnemonic = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'

# user declared algod connection parameters. 
# Node must have EnableDeveloperAPI set to true in its config
algod_address = 'https://node.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_token = ""

algod_indexer_address = 'https://algoindexer.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_indexer_token = ""

def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address, headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(algod_indexer_token, algod_indexer_address, headers={'User-Agent': 'py-algorand-sdk'})

    # define private keys
    creator_private_key = get_private_key_from_mnemonic(creator_mnemonic)

    print("--------------------------------------------")
    print("Calling Counter application......")
    app_args = ["SetData"]
    #call_app(algod_client, creator_private_key, SatanApp.app_id, app_args)

    # read global state of application
    print("Global state:", read_global_state(algod_indexer_client, account.address_from_private_key(creator_private_key), SatanApp.app_id))

if __name__ == "__main__":
    main()