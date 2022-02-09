import traceback
from datetime import datetime, timedelta
import json
from json import JSONDecodeError

from .process import api_post, notifier_post, api_get, jsoff_load
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction, MarketOffer
from .bg_tasks import tx_mon, bg_mon
from requests.exceptions import ConnectionError
from sys import stderr


def get_perks_info(pack_data, data_type, session):
  """
  Obtain player collected items information from the wallet
  """
  text = ""
  result = None
  try:
    if not data_type or data_type not in ('ship', 'weapon', 'module'):
      raise Exception(f"invalid or missing data type. doing nothing: {data_type}")

    if not session.get('perks_last_update') or session.get('perks_last_update') <= datetime.timestamp(datetime.now()-timedelta(seconds=60)):
      response = api_get('perks/')
      ### cache response
      data = response.get('data', {})
      ## parse data
      session['perks_data'] = {
        'titles_ships': jsoff_load(data.get("titles_ships")),
        'mods_ships': jsoff_load(data.get("mods_ships")),
        'titles_weapons': jsoff_load(data.get("titles_weapons")),
        'mods_weapons': jsoff_load(data.get("mods_weapons")),
        'titles_modules': jsoff_load(data.get("titles_modules")),
        'mods_modules': jsoff_load(data.get("mods_modules")),
      }
      ## update last fetch time
      session['perks_last_update'] = datetime.timestamp(datetime.now())

    ## unpack perks data
    data = json.loads(pack_data)

    ## get key name and apply nodifier
    for k in data:
      key = session['perks_data'][f'titles_{data_type}s'][k]
      mod = int(session['perks_data'][f'mods_{data_type}s'][k])
      val = data[k]*mod
      text += f"<li class='list-group-item'><strong>{key}:</strong> <span class='text-success'>{val}<span></li>"

  except JSONDecodeError:
    return {}
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, e, file=stderr)
    traceback.print_exc(file=stderr)
  else:
    if text:
      result = f"<ul class='list-group small'>{text}</ul>"

  return result


def get_player_items(player):
  """
  Obtain player collected items information from the wallet
  """
  try:
    data = {'user': player.nick_name}
    response = api_post('user/items/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def regroup_player_stacks(player):
  """
  Regroup all the dispersed stacks in the same places
  """
  try:
    data = {'name': player.nick_name}
    response = api_post('user/items/regroup/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def get_player_items_for_sale(player):
  """
  Obtain player collected items information from the wallet
  Only sellable items
  """
  try:
    data = {'user': player.nick_name}
    print(data)
    response = api_post('user/items/forsale/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def get_player_minerals(player):
  """
  Obtain player collected minerals information from the wallet
  """
  try:
    data = {'user': player.nick_name}
    print(data)
    response = api_post('user/minerals/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def check_player_enj_wallet(player):
  ## get single item information
  try:
    data = {'user': player.nick_name}
    response = api_post('has_wallet/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def check_player_has_inventory(nick_name):
  ## get single item information
  try:
    response = api_post(f'has_inventory/{nick_name}/')
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def get_player_single_item(player, item_id):
  ## get single item information
  try:
    data = {'user': player.nick_name, 'item': item_id}
    response = api_post('item/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def reserve_item_for_exchange(player, amount, item_id, txid):
  """
  reserve items in the PVE database for later exchange
  """
  try:
    data = {'user': player.nick_name, 'amount': abs(amount), 'item': item_id, 'txid': txid}
    response = api_post('item/reserve/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def update_player_items(reservation_id, new_status):
  """
  Update player wallet content (return content or confirm action)
  """
  try:
    data = {'reservation': reservation_id, 'status': new_status}
    response = api_post('item/reserve/update/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def resync_transaction(txid):
  data = {'txid': txid}
  try:
    response = api_post('item/reserve/resync/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def search_user(string, me):
  data = {'string': string, "me": me}
  try:
    response = api_post('user/search/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def user_exists_in_pve(name):
  data = {'name': name}
  try:
    response = api_post('user/exists/', **data)
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


### market & trading
#
def reserve_bundle(bundle):
  try:
    response = api_post('trading/reserve/', data=json.dumps(bundle))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def update_market_reservation_in_pve(reservation_id, tx_id, action):
  try:
    response = api_post('trading/reserve/update/', data=json.dumps({
      "id": reservation_id,
      "tx_id": tx_id,
      "action": action,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def reserve_bundle_for_sale(bundle):
  try:
    response = api_post('market/reserve/', data=json.dumps(bundle))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def reserve_for_buyer(offer):
  try:
    response = api_post('market/setdown/', data=json.dumps({
      "id": offer.pve_reservation_id,
      "tx_id": offer.id,
      "buyer": offer.player_b.id,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def purchase_reservation_in_pve_v2(offer):
  try:
    response = api_post('market/purchase/', data=json.dumps({
      "reservation_id": offer.pve_reservation_id,
      "offer_id": offer.id,
      "buyer_id": offer.player_b.id,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def release_buyer_reservation(offer):
  try:
    response = api_post('market/release/', data=json.dumps({
      "id": offer.pve_reservation_id,
      "tx_id": offer.id,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


def return_reservation_for_sale(offer):
  try:
    response = api_post('market/return/', data=json.dumps({
      "id": offer.pve_reservation_id,
      "tx_id": offer.id,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


## WS notifications
def trading_notify(offer_uuid, action, data):
  try:
    response = notifier_post(f'/{offer_uuid}/{action}/', data)
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    traceback.print_exc(file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}
  else:
    return response


def general_notify(secret_key, order, title, message, extra={}):
  try:
    response = notifier_post(f'/notify/{secret_key}/',
                             {"order": order, "title": title, "message": message, "extra": extra})
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {
      'status': 0,
      'connection': True,
      'error': 'Connection failed while trying to communicate with the main service',
      'source': 'function'
    }
  except Exception as e:
    print("EXCEPTION IN API", type(e), e, file=stderr)
    traceback.print_exc(file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}
  else:
    return response


## signal listener for the Exchange Transactions model
@receiver(post_save, sender=Transaction)
def update_reservation(signal, **kw):
  """
  Update item reservation status in the PVE database
  This is called when the save() method is used on a Transaction object
  """
  m = kw.get('instance')

  if m and m.id != -1:
    if m.status in ("PENDING", "BROADCAST", "TP_PROCESSING",):
      bg_mon.event.set()
      return

    if m.status == 'WAITING_FOR_EXCHANGE':
      tx_mon.event.set()
      return

    if not m.reservation_updated:
      if m.status == 'EXECUTED':
        response = update_player_items(m.reservation_id, 'APPLIED')
        if response.get('status') or response.get('error') == "cannot modify reservation status":
          Transaction.objects.filter(pk=m.id).update(reservation_updated=True)
      elif m.status in ('CANCELED_USER', 'CANCELED_PLATFORM', 'DROPPED', 'FAILED',):
        response = update_player_items(m.reservation_id, 'ROLLED_BACK')
        if response.get('status') or response.get('error') == "cannot modify reservation status":
          Transaction.objects.filter(pk=m.id).update(reservation_updated=True)
      elif m.status == 'FAILED_AT_RESERVATION':
        response = resync_transaction(m.id)
        if response.get('status'):
          Transaction.objects \
            .filter(id=m.id) \
            .update(reservation_updated=True,
                    reservation_id=response.get('data', {}).get('reservation', m.reservation_id))
    else:
      print("[DEBUG UNKNOWN ERROR]:", m, file=stderr)


## signal listener for the Trading and Market model
@receiver(post_save, sender=MarketOffer)
def update_market_reservation(signal, **kw):
  """
  Update item reservation status in the PVE database
  This is called when the save() method is used on a Transaction object
  """
  m = kw.get('instance')

  if m.touched:
    print("avoiding duplicate edition", m)
    return

  #### TRADING states hooks
  if m.offer_type == m.TRADING:
    if m.state == m.SUBMITTED:
      if m.pve_reservation_id != -1:
        return

      ## make items reservation
      bundle_a = json.loads(m.player_a.bundles.get(offer=m).entries)
      bundle_b = json.loads(m.player_b.bundles.get(offer=m).entries)

      response = reserve_bundle({
        "offer_id": m.id,
        "player_a": {
          'nick_name': m.player_a.nick_name,
          'bits': bundle_a.get("bits", 0),
          'items': [{'stack_id': int(_["id"]), 'amount': int(_["amount"])} for _ in bundle_a["item"]],
          'minerals': [{'stack_id': int(_["id"]), 'amount': int(_["amount"])} for _ in bundle_a["mineral"]],
        },
        "player_b": {
          'nick_name': m.player_b.nick_name,
          'bits': bundle_b.get("bits", 0),
          'items': [{'stack_id': int(_["id"]), 'amount': int(_["amount"])} for _ in bundle_b["item"]],
          'minerals': [{'stack_id': int(_["id"]), 'amount': int(_["amount"])} for _ in bundle_b["mineral"]],
        },
      })

      if response.get("status"):
        rid = response.get("data", {}).get("id", -1)
        if rid != -1:
          m.pve_reservation_id = rid
          m.state = m.RESERVED
        else:
          m.state = m.FAILED
      else:
        if response.get('connection'):
          m.should_check_remote = True
        m.failed_reason = str(response.get("error"))
        m.state = m.FAILED

      ## don't taint. we need to trigger other states
      m.save()

    elif m.state == m.RESERVED:
      trading_notify(m.uuid, 'RESERVED', {"target": "both"})
      ## taint so it can't fall in the same hook twice
      m.touched = True
      m.save()

    elif m.state == m.ACCEPTED:
      response = update_market_reservation_in_pve(m.pve_reservation_id, m.id, 'APPLY')
      if response.get("status"):
        m.pve_reservation_updated = True
        m.state = m.COMPLETED
      else:
        if response.get('connection'):
          m.should_check_remote = True
        else:
          m.state = m.FAILED
          m.failed_reason = response.get("error")
      ## taint so it can't fall in the same hook twice
      m.touched = True
      m.save()

    elif m.state == m.CANCELLED:
      response = update_market_reservation_in_pve(m.pve_reservation_id, m.id, 'RETURN')
      if response.get("status"):
        m.pve_reservation_updated = True
      elif response.get('connection'):
        m.should_check_remote = True
      ## taint so it can't fall in the same hook twice
      m.touched = True
      m.save()
      trading_notify(m.uuid, 'CANCELLED', {"target": "both"})

    elif m.state == m.COMPLETED:
      trading_notify(m.uuid, 'COMPLETED', {"target": "both"})

    elif m.state == m.FAILED:
      if m.pve_reservation_id != -1:
        response = update_market_reservation_in_pve(m.pve_reservation_id, m.id, 'RETURN')
        if response.get("status"):
          m.pve_reservation_updated = True
        elif response.get('connection'):
          m.should_check_remote = True

      trading_notify(m.uuid, 'FAILED', {"target": "both"})
      ## taint so it can't fall in the same hook twice
      m.touched = True
      m.save()

  #### SELLING states hooks
  elif m.offer_type == m.SELLING:
    if m.state == m.ACCEPTED:
      pass
    elif m.state == m.FAILED or m.state == m.CANCELLED:
      if m.pve_reservation_id != -1:
        response = return_reservation_for_sale(m)
        if response.get("status"):
          m.pve_reservation_updated = True
        elif response.get('connection'):
          m.should_check_remote = True

      ## taint so it can't fall in the same hook twice
      m.touched = True
      m.save()
