from SatanCommands import *
from ledger import *
from algosdk.future import transaction
from algosdk import account, mnemonic, logic
from algosdk.v2client import algod, indexer
from utils.tealhelpher import create_app, delete_app, update_app, read_global_state, get_private_key_from_mnemonic, wait_for_confirmation, call_app, delete_app
from pyteal import *

# user declared account mnemonics
creator_mnemonic = 'void hobby pyramid illness orphan arena blur service energy ranch welcome diesel behind become plastic only core audit rookie cage swap extra milk above mass'
creator_addr = 'KTNKJPJHLBTVLHMPPR5GXJ37SCMGZQ3TTFAVVGVAU6IPEQRPUJO57T736Y'

buyer_mnem = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
buyer_addr = '37UGYG6N2W4WO3GWASOLY4AFVYJTT5MQYPYEJHNQ5H2FZYW5ORIQAS6I2M'
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
    buyer_pk = get_private_key_from_mnemonic(buyer_mnem)

    print("--------------------------------------------")
    print("Calling SetData application......")
    asaId1 = 56335894
    asaId2 = 56335957
    app_id = 58075637
    #delete_app(algod_client, algod_indexer_client, app_id, creator_private_key)


    create_marker(algod_client, algod_indexer_client, asaId1, asaId2)
    get_pair_marker_id(algod_indexer_client, asaId1, asaId2)
    marker_id = get_pair_marker_id(algod_indexer_client, asaId1, asaId2)

    args = {}
    args['ASA1'] = asaId1
    args['ASA2'] = asaId2
    args['MARKER'] = marker_id
    args['PAIR'] = (1000, 1000, 1, 1)
    args['NOOP_INDEX'] = 0
    args['NOOP'] = ''
    args['TRANSACT'] = 495
    #transact_command(algod_client, algod_indexer_client, app_id, buyer_addr, args, buyer_pk)
    #opt_in_app_command(algod_client, algod_indexer_client, app_id, creator_addr, args, creator_private_key)
    #close_out_app_command(algod_client, algod_indexer_client, app_id, creator_addr, args, creator_private_key)
    opt_in_command(algod_client, algod_indexer_client, app_id, creator_addr, args, creator_private_key)
    #data_set_command(algod_client, algod_indexer_client, app_id, creator_addr, args, creator_private_key)

    delete_app_command(algod_client, algod_indexer_client, app_id, creator_addr, args, creator_private_key)

    transact_command(algod_client, algod_indexer_client, app_id, buyer_addr, args, buyer_pk)


    # read global state of application
    print("Global state:", read_global_state(algod_indexer_client, account.address_from_private_key(creator_private_key), app_id))

if __name__ == "__main__":
    main()