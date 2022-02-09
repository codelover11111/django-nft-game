
import datetime
import json
import traceback

from django.utils import timezone
from django.utils.timezone import make_aware
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError

from json.decoder import JSONDecodeError
from requests.exceptions import ConnectionError, ConnectTimeout

from .exceptions import CoolDownError
from .models import TokenInfo, Transaction
from time import time

from os import getenv as env
from sys import stderr

from .process import api_post

ENJIN_APP_ID=int(env('ENJIN_APP_ID'))
ENJIN_SERVER_URL=env('ENJIN_SERVER_URL')
ENJIN_SERVER_URL_KEY=env('ENJIN_SERVER_URL_KEY')
ENJIN_SECRET=env('ENJIN_SECRET')


## globals
owner_info = None
cooldown_start = None
cooldown_seconds = 5

token_dev=""
token_user=""
token_delta=datetime.timedelta(hours=24)
token_time=datetime.datetime.now() + token_delta


def set_headers():
  if token_dev:
    return {
      'X-App-Id': str(ENJIN_APP_ID),
      'Authorization': f'Bearer {token_dev}'
    }

  return {}

def do_query(q, params={}, try_renew=True):
  global cooldown_start
  global cooldown_seconds

  if cooldown_start and time()-cooldown_start < cooldown_seconds:
    raise CoolDownError('Too many requests. Please try again in a moment')

  if cooldown_start and time()-cooldown_start >= cooldown_seconds:
    cooldown_start = None

  if try_renew:
    if not renewSecret():
      raise TransportQueryError(str({ 'message': 'Failed to renew the session' }))

  with open("Enjin.log", 'a') as errfile:
    print(datetime.datetime.now(), "[QUERY LOG] performing query", file=errfile)

    _transport = RequestsHTTPTransport(
      url=ENJIN_SERVER_URL,
      use_json=True,
      headers=set_headers()
    )

    client = Client(transport=_transport)
    query = gql(q)

    try:
      return client.execute(query, variable_values=params)
    except ConnectionError as e:
      print(datetime.datetime.now(), "[QUERY ERROR] connection", type(e), e, file=errfile)
      traceback.print_exc(file=errfile)
      raise e
    except JSONDecodeError as e:
      print(datetime.datetime.now(), "[QUERY ERROR] json", type(e), e, file=errfile)
      traceback.print_exc(file=errfile)
      raise e
    except TransportQueryError as e:
      error = eval(str(e))
      print(datetime.datetime.now(), "[QUERY ERROR] transport error", type(e), e, file=errfile)
      traceback.print_exc(file=errfile)
      if error['code'] == 429:
        if not cooldown_start:
          cooldown_start = time()

        raise CoolDownError('Too many requests. Please try again in a moment')
      else:
        raise e
    except Exception as e:
      print(datetime.datetime.now(), "[QUERY ERROR]", type(e), e, file=errfile)
      traceback.print_exc(file=errfile)
      raise e


## authenticate app
def authapp(app_id, secret):
  query="""
  query Auth($id: Int!, $secret: String!) {
    app: AuthApp(id: $id, secret: $secret) {
      accessToken
      expiresIn
    }
  }"""

  global token_dev

  params={ 'id': app_id, 'secret': secret }
  return do_query(query, params, bool(token_dev))


def renewSecret():
  #print("[DEBUG] renewing secret", file=stderr)
  ## renew enjin application secret
  global token_time
  global token_dev

  #print("[DEBUGGING TOKEN TIME]", token_time, file=stderr)

  if not token_dev or token_time <= datetime.datetime.now():
    with open("Enjin.log", 'a') as errfile:
      print(datetime.datetime.now(), "[SESSION NOTICE] acquiring new token", file=errfile)

      try:
        token_dev = ""
        app = authapp(ENJIN_APP_ID, ENJIN_SECRET).get('app', {})
        print(datetime.datetime.now(), "[TOKEN SUCCESS]", "token acquired", file=errfile)
      except TransportQueryError as e:
        print(datetime.datetime.now(), "[TOKEN ERROR transport]", e, file=errfile)
        traceback.print_exc(file=errfile)
        return False
      except Exception as e:
        print(datetime.datetime.now(), "[TOKEN ERROR exception]", type(e), e, file=errfile)
        traceback.print_exc(file=errfile)
        return False
      else:
        #print(r_json["access_token"], file=errfile)
        token_dev = app.get("accessToken", '')
        token_time = datetime.datetime.now() + datetime.timedelta(seconds=app.get('expiresIn', 0))

  # return true by default
  return True


### - - - - - - - - - -
## top level functions
### - - - - - - - - - -

## CURRENT token exchange version
# params:
#   player: PlayerBase obj
#   tx_obj: Transaction obj
def exchange_for_tokens(tx):
  tx_obj = Transaction.objects.get(pk=tx)
  player = get_player_info(tx_obj.player)

  ## check player data
  if not player.identity_id:
    raise TransportQueryError(str({ 'message': 'Unidentified user' } ))

  if not player.wallet:
    raise TransportQueryError(str( { 'message': 'User does not have a linked wallet' } ))

  try:
    result = mint_tokens(tx_obj).get('req')
  except TransportQueryError as e:
    error = eval(str(e))
    if error.get('code') in [422, 90001]:
      tx_obj.status = 'FAILED'
      tx_obj.save()
    else:
      tx_obj.dirty = True
    raise e

  except CoolDownError as e:
    raise e

  except (ConnectTimeout, ConnectionError, Exception) as e:
    tx_obj.status = 'UNDER_REVISION'
    tx_obj.dirty = True
    tx_obj.save()
    raise e

  try:
    tx_obj.app_transaction_id = result.get('id', tx_obj.app_transaction_id)
    tx_obj.eth_transaction_id = result.get('transactionId', tx_obj.eth_transaction_id)
    tx_obj.status = result.get('state', tx_obj.status)
    tx_obj.save()
  except Exception as e:
    raise e
  else:
    return tx_obj



## - - - - - - - - - - - - - - - -
#  miscellaneous (base) functions
## - - - - - - - - - - - - - - - -
def check_available_stock(token_id):
  #print("[ENJIN] checking available stock", file=stderr)
  query = """
  query CheckOwnerStock($id: String!) {
    app: EnjinApp {
      owner {
        identities {
          wallet { ethAddress }
          tokens(id: $id) { id, balance, index, nonFungible }
        }
      }
    }
  }"""
  result = do_query(query, { 'id': str(token_id) })
  data = {}

  owner = result['app']['owner'].get('identities',[])[0]

  if owner['tokens']:
    token = owner['tokens'][0]

    data['id'] = token['id']
    data['balance'] = int(token['balance'])
    data['index'] = token['index']
    data['nft?'] = int(token['nonFungible'])

  return data


def check_available_to_mint(token_id):
  #print("[ENJIN] checking minting availability", file=stderr)
  query = """
  query AvailableToMint($id: String!) {
    token: EnjinToken(id: $id) {
      id
      availableToMint
      nonFungible
    }
  }"""

  result = do_query(query, { 'id': str(token_id) })
  data = {}

  if result.get('token'):
    token = result['token']

    data['id'] = token['id']
    data['available'] = token['availableToMint']
    data['nft?'] = token['nonFungible']

  return data



## send from one player to the other
def transfer_from_player_to_player(amount, token_id, sender, receiver):
  pass


## send from the app owner to a player
def transfer_token_from_reserve(amount, token_id, is_nft, receiver_address):
  #print("[ENJIN] transfering from reserve", file=stderr)
  owner = get_owner_info()

  if not amount:
    raise Exception("amount cannot be Zero (0)")

  if not owner.get('wallet'):
    raise TransportQueryError(str({ 'message': 'Owner does not have a linked wallet', 'code': 90001 }))

  if is_nft:
    return send_nft(amount, token_id, owner['identity_id'], receiver_address)
  else:
    return send_ft(amount, token_id, owner['identity_id'], receiver_address)


def make_TransferInput(assets, receiver_id):
  ti = []
  for asset in assets:
    entry = {}

    entry['to_id'] = receiver_id
    entry['token_id'] = asset.get('id')
    entry['value'] = asset.get('amount')

    if asset.get('index'):
      entry['token_index'] = asset.get('index')

    ti.append(entry)

  return ti


## send tokens to broker and viceversa
def reserve_assets(sender_id, tokens):
  broker = get_owner_info()

  if not broker.get("wallet"):
    raise TransportQueryError(str({ "message": "Broker doesn't have a wallet", "code": 90001 }))

  transfer_inputs = make_TransferInput(tokens, broker["identity_id"])

  query = """mutation SendAssetsToBroker($id: Int, $ti: [TransferInput]) {
    CreateEnjinRequest(
      identityId: $id
      type: ADVANCED_SEND
      advanced_send_token_data: {
        transfers: $ti
      }
    ) {
      id
      state
      transactionId
      value
      updatedAt
      createdAt
    }
  }"""

  result = do_query(query, params={ "id": sender_id, "ti": transfer_inputs })

  return result.get("CreateEnjinRequest")


## toksen transference
def send_ft(amount, token_id, sender_id, receiver_address):
  #print("[ENJIN] sending FT", file=stderr)
  query = """
  mutation sendFTfromReserve($token_id: String!, $receiver_address: String!, $amount: String, $identity_id: Int!) {
    req: CreateEnjinRequest(
      identityId: $identity_id
      type: ADVANCED_SEND
      advanced_send_token_data: {
        transfers: [{
          to: $receiver_address
          token_id: $token_id
          value: $amount
        }]
      }
    ) { id, encodedData, transactionId, state }
  }"""
  
  params = {
    'identity_id': sender_id,
    'token_id': token_id,
    'receiver_address': receiver_address,
    'amount': amount,
  }
  
  return do_query(query, params)


def send_nft(amount, token_id, token_index, sender_id, receiver_address):
  #print("[ENJIN] sending NFT", file=stderr)
  query = """
  mutation sendFTfromReserve($token_id: String!, $token_index: String!, $receiver_address: String!, $identity_id: Int!, $amount: String) {
    req: CreateEnjinRequest(
      identityId: $identity_id
      type: ADVANCED_SEND
      advanced_send_token_data: {
        transfers: [{
          to: $receiver_address
          token_id: $token_id
          token_index: $token_index
          value: $amount
        }]
      }
    ) { id, encodedData, transactionId, state }
  }"""

  params = {
    'identity_id': sender_id,
    'token_id': token_id,
    'receiver_address': receiver_address,
    'token_index': token_index,
    'amount': amount,
  }
  
  return do_query(query, params)


def send_multiple(sender_id, receiver_address, **tokens):
  pass



## mint tokens
def mint_tokens(tx_obj):
  #print("[ENJIN] minting tokens", file=stderr)
  owner = get_owner_info()

  if not owner.get('wallet'):
    # TODO: move error codes to CONSTANTS
    raise TransportQueryError(str({ 'message': 'Owner does not have a linked wallet', 'code': 90001 }))

  if tx_obj.nft:
    return mint_nft(tx_obj)
  else:
    return mint_ft(tx_obj)


## mint and send
def mint_ft(tx_obj, dummy=False):
  #print("[ENJIN] minting FT", file=stderr)
  query = """
  mutation MintFungibleItems($identityId: Int!, $tokenId: String!, $wallets: [String], $values: [Int], $is_dummy: Boolean) {
    req: CreateEnjinRequest(
      dummy: $is_dummy,
      identityId: $identityId,
      type: MINT,
      mint_token_data: {
        token_id: $tokenId,
        recipient_address_array: $wallets,
        value_array: $values
      }
    ) { id, encodedData, transactionId, state }
  }"""
  owner = get_owner_info()

  params = {
    'identityId': int(owner['identity_id']),
    'tokenId': str(tx_obj.token_id),
    'wallets': [tx_obj.player.wallet],
    'values': [int(tx_obj.q_tokens)],
    'is_dummy': dummy,
  }

  tx_obj.transaction_time = timezone.now()
  tx_obj.save()
  result = do_query(query, params)
  return result


def mint_nft(tx_obj, dummy=False):
  #print("[ENJIN] minting NFT", file=stderr)
  query = """
  mutation MintNonFungibleItems($identityId: Int!, $tokenId: String!, $wallets: [String], $is_dummy: Boolean) {
    req: CreateEnjinRequest(
      dummy: $is_dummy,
      identityId: $identityId,
      type: MINT,
      mint_token_data: {
        token_id: $tokenId,
        token_index: "",
        recipient_address_array: $wallets
      }
    ) { id, encodedData, transactionId, state }
  }"""
  owner = get_owner_info()

  #print("[LA CONCHA DE TU MADRE ALL BOYS]", receiver_address, amount, [receiver_address]*int(amount), file=stderr)
  params = {
    'identityId': int(owner['identity_id']),
    'tokenId': tx_obj.token_id,
    'wallets': [tx_obj.player.wallet]*int(tx_obj.q_tokens),
    'is_dummy': dummy,
  }

  tx_obj.transaction_time = timezone.now()
  tx_obj.save()
  result = do_query(query, params)
  return result


## status checks
# transaction
def check_transactions_status(transaction_ids=[]):
  #print("[ENJIN] checking transaction", file=stderr)

  if not transaction_ids:
    return []

  subquery_template = """
  _%d: EnjinTransactions(id: %d) {
    id
    state
  }"""

  queries = "\n".join([subquery_template % (_,_) for _ in transaction_ids])
  query = "query GetTransactionsData { %s }" % (queries)
  result = do_query(query)

  transactions = []
  for _ in result.values():
    transactions.extend(_)

  return transactions


## NON-ENJIN function
def get_player_enj_info(player):
  """
  obtain enjin information from the player
  :param player: PlayerBase
  :return: dict
  """
  try:
    data = { 'user': player.nick_name }
    print(data)
    response = api_post('enj/info/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return { 'status': 0, 'error': 'Connection failed while trying to communicate with the main service', 'source': 'function' }
  except Exception as e:
    print("EXCEPTION IN API",type(e), file=stderr)
    return { 'status': 0, 'error': str(e), 'source': 'function' }


# player information
def get_player_info(player, force_update=False):
  """
  updates player information from enjin
  returns the user model with updated info if necessary
  """
  enj_data = get_player_enj_info(player)
  if enj_data.get('status'):
    data = enj_data.get('data', {})
    player.identity_id = data.get('enj_id', player.identity_id)
    player.wallet = data.get('enj_eth', player.wallet)
    player.id = data.get('id', player.id)
    player.save(update_fields=['identity_id', 'wallet', 'id'])

  return player
  # query = """
  # query CheckPlayer($name: String!) {
  #   users: EnjinUsers(name: $name) {
  #     id
  #     identities {
  #       id
  #       appId
  #       wallet {
  #         ethAddress
  #       }
  #     }
  #   }
  # }"""
  # result = do_query(query, { 'name': player.nick_name })
  #
  # try:
  #   the_user = None
  #   the_identity = None
  #
  #   for user in result.get('users', []):
  #     for identity in user.get('identities', []):
  #       if identity.get('appId') == ENJIN_APP_ID:
  #         the_user = user
  #         the_identity = identity
  #         break
  #
  # except TransportQueryError as e:
  #   with open('Enjin.log', 'a') as errfile:
  #     print(datetime.datetime.now(), "[ENJIN update_player_info]", e, file=errfile)
  # except Exception as e:
  #   with open('Enjin.log', 'a') as errfile:
  #     print(datetime.datetime.now(), "[ENJIN update_player_info]", type(e), e, file=errfile)
  # else:
  #   if not the_user:
  #     return player
  #
  #   player.user_id = the_user['id']
  #   player.identity_id = the_identity['id']
  #   player.wallet = the_identity['wallet'].get('ethAddress', None)
  #   player.save()
  #
  #   return player


def get_player_tokens(player):
  player = get_player_info(player)
  if not player.wallet:
    return []

  query = """
  query GetPlayerTokens($id: Int!) {
    identity: EnjinIdentity(id: $id) {
      id
      tokens {
        id
        name
        balance
        metadata
        nonFungible
        transferable
        index
      }
    }
  }"""
  result = do_query(query, { 'id': player.identity_id })
  return result['identity'].get('tokens', [])

  
## the owner is the app creator
#  all transactions/minting are tied to its identity
def get_owner_info():
  #print("[ENJIN] checking app owner info", file=stderr)
  global owner_info

  if owner_info:
    return owner_info

  query="""
  query CheckOwnerInfo {
    EnjinApp {
      name
      owner {
        name
        identities {
          id
          appId
          linkingCode
          wallet { ethAddress }
        }
      }
    }
  }"""
  
  data = {
    'identity_id': -1,
    'wallet': '',
  }

  result = do_query(query)
  owner = result['EnjinApp']['owner']

  #print("DEBUG owner", owner, file=stderr)
  try:
    if not owner:
      raise Exception("Application does not have an owner")

    the_identity = None

    for identity in owner.get('identities'):
      if identity.get('appId') == ENJIN_APP_ID:
        the_identity = identity

    if not the_identity:
      raise Exception('The application does not have a linked wallet to mint or transfer')

    data['identity_id'] = the_identity.get('id', -1)
    data['wallet'] = the_identity.get('wallet').get('ethAddress') if the_identity.get('wallet') else None

    owner_info = data
  except Exception as e:
    raise TransportQueryError(str({ 'code': 90001, 'message': str(e) }))

  return owner_info


def get_token_info(token_id):
  token=None

  try:
    print("[EXCHANGE querying DB for token]")
    token = TokenInfo.objects.get(pk=token_id)
  except TokenInfo.DoesNotExist:
    print("[EXCHANGE must create a new entry]")
  except Exception as e:
    print("[EXCHANGE unknown exception 1]", type(e), e)
    raise e
  else:
    print('[EXCHANGE] token return 1')
    if token.updated_at > make_aware(datetime.datetime.now()-datetime.timedelta(minutes=15)):
      return token

  ## token does not exist in database. pull the original if exists
  try:
    print("[EXCHANGE querying ENJIN for token]")
    query="""
    query GetTokenInfo($id: String!) {
      token: EnjinToken(id: $id) {
        id
        name
        nonFungible
        metadata
      }
    }"""

    data = do_query(query, { 'id': str(token_id) })
  except TransportQueryError as e:
    error = eval(str(e))
    with open("Enjin.log", 'a') as errfile:
      print(datetime.datetime.now(), "[EXCHANGE get_token_info]", e, file=errfile)

    if error['code'] == 404:
      raise e
    else:
      raise TransportQueryError(str({ 'message': "Connection with Enjin failed" }))
  except Exception as e:
    print("[EXCHANGE unknown exception 2]", type(e), e)
    raise e
  else:
    print("[EXCHANGE we have token info]", data)
    tk = data.get('token')

  try:
    if not token:
      token = TokenInfo(id=tk.get('id'))

    token.name = tk.get('name', token.name)
    token.nonFungible = tk.get('nonFungible', token.nonFungible)
    token.metadata = json.dumps(tk.get('metadata', token.metadata)) if tk.get('metadata') else None
    token.save()
  except Exception as e:
    print("[EXCHANGE unknown exception 3]", type(e), e)
    raise e
  else:
    print("[EXCHANGE return saved token]")
    return token


def get_latest_transactions():
  query="""
  query TransactionsList {
    app: EnjinApp {
      transactions {
        id
        title
        tokenId
        value
        type
        createdAt
      }
    }
  }"""
  result = do_query(query)
  return result.get('app', {}).get('transactions', [])


def get_tokens():
  query="""
  query GetTokens {
    app: EnjinApp {
      tokens {
        id
        name
        nonFungible
        transferable
        metadata
      }
    }
  }"""
  result = do_query(query)
  tokens = result['app'].get('tokens', [])

  return tokens


def get_single_tx_info(txid):
  query="""
  query GetTXInfo($id: Int) {
    tx: EnjinTransactions(id:$id) {
      id
      encodedData
      transactionId
      state
    }
  }
  """

  result = do_query(query, { 'id': txid })
  return result.get('tx', [])[0]
