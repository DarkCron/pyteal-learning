import algosdk
from pyteal import *
from algosdk.encoding import decode_address, encode_address
from algosdk import account, mnemonic
from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from pyteal.ast.itxn import InnerTxnActionExpr
from utils.tealhelpher import create_app, delete_app, update_app, read_global_state, get_private_key_from_mnemonic, intToBytes, OPT_IN_FEE, TX_FEE, ACT_FEE
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

def approval_program(asa1Id : int, asa2Id : int ):
    asa1Id = Int(asa1Id)
    asa2Id = Int(asa2Id)

    VERSION = Int(1)

    @Subroutine(TealType.uint64)
    def sub_has_correct_assets():
        return And(
            (Btoi(Txn.application_args[0]) == Txn.assets[0]),
            (Btoi(Txn.application_args[1]) == Txn.assets[1]),
            (Btoi(Txn.application_args[3]) == Txn.assets[2])
        )
    
    @Subroutine(TealType.uint64)
    def sub_has_correct_assets_for_i(i : Int):
        return And(
            Or(App.globalGet(Bytes("Asa1ID")) == Int(1),App.globalGet(Bytes("Asa1ID")) == Gtxn[i].assets[0]),
            Or(App.globalGet(Bytes("Asa2ID")) == Int(1),App.globalGet(Bytes("Asa2ID")) == Gtxn[i].assets[1]),
            (App.globalGet(Bytes("MarkerId")) == Gtxn[i].assets[2])
        )

    asa1Opt = AssetHolding.balance(Txn.sender(), asa1Id)
    asa2Opt = AssetHolding.balance(Txn.sender(), asa2Id)

    tx_act_fee = Int(ACT_FEE)
    tx_min_fee = Int(TX_FEE)
    tx_min_fee_opt = Int(OPT_IN_FEE)

    marker_clawback = AssetParam.clawback(Txn.assets[2])
    scratchCount = ScratchVar(TealType.uint64)

    @Subroutine(TealType.none)
    def sub_assert_gtxn_safe(i : Int):
        """Check Gtxn[0] through Gtxn[i] if they're safe

        Args:
            i (Int): [description]

        Returns:
            [type]: [description]
        """
        scratchCount.store(Int(0)),
        While(scratchCount.load() <= i).Do(
            Seq(
                [
                    Assert(
                        And(
                            Gtxn[scratchCount.load()].close_remainder_to() == Global.zero_address(),
                            Gtxn[scratchCount.load()].asset_close_to() == Global.zero_address(),
                            Gtxn[scratchCount.load()].rekey_to() == Global.zero_address(),
                            Gtxn[scratchCount.load()].fee() <= tx_min_fee
                        )
                    ),
                    scratchCount.store(scratchCount.load() + Int(1))
                ]
            )
        )
        return Assert(Int(1) == Int(1))
    
    @Subroutine(TealType.none)
    def sub_opt_in(id):
        return Seq([
            InnerTxnBuilder().Begin(), 
            InnerTxnBuilder().SetFields(
                {   
                    #Keep Sender empty for OptIn
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.xfer_asset :  id,
                    TxnField.asset_amount :  Int(0),
                    TxnField.fee : tx_min_fee
                    }),
            InnerTxnBuilder().Submit(),
        ])

    @Subroutine(TealType.none)
    def sub_complete_opt_in():
        return Seq([
            sub_assert_gtxn_safe(Int(1)),
            Seq([
                Assert(sub_has_correct_assets_for_i(Int(1))),
                Assert(And(
                    Global.group_size() == Int(2),
                    Gtxn[0].type_enum() == TxnType.Payment,                             #Provide Algo for tx fees
                    Gtxn[1].type_enum() == TxnType.ApplicationCall,                     #
                    Gtxn[0].receiver() == Global.current_application_address(),         #Make sure the algo receiver is this
                    Gtxn[0].sender() == Gtxn[1].sender(),
                    Gtxn[1].sender() == App.globalGet(Bytes("Creator")),
                )),
                If(And(App.globalGet(Bytes("Asa1ID")) != Int(1),App.globalGet(Bytes("Asa2ID")) != Int(1)),
                    Assert(Gtxn[0].amount() == tx_act_fee + (tx_min_fee + tx_min_fee_opt) * Int(2)),
                    Assert(Gtxn[0].amount() == tx_act_fee + (tx_min_fee + tx_min_fee_opt))
                )
            ]),
            If(App.globalGet(Bytes("Asa1ID")) != Int(1), 
                sub_opt_in(App.globalGet(Bytes("Asa1ID")))
            ),
            If(App.globalGet(Bytes("Asa2ID")) != Int(1),
                sub_opt_in(App.globalGet(Bytes("Asa2ID")))
            )
        ])

    handle_creation = Seq([
        sub_assert_gtxn_safe(Int(2)),
        marker_clawback,
        Assert(
            And(
                marker_clawback.hasValue(),
                Global.group_size() == Int(3),
                #Gtxn[0].type_enum() == TxnType.ApplicationCall,     #Should be this create call, mustn't be check
                Gtxn[1].type_enum() == TxnType.AssetTransfer,
                Gtxn[1].xfer_asset() == Btoi(Txn.application_args[3]),
                Gtxn[1].asset_receiver() ==  Txn.application_args[2],
                Gtxn[2].type_enum() == TxnType.Payment,
                Gtxn[2].sender() == Txn.application_args[2],
                Gtxn[2].receiver() == marker_clawback.value(),
                Gtxn[2].amount() == tx_min_fee
        )),
        Assert(Txn.application_args.length() == Int(4)),
        Assert(sub_has_correct_assets()),
        asa1Opt,
        asa2Opt,
        Assert(And(asa1Opt.hasValue(), asa2Opt.hasValue())),
        App.globalPut(Bytes("Asa1ID"), Btoi(Txn.application_args[0])),
        App.globalPut(Bytes("Asa2ID"), Btoi(Txn.application_args[1])),
        App.globalPut(Bytes("Asa1Amt"), Int(0)),
        App.globalPut(Bytes("Asa2Amt"), Int(0)),
        App.globalPut(Bytes("Asa1Div"), Int(0)),
        App.globalPut(Bytes("Asa2Div"), Int(0)),
        App.globalPut(Bytes("Creator"), Txn.application_args[2]),
        App.globalPut(Bytes("bDataSet"), Int(0)),
        App.globalPut(Bytes("MarkerId"), Btoi(Txn.application_args[3])),
        App.globalPut(Bytes("Version"), VERSION),
        Return(Int(1))
    ])

    handle_optin = Seq([
        Assert(Txn.sender() ==  App.globalGet(Bytes("Creator"))),
        Return(Int(1))
    ])

    @Subroutine(TealType.uint64)
    def and_assets_ok(i): 
        return And(
            Gtxn[i].assets[0] == App.globalGet(Bytes("Asa1ID")),
            Gtxn[i].assets[1] == App.globalGet(Bytes("Asa2ID")),
            Gtxn[i].assets[2] == App.globalGet(Bytes("MarkerId")),
        )

    dataSet = Seq([
        sub_assert_gtxn_safe(Int(1)),
        If(And(App.globalGet(Bytes("Asa1ID")) != Int(1)), 
            #THEN BRANCH -> IF ASSET 1 AND ASSET 2 =/= ALGO
            Seq([
                Assert(sub_has_correct_assets_for_i(Int(0))),
                Assert(And(
                    Global.group_size() == Int(2),
                    Gtxn[1].type_enum() == TxnType.AssetTransfer,                       #Provide Asset 1 for contract
                    Gtxn[0].type_enum() == TxnType.ApplicationCall,                     #
                    Gtxn[1].asset_receiver() == Global.current_application_address(),   #Make sure the asset 1 receiver is this
                    Gtxn[0].assets[0] == Gtxn[1].xfer_asset(),                          #Make sure asset 1 is being supplied
                    Gtxn[1].asset_amount() > Int(0),
                    Gtxn[1].sender() == Gtxn[0].sender(),
                    Gtxn[0].sender() == App.globalGet(Bytes("Creator")),
                    #Make sure initial provision matches amount transferred
                    Gtxn[1].asset_amount()  == Btoi(Gtxn[0].application_args[0])
                )),
            ]),
            #ELSE BRANCH -> IF ASSET 1 OR ASSET 2 == ALGO
            #ASA1 IS ALGO
            Seq([
                Assert(sub_has_correct_assets_for_i(Int(0))),
                Assert(And(
                    Global.group_size() == Int(2),
                    Gtxn[1].type_enum() == TxnType.Payment,                             #Provide Asset 1 for contract
                    Gtxn[0].type_enum() == TxnType.ApplicationCall,                     #
                    Gtxn[1].receiver() == Global.current_application_address(),         #Make sure the asset 1 receiver is this
                    App.globalGet(Bytes("Asa1ID")) == Int(1),                               #In this special case ALGO == ID 1
                    Gtxn[1].amount() > Int(0),
                    Gtxn[1].sender() == Gtxn[0].sender(),
                    Gtxn[0].sender() == App.globalGet(Bytes("Creator")),
                    #Make sure initial provision matches amount transferred
                    Gtxn[1].amount()  == Btoi(Gtxn[0].application_args[0])
                )),
            ])
        ),
        #math check common props for both asset and transfer payment
        Assert(And(
            Gtxn[0].application_args.length() == Int(5), #args[0] = amount 1, args[1] = amount 2, args[2] = div 1, args[3] = div 2 , args[4] = NooP Call
            Btoi(Gtxn[0].application_args[0]) > Int(0),
            Btoi(Gtxn[0].application_args[1]) > Int(0),
            Btoi(Gtxn[0].application_args[2]) > Int(0),
            Btoi(Gtxn[0].application_args[3]) > Int(0),
            Btoi(Gtxn[0].application_args[0]) % Btoi(Gtxn[0].application_args[2]) == Int(0),
            Btoi(Gtxn[0].application_args[1]) % (Btoi(Gtxn[0].application_args[0]) / Btoi(Gtxn[0].application_args[2])) == Int(0),
            Btoi(Gtxn[0].application_args[1]) % (Btoi(Gtxn[0].application_args[3])) == Int(0),
            (Btoi(Gtxn[0].application_args[0]) * Btoi(Gtxn[0].application_args[3]) / Btoi(Gtxn[0].application_args[2])) == Btoi(Gtxn[0].application_args[1]),
        )),
        App.globalPut(Bytes("Asa1Amt"), Btoi(Gtxn[0].application_args[0])),
        App.globalPut(Bytes("Asa2Amt"), Btoi(Gtxn[0].application_args[1])),
        App.globalPut(Bytes("Asa1Div"), Btoi(Gtxn[0].application_args[2])),
        App.globalPut(Bytes("Asa2Div"), Btoi(Gtxn[0].application_args[3])),
        App.globalPut(Bytes("bDataSet"), Int(1)),
        sub_opt_in(App.globalGet(Bytes("Asa1ID"))),
        sub_opt_in(App.globalGet(Bytes("Asa2ID"))),
        Return(Int(1))
    ])

    transact = Seq([
        # scratchCount.store(App.globalGet(Bytes("bDataSet"))),
        # sub_assert_gtxn_safe(Int(0)), #Sell pair trade
        # sub_assert_gtxn_safe(Int(1)), #Tx fee payment
        sub_assert_gtxn_safe(Int(2)), #This application call
        If(And(Gtxn[0].type_enum() == TxnType.AssetTransfer, App.globalGet(Bytes("Asa2ID")) != Int(1)), 
            #THEN BRANCH -> IF ASSET 2 =/= ALGO
            Seq([
                Assert(sub_has_correct_assets_for_i(Int(2))),
                scratchCount.store(Gtxn[0].asset_amount()),
                Assert(And(
                    Global.group_size() == Int(3),
                    Gtxn[0].type_enum() == TxnType.AssetTransfer,                       #Provide Asset 2 for trade
                    Gtxn[1].type_enum() == TxnType.Payment,                             #Provide Algo for tx fees
                    Gtxn[2].type_enum() == TxnType.ApplicationCall,                     #
                    Gtxn[0].asset_receiver() == Global.current_application_address(),   #Make sure the asset 2 receiver is this
                    Gtxn[1].receiver() == Global.current_application_address(),         #Make sure the algo receiver is this
                    and_assets_ok(Int(2)) == Int(1),
                    Gtxn[2].assets[1] == Gtxn[0].xfer_asset(),                          #Make sure asset 2 is being supplied
                    Gtxn[0].asset_amount() > Int(0),
                    App.globalGet(Bytes("Asa2Amt")) >= Btoi(Gtxn[2].application_args[0]),
                    scratchCount.load() % App.globalGet(Bytes("Asa2Div")) == Int(0),
                    Gtxn[1].amount() == tx_min_fee,
                    Gtxn[0].sender() == Gtxn[1].sender(),
                    Gtxn[1].sender() == Gtxn[2].sender(),
                    Gtxn[2].sender() == Gtxn[0].sender(),
                )),
            ]),
            #ELSE BRANCH -> IF ASSET 2 == ALGO
            Seq([
                Assert(sub_has_correct_assets_for_i(Int(2))),
                scratchCount.store(Gtxn[0].amount()),
                Assert(And(
                    Global.group_size() == Int(3),
                    Gtxn[0].type_enum() == TxnType.Payment,                             #Provide Asset 1 for contract (Algo)
                    Gtxn[1].type_enum() == TxnType.Payment,                             #Provide Algo for tx fees
                    Gtxn[2].type_enum() == TxnType.ApplicationCall,                     #
                    Gtxn[0].receiver() == Global.current_application_address(),         #Make sure the asset 1 receiver is this
                    Gtxn[1].receiver() == Global.current_application_address(),         #Make sure the algo receiver is this
                    and_assets_ok(Int(2)) == Int(1),                                           #Make sure asset 2 is being supplied
                    App.globalGet(Bytes("Asa2ID")) == Int(1),                               #In this special case ALGO == ID 1
                    Gtxn[0].amount() > Int(0),
                    App.globalGet(Bytes("Asa2Amt")) >= Btoi(Gtxn[2].application_args[0]),
                    scratchCount.load() % App.globalGet(Bytes("Asa2Div")) == Int(0),
                    Gtxn[1].amount() == tx_min_fee,
                    Gtxn[0].sender() == Gtxn[1].sender(),
                    Gtxn[1].sender() == Gtxn[2].sender(),
                    Gtxn[2].sender() == Gtxn[0].sender(),
                ))
            ])   
        ),
        #math check common props for both asset and transfer payment
        Assert(Gtxn[2].application_args.length() == Int(5)),
        App.globalPut(Bytes("Asa1Amt"), App.globalGet(Bytes("Asa1Amt")) - ((App.globalGet(Bytes("Asa2Div")) / scratchCount.load()) * App.globalGet(Bytes("Asa1Div")))),
        App.globalPut(Bytes("Asa2Amt"), App.globalGet(Bytes("Asa1Amt")) - ((App.globalGet(Bytes("Asa2Div")) / scratchCount.load()) * App.globalGet(Bytes("Asa2Div")))),
        If(And(Gtxn[0].type_enum() == TxnType.AssetTransfer, App.globalGet(Bytes("Asa2ID")) != Int(1)),
            #THEN BRANCH -> IF ASSET 2 =/= ALGO
            Seq(
                InnerTxnBuilder().Begin(), 
                InnerTxnBuilder().SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset :  App.globalGet(Bytes("Asa1ID")),
                        TxnField.asset_receiver: Gtxn[0].sender(),
                        TxnField.asset_amount : (scratchCount.load() / App.globalGet(Bytes("Asa2Div"))) * App.globalGet(Bytes("Asa1Div")),
                        TxnField.fee : tx_min_fee,
                    }),
                InnerTxnBuilder().Submit()
            ),
            #THEN BRANCH -> IF ASSET 2 == ALGO
            Seq(
                InnerTxnBuilder().Begin(), 
                InnerTxnBuilder().SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.receiver: Gtxn[0].sender(),
                        TxnField.amount : (scratchCount.load() / App.globalGet(Bytes("Asa2Div"))) * App.globalGet(Bytes("Asa1Div")),
                        TxnField.fee : tx_min_fee,
                    }),
                InnerTxnBuilder().Submit())
            ),
        Return(Int(1))
    ])

    is_creator = Seq([
        If(Txn.sender() == App.globalGet(Bytes("Creator")), Return(Int(1))),
        Return(Int(0))
    ])

    itxn = Seq([
            sub_assert_gtxn_safe(Int(3)),
            marker_clawback,
            Assert(Txn.sender() == App.globalGet(Bytes("Creator"))),
            Assert(And(
                    marker_clawback.hasValue(),
                    Global.group_size() == Int(4),
                    Gtxn[3].type_enum() == TxnType.ApplicationCall,     #Clean up call (this)
                    Gtxn[3].sender() == App.globalGet(Bytes("Creator")),
                    Gtxn[0].type_enum() == TxnType.Payment,             #Tx fees payment
                    Gtxn[1].type_enum() == TxnType.Payment,             #Tx fees payment to clawback
                    Gtxn[2].type_enum() == TxnType.AssetTransfer,       #Clawback action of Marker asset
                    Gtxn[0].sender() == Gtxn[1].sender(),
                    Gtxn[0].receiver() == Global.current_application_address(),
                    Gtxn[0].amount() == (tx_min_fee) * Int(3),           #max 2 asset close-outs + algo close-out
                    Gtxn[1].receiver() == marker_clawback.value(),
                    Gtxn[1].sender() == App.globalGet(Bytes("Creator")),
                    Gtxn[1].amount() == tx_min_fee,
                    Gtxn[2].xfer_asset() == App.globalGet(Bytes("MarkerId")),
                    Gtxn[2].asset_sender() == App.globalGet(Bytes("Creator")),
                    Gtxn[2].asset_receiver() == marker_clawback.value(),
                    Gtxn[2].asset_amount() == Int(1)
                    )),
            #Clear assets
            If(App.globalGet(Bytes("Asa1ID")) != Int(1),
                Seq([
                    InnerTxnBuilder().Begin(), 
                    InnerTxnBuilder().SetFields(
                        {
                            TxnField.type_enum: TxnType.AssetTransfer,
                            TxnField.xfer_asset :  App.globalGet(Bytes("Asa1ID")),
                            TxnField.asset_receiver: App.globalGet(Bytes("Creator")),
                            TxnField.asset_close_to : App.globalGet(Bytes("Creator")),
                            TxnField.fee : tx_min_fee,
                        }),
                    InnerTxnBuilder().Submit(),
                ])
            ),
            If(App.globalGet(Bytes("Asa2ID")) != Int(1),
                Seq([
                    InnerTxnBuilder().Begin(), 
                    InnerTxnBuilder().SetFields(
                        {
                            TxnField.type_enum: TxnType.AssetTransfer,
                            TxnField.xfer_asset :  App.globalGet(Bytes("Asa2ID")),
                            TxnField.asset_receiver: App.globalGet(Bytes("Creator")),
                            TxnField.asset_close_to : App.globalGet(Bytes("Creator")),
                            TxnField.fee : tx_min_fee,
                        }),
                    InnerTxnBuilder().Submit(),
                ])
            ), 
            InnerTxnBuilder().Begin(),
            InnerTxnBuilder().SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(Bytes("Creator")),
                    TxnField.close_remainder_to :  App.globalGet(Bytes("Creator")),
                    TxnField.fee : tx_min_fee,
                }),
            InnerTxnBuilder().Submit(), 
            Return(Int(1))
        ])

    optin = Seq(
        [
            sub_complete_opt_in(),
            Return(Int(1))
        ]
    )

    handle_noop = Cond(
        [And(
            Txn.application_args[4] == Bytes("OptIn")
        ), optin],
        [And(
            Txn.application_args[4] == Bytes("Transact")
        ), transact],
        [And(
            App.globalGet(Bytes("bDataSet")) == Int(0),
            Txn.application_args.length() == Int(5),
            Txn.application_args[4] == Bytes("SetData")
        ), dataSet]
    )



    program = Cond(
        [Txn.application_id() == Int(0), handle_creation],
        [Txn.on_completion() == OnComplete.OptIn, handle_optin],
        [Txn.on_completion() == OnComplete.CloseOut, is_creator],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Int(0))],
        [Txn.on_completion() == OnComplete.DeleteApplication, itxn],
        #[Txn.on_completion() == OnComplete.DeleteApplication, Return(Int(1))],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop]
    )
    return compileTeal(program, Mode.Application, version=5)

def b64len(b64str):
    """
    Calculate the length in bytes of a base64 string.
    This function could decode the base64 string to a binary blob and count its
    number of bytes with len(). But, that's inefficient and requires more
    memory that really needed.
    Base64 encodes three bytes to four characters. Sometimes, padding is added
    in the form of one or two '=' characters.
    So, the following formula allows to know the number of bytes of a base64
    string without decoding it::
        (3 * (length_in_chars / 4)) - (number_of_padding_chars)
    :param str b64str: A base64 encoded string.
    :return: Length, in bytes, of the binary blob encoded in base64.
    :rtype: int
    """
    return (3 * (len(b64str) / 4)) - b64str[-2:].count('=')

def clear_state_program():
    program = Return(Int(1))
    # Mode.Application specifies that this is a smart contract
    return compileTeal(program, Mode.Application, version=5)

# helper function to compile program source
def compile_program(client, source_code):
    compile_response = client.compile(source_code)
    len = b64len(compile_response['result'])
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
    return 100000 + (25000+3500)*global_schema.num_uints + (25000+25000)*global_schema.num_byte_slices

def app_schemas():
    # declare application state storage (immutable)
    local_ints = 0
    local_bytes = 0
    global_ints = 9 
    global_bytes = 1
    global_schema = transaction.StateSchema(global_ints, global_bytes)
    local_schema = transaction.StateSchema(local_ints, local_bytes)

    return global_schema, local_schema

def app_ready_to_go(algod : algod.AlgodClient, indexer : indexer.IndexerClient, creator_pk :str, source_addr : bytes, args : dict):
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

    Asa1ID = args['ASA1']
    Asa2ID = args['ASA2']

    # compile program to TEAL assembly
    with open("./approval.teal", "w") as f:
        approval_program_teal = approval_program(Asa2ID, Asa2ID)
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

    # create list of bytes for app args
    app_args = [
        intToBytes(Asa1ID),
        intToBytes(Asa2ID),
        source_addr,
        intToBytes(args['MARKER'])
    ]


    return create_app(algod, indexer, creator_pk, approval_program_compiled, clear_state_program_compiled, global_schema, local_schema, app_args, args)