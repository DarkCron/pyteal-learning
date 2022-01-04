import algosdk
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from utils.tealhelpher import create_app, delete_app, update_app, read_global_state, get_private_key_from_mnemonic, intToBytes
import base64
import time


def approval_program():
   # Mode.Application specifies that this is a smart contract
   handle_creation = Seq([
       App.globalPut(Bytes("Asa1ID"), Int(0)),
       App.globalPut(Bytes("Asa2ID"), Int(0)),
       App.globalPut(Bytes("Asa1Amt"), Int(0)),
       App.globalPut(Bytes("Asa2Amt"), Int(0)),
       App.globalPut(Bytes("Asa1Prec"), Int(0)),
       App.globalPut(Bytes("Asa2Prec"), Int(0)),
       App.globalPut(Bytes("CreatorId"), Int(11)),
       App.globalPut(Bytes("EscAddr"), Txn.sender()),
       App.globalPut(Bytes("bDataSet"), Int(0)),
       Return(Int(1))
   ])

   handle_optin = Return(Int(0))
   handle_closeout = Return(Int(0))
   handle_updateapp = Return(Int(1))
   handle_deleteapp = Return(Int(0))

   scratchCount = ScratchVar(TealType.uint64)

   dataSet = Seq([
       scratchCount.store(App.globalGet(Bytes("bDataSet"))),
       App.globalPut(Bytes("EscAddr"), Txn.sender()),
       App.globalPut(Bytes("bDataSet"), scratchCount.load() + Int(1)),
       Return(Int(1))
   ])

   add = Seq([
       scratchCount.store(App.globalGet(Bytes("Count"))),
       App.globalPut(Bytes("Count"), scratchCount.load() + Int(1)),
       Return(Int(1))
   ])

   is_creator = Int(11) == App.globalGet(Bytes("CreatorId"))

   deduct = Seq([
       scratchCount.store(App.globalGet(Bytes("Count"))),
       If(scratchCount.load() > Int(0),
          App.globalPut(Bytes("Count"), scratchCount.load() - Int(1)),
          ),
       Return(Int(1))
   ])

   handle_noop = Cond(
       [And(
           Global.group_size() == Int(1),  # Make sure the transaction isn't grouped
           App.globalGet(Bytes("bDataSet")) == Int(0),
           Txn.application_args[0] == Bytes("SetData")
       ), dataSet],
       [And(
           Global.group_size() == Int(1),  # Make sure the transaction isn't grouped
           Txn.application_args[0] == Bytes("Add")
       ), add],
       [And(
           Global.group_size() == Int(1),
           Txn.application_args[0] == Bytes("Deduct")
       ), deduct],
   )

   program = Cond(
       [Txn.application_id() == Int(0), handle_creation],
       [Txn.on_completion() == OnComplete.OptIn, handle_optin],
       [Txn.on_completion() == OnComplete.CloseOut, handle_closeout],
       [Txn.on_completion() == OnComplete.UpdateApplication, Return(is_creator)],
       [Txn.on_completion() == OnComplete.DeleteApplication, Return(is_creator)],
       [Txn.on_completion() == OnComplete.NoOp, handle_noop]
   )
   return compileTeal(program, Mode.Application, version=5)


def clear_state_program():
   program = Return(Int(1))
   # Mode.Application specifies that this is a smart contract
   return compileTeal(program, Mode.Application, version=5)

# helper function to compile program source
def compile_program(client, source_code):
    compile_response = client.compile(source_code)
    return base64.b64decode(compile_response['result']), compile_response['hash']

# user declared algod connection parameters. 
# Node must have EnableDeveloperAPI set to true in its config
algod_address = 'https://node.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_token = ""

algod_indexer_address = 'https://algoindexer.testnet.algoexplorerapi.io' #"https://testnet.algoexplorerapi.io"
algod_indexer_token = ""

creator_mnemonic = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
app_id = 56481777

def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address, headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(algod_indexer_token, algod_indexer_address, headers={'User-Agent': 'py-algorand-sdk'})

    creator_private_key = get_private_key_from_mnemonic(creator_mnemonic)

    # declare application state storage (immutable)
    local_ints = 0
    local_bytes = 1
    global_ints = 9 
    global_bytes = 1
    global_schema = transaction.StateSchema(global_ints, global_bytes)
    local_schema = transaction.StateSchema(local_ints, local_bytes)

    # compile program to TEAL assembly
    with open("./approval.teal", "w") as f:
        approval_program_teal = approval_program()
        f.write(approval_program_teal)

    # compile program to TEAL assembly
    with open("./clear.teal", "w") as f:
        clear_state_program_teal = clear_state_program()
        f.write(clear_state_program_teal)

    # compile program to binary
    approval_program_compiled, addr = compile_program(algod_client, approval_program_teal)

    # compile program to binary
    clear_state_program_compiled, _ = compile_program(algod_client, clear_state_program_teal)


    print("---------Generating args-----------")

    # configure registration and voting period
    Asa1ID = 0
    Asa2ID = 0
    Asa1Prec = 0
    Asa2Prec = 0

    # create list of bytes for app args
    app_args = [
        intToBytes(Asa1ID),
        intToBytes(Asa2ID),
        intToBytes(Asa1Prec),
        intToBytes(Asa2Prec),
    ]

    print("--------------------------------------------")
    print("Updating application......")
    
    # create new application
    app_id = create_app(algod_client, algod_indexer_client, creator_private_key, approval_program_compiled, clear_state_program_compiled, global_schema, local_schema)
    #app_id = update_app(algod_client, algod_indexer_client, app_id ,creator_private_key, approval_program_compiled, clear_state_program_compiled)
    #delete_app(algod_client, algod_indexer_client, app_id, creator_private_key)

    # read global state of application
    print("Global state:", read_global_state(algod_indexer_client ,account.address_from_private_key(creator_private_key), app_id))



if __name__ == "__main__":
    main()