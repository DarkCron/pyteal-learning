MARKER_MNEM = 'claim sustain health test dice margin duck broccoli boy list tiger harvest hurt plate federal stage opera turtle drill vocal defense middle spend abandon claim'
MARKER_ADDR = 'VAFYQMEBVPSOG2RVGAF36BKTLYNC2O263IMYU2PY7HFQSSKHATAB5LEKWE'

from algosdk.future import transaction
from algosdk.v2client import algod, indexer
from algosdk.encoding import checksum
from algosdk import account, mnemonic
import pyteal
import time
import base64

MARKER_DICT = {}

# helper function that converts a mnemonic passphrase into a private signing key
def get_private_key_from_mnemonic(mn) :
    private_key = mnemonic.to_private_key(mn)
    return private_key

def MARKER_PK():
    return mnemonic.to_private_key(MARKER_MNEM)

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

def pair_marker_metadata_hash(asaId1 : int, asaId2) -> str:
    hash = (checksum(b'asa1'+(asaId1).to_bytes(8, 'big')+b'asa2'+(asaId2).to_bytes(8, 'big')))
    return base64.b64encode(hash).decode('utf-8')

def get_pair_marker_id(indexer: indexer.IndexerClient, asaId1 : int, asaId2 : int) -> int:
    """returns the pair marker id, -1 if not found.
    Do note, that order of asa IDs is important.

    Args:
        indexer (indexer.IndexerClient): v2 indexer
        asaId1 (int): asa 1 index
        asaId2 (int): asa 2 index

    Returns:
        int: returns the pair marker id, -1 if not found
    """
    if (asaId1, asaId2) in MARKER_DICT:
        return MARKER_DICT[(asaId1, asaId2)]

    MARKER_ACT_INFO = indexer.account_info(MARKER_ADDR)
    hash_to_find_marker = pair_marker_metadata_hash(asaId1, asaId2)

    if 'assets' in MARKER_ACT_INFO['account']:
        for asset in MARKER_ACT_INFO['account']['assets']:
            id = asset['asset-id']
            asset_info = indexer.asset_info(id)
            if asset_info['asset']['params']['metadata-hash'] == hash_to_find_marker:
                MARKER_DICT[(asaId1, asaId2)] = id
                return id
    
    return -1

def unfreeze(client : algod.AlgodClient, indexer: indexer.IndexerClient, asaId : int, recipient_addr : str):

    params = client.suggested_params()

    txn = transaction.AssetFreezeTxn(
        sender=MARKER_ADDR,
        sp=params,
        index=asaId, 
        new_freeze_state=False,
        target=recipient_addr)
    
    # sign by the current manager - Account 2
    stxn = txn.sign(get_private_key_from_mnemonic(MARKER_MNEM))
    txid = client.send_transaction(stxn)

    # Wait for the transaction to be confirmed
    wait_for_confirmation(client, txid,5)
    return

def freeze(client : algod.AlgodClient, indexer: indexer.IndexerClient, asaId : int, recipient_addr : str):
    params = client.suggested_params()

    txn = transaction.AssetFreezeTxn(
        sender=MARKER_ADDR,
        sp=params,
        index=asaId, 
        new_freeze_state=True,
        target=recipient_addr)
    
    # sign by the current manager - Account 2
    stxn = txn.sign(get_private_key_from_mnemonic(MARKER_MNEM))
    txid = client.send_transaction(stxn)
    
    # Wait for the transaction to be confirmed
    wait_for_confirmation(client, txid,5)
    return

def create_marker(client : algod.AlgodClient, indexer: indexer.IndexerClient, asaId1 : int, asaId2 : int):
    if (asaId1, asaId2) in MARKER_DICT:
        return
    
    MARKER_ACT_INFO = indexer.account_info(MARKER_ADDR)
    found_marker_asa = False
    hash_to_find_marker = (checksum(b'asa1'+(asaId1).to_bytes(8, 'big')+b'asa2'+(asaId2).to_bytes(8, 'big')))

    if 'assets' in MARKER_ACT_INFO['account']:
        for asset in MARKER_ACT_INFO['account']['assets']:
            id = asset['asset-id']
            asset_info = indexer.asset_info(id)
            if asset_info['asset']['params']['metadata-hash'] == base64.b64encode(hash_to_find_marker).decode('utf-8'):
                found_marker_asa = True
                MARKER_DICT[(asaId1, asaId2)] = id
                break

    if found_marker_asa:
        return
    
    params = client.suggested_params()

    assetInfo1 = indexer.asset_info(asaId1)
    assetInfo2 = indexer.asset_info(asaId2)

    asaStr1 = str(assetInfo1['asset']['index'])
    asaStr2 = str(assetInfo2['asset']['index'])
    if len(asaStr1) > 10:
        asaStr1 = asaStr1[0:10]
    if len(asaStr2) > 10:
        asaStr2 = asaStr2[0:10]

    marker_name = 'MARKER_'+asaStr1+'_'+asaStr2

    txn = transaction.AssetConfigTxn(
        sender=MARKER_ADDR,
        sp=params,
        total=1000000000,
        default_frozen=False,
        asset_name=marker_name,
        manager=MARKER_ADDR,
        reserve=MARKER_ADDR,
        freeze=MARKER_ADDR,
        clawback=MARKER_ADDR,
        metadata_hash=hash_to_find_marker,
        decimals=0)
    
    stxn = txn.sign(get_private_key_from_mnemonic(MARKER_MNEM))
    txid = client.send_transaction(stxn)
    wait_for_confirmation(client,txid, 5)

    #!!!!!!!! Must be gotten from indexer 
    # display results
    while(True):
        try:
            ptx = indexer.transaction(txid)
            print(ptx['transaction']["asset-index"])
            break
        except Exception:
            pass
        finally:
            time.sleep(0.1)



    return