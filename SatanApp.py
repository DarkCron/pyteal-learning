import algosdk
from pyteal import *
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
import base64
import time


def approval_program():
   # Mode.Application specifies that this is a smart contract
   handle_creation = Seq([
       Assert(Txn.application_args.length() == Int(7)),
       App.globalPut(Bytes("Asa1ID"), Int(0)),
       App.globalPut(Bytes("Asa2ID"), Int(0)),
       App.globalPut(Bytes("Asa1Amt"), Int(0)),
       App.globalPut(Bytes("Asa2Amt"), Int(0)),
       App.globalPut(Bytes("Asa1Prec"), Int(0)),
       App.globalPut(Bytes("Asa2Prec"), Int(0)),
       App.globalPut(Bytes("CreatorId"), Txn.sender()),
       App.globalPut(Bytes("EscAddr"), Int(0)),
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
       App.globalPut(Bytes("bDataSet"), scratchCount.load() + Int(1)),
       Return(Int(1))
   ])

   add = Seq([
       scratchCount.store(App.globalGet(Bytes("Count"))),
       App.globalPut(Bytes("Count"), scratchCount.load() + Int(1)),
       Return(Int(1))
   ])

   is_creator = Txn.sender() == App.globalGet(Bytes("CreatorId"))

   deduct = Seq([
       scratchCount.store(App.globalGet(Bytes("Count"))),
       If(scratchCount.load() > Int(0),
          App.globalPut(Bytes("Count"), scratchCount.load() - Int(1)),
          ),
       Return(Int(1))
   ])

   handle_noop = Cond(
       [And(
            App.globalGet(Bytes("bDataSet")) == Int(0),  # Make sure the transaction isn't grouped
           Txn.application_args[0] == Bytes("DataSet")
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
       [Txn.on_completion() == OnComplete.UpdateApplication, is_creator],
       [Txn.on_completion() == OnComplete.DeleteApplication, is_creator],
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


def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address, headers={'User-Agent': 'py-algorand-sdk'})

    # declare application state storage (immutable)
    local_ints = 0
    local_bytes = 0
    global_ints = 9 
    global_bytes = 0
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



if __name__ == "__main__":
    main()