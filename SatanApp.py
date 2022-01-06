import algosdk
from pyteal import *
from algosdk.encoding import decode_address, encode_address
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from pyteal.ast.itxn import InnerTxnActionExpr
from utils.tealhelpher import create_app, delete_app, update_app, read_global_state, get_private_key_from_mnemonic, intToBytes
import base64
import time
import random
import hashlib

def Satansbank(creator_addr : str):
    """Only allow receiver to withdraw funds from this contract account.

    Args:
        creator_addr (str): Base 32 Algorand address of the receiver.
    """
    is_payment = Txn.type_enum() == TxnType.Payment
    is_single_tx = Global.group_size() == Int(1)
    is_correct_receiver = Txn.receiver() == Addr(creator_addr)
    no_close_out_addr = Txn.close_remainder_to() == Global.zero_address()
    no_rekey_addr = Txn.rekey_to() == Global.zero_address()
    acceptable_fee = Txn.fee() <= Int(1000)

    return And(
        is_payment,
        is_single_tx,
        is_correct_receiver,
        no_close_out_addr,
        no_rekey_addr,
        acceptable_fee,
    )

def approval_program():
    # Mode.Application specifies that this is a smart contract
    handle_creation = Seq([
        Assert(Txn.application_args.length() == Int(5)),
        App.globalPut(Bytes("Asa1ID"), Btoi(Txn.application_args[0])),
        App.globalPut(Bytes("Asa2ID"), Btoi(Txn.application_args[1])),
        App.globalPut(Bytes("Asa1Amt"), Int(0)),
        App.globalPut(Bytes("Asa2Amt"), Int(0)),
        App.globalPut(Bytes("Asa1Prec"), Btoi(Txn.application_args[2])),
        App.globalPut(Bytes("Asa2Prec"), Btoi(Txn.application_args[3])),
        App.globalPut(Bytes("CreatorId"), Int(11)),
        App.globalPut(Bytes("Closer"), (Txn.application_args[4])),
        App.globalPut(Bytes("bDataSet"), Int(0)),
        App.globalPut(Bytes("Key"), Int(random.randrange(pow(2,31)))),
        Return(Int(1))
    ])

    handle_optin = Return(Int(0))
    handle_closeout = Return(Int(0))
    handle_updateapp = Return(Int(1))
    handle_deleteapp = Return(Int(0))

    scratchCount = ScratchVar(TealType.uint64)
    scratchBytesCount = ScratchVar(TealType.bytes)

    dataSet = Seq([
        scratchCount.store(App.globalGet(Bytes("bDataSet"))),
        App.globalPut(Bytes("Closer"), Txn.sender()),
        App.globalPut(Bytes("bDataSet"), scratchCount.load() + Int(1)),
        Return(Int(1))
    ])

    add = Seq([
        scratchCount.store(App.globalGet(Bytes("Count"))),
        App.globalPut(Bytes("Count"), scratchCount.load() + Int(1)),
        Return(Int(1))
    ])

    is_creator = Seq([
        If(Txn.sender() == App.globalGet(Bytes("Closer")), Return(Int(1))),
        Return(Int(0))
    ])
    #is_creator = Bytes('base64',encode_address(base64.b64decode(Txn.sender()))) == App.globalGet(Bytes("Closer"))

    deduct = Seq([
        scratchCount.store(App.globalGet(Bytes("Count"))),
        If(scratchCount.load() > Int(0),
            App.globalPut(Bytes("Count"), scratchCount.load() - Int(1)),
            ),
        Return(Int(1))
    ])

    itxn = Seq([
        #Clear assets
            # InnerTxnBuilder().Begin(), 
            # InnerTxnBuilder().SetFields(
            #     {
            #         TxnField.type_enum: TxnType.AssetTransfer,
            #         TxnField.asset_sender: Global.current_application_address(),
            #         TxnField.asset_receiver: App.globalGet(Bytes("Closer")),
            #         TxnField.asset_close_to : App.globalGet(Bytes("Closer")),
            #         }),
            # InnerTxnBuilder().Submit(), 
            InnerTxnBuilder().Begin(), 
            InnerTxnBuilder().SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(Bytes("Closer")),
                    TxnField.close_remainder_to :  App.globalGet(Bytes("Closer")),
                    TxnField.asset_close_to : App.globalGet(Bytes("Closer")),
                    }),
            InnerTxnBuilder().Submit(), 
            Approve()
        ])

    optin = Seq([
            InnerTxnBuilder().Begin(), 
            InnerTxnBuilder().SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    #TxnField.asset_sender: Global.current_application_address(),
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.xfer_asset :  App.globalGet(Bytes("Asa1ID")),
                    TxnField.asset_amount :  Int(0),
                    }),
            InnerTxnBuilder().Submit(), 
            Approve()
        ])

    handle_noop = Cond(
        [And(
            Global.group_size() == Int(1),  # Make sure the transaction isn't grouped
            Txn.application_args[0] == Bytes("OptIn")
        ), optin],
        [And(
            Global.group_size() == Int(1),  # Make sure the transaction isn't grouped
            Txn.application_args[0] == Bytes("ITxn")
        ), itxn],
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

creator_mnemonic = 'soup kind never flavor anger horse family asthma hollow best purity slight lift inmate later left smoke stamp basic syrup relief pencil point abstract fiscal'
app_id = 56510473

def min_cost_for_app() -> int:
    global_schema, local_schema = app_schemas()
    return 100000*(2) + (25000+35000)*global_schema.num_uints + (25000+25000)*global_schema.num_byte_slices*10

def app_schemas():
    # declare application state storage (immutable)
    local_ints = 0
    local_bytes = 2
    global_ints = 10 
    global_bytes = 4
    global_schema = transaction.StateSchema(global_ints, global_bytes)
    local_schema = transaction.StateSchema(local_ints, local_bytes)

    return global_schema, local_schema

def app_ready_to_go(algod : algod.AlgodClient, indexer : indexer.IndexerClient, creator_pk :str, source_addr : bytes):
    """A complete and ready to go compilation of the Satan app

    Args:
        algod (algod.AlgodClient): [description]
        indexer (indexer.IndexerClient): [description]
        creator_pk ([type]): [description]
        source_addr ([type]): Address of the instantiator, this is not the the creator of the app. Instantiator is the person with intent of use.

    Returns:
        [int]: id of the created app
    """
    global_schema, local_schema = app_schemas()

    # compile program to TEAL assembly
    with open("./approval.teal", "w") as f:
        approval_program_teal = approval_program()
        f.write(approval_program_teal)

    # compile program to TEAL assembly
    with open("./clear.teal", "w") as f:
        clear_state_program_teal = clear_state_program()
        f.write(clear_state_program_teal)
    
    # compile program to binary
    approval_program_compiled, _ = compile_program(algod, approval_program_teal)

    # compile program to binary
    clear_state_program_compiled, _ = compile_program(algod, clear_state_program_teal)

    print("---------Generating args-----------")
    # configure registration and voting period
    Asa1ID = 56335894
    Asa2ID = 56335957

    d1 = indexer.asset_info(Asa1ID)
    d2 = indexer.asset_info(Asa2ID)
    asaId1Decimals = d1['asset']['params']['decimals']
    asaId2Decimals = d2['asset']['params']['decimals']

    Asa1Prec = asaId1Decimals
    Asa2Prec = asaId2Decimals

    # create list of bytes for app args
    app_args = [
        intToBytes(Asa1ID),
        intToBytes(Asa2ID),
        intToBytes(Asa1Prec),
        intToBytes(Asa2Prec),
        source_addr
    ]


    return create_app(algod, indexer, creator_pk, approval_program_compiled, clear_state_program_compiled, global_schema, local_schema, app_args)

def main() :
    # initialize an algodClient
    algod_client = algod.AlgodClient(algod_token, algod_address, headers={'User-Agent': 'py-algorand-sdk'})
    algod_indexer_client = indexer.IndexerClient(algod_indexer_token, algod_indexer_address, headers={'User-Agent': 'py-algorand-sdk'})

    creator_private_key = get_private_key_from_mnemonic(creator_mnemonic)

    global_schema, local_schema = app_schemas()

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
    print("program address: ", addr)
    
    # compile program to binary
    clear_state_program_compiled, _ = compile_program(algod_client, clear_state_program_teal)


    print("---------Generating args-----------")


    # configure registration and voting period
    Asa1ID = 56335894
    Asa2ID = 56335957

    d1 = algod_indexer_client.asset_info(Asa1ID)
    d2 = algod_indexer_client.asset_info(Asa2ID)
    asaId1Decimals = d1['asset']['params']['decimals']
    asaId2Decimals = d2['asset']['params']['decimals']

    Asa1Prec = asaId1Decimals
    Asa2Prec = asaId2Decimals

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
    #app_id = create_app(algod_client, algod_indexer_client, creator_private_key, approval_program_compiled, clear_state_program_compiled, global_schema, local_schema)
    #app_id = update_app(algod_client, algod_indexer_client, app_id ,creator_private_key, approval_program_compiled, clear_state_program_compiled)
    delete_app(algod_client, algod_indexer_client, app_id, creator_private_key)

    # read global state of application
    print("Global state:", read_global_state(algod_indexer_client ,account.address_from_private_key(creator_private_key), app_id))



if __name__ == "__main__":
    main()