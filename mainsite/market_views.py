## MARKETPLACE
### Trading
import json
import traceback
from datetime import timedelta
from os import getenv
from sys import stderr

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from mainsite.custom_auth import needs_user_auth
from mainsite.models import MarketOffer, PlayerBase, Bundle, Setup
from mainsite.player_api import search_user, user_exists_in_pve, trading_notify, get_player_minerals, general_notify, \
  get_player_items_for_sale, get_perks_info, check_player_has_inventory, reserve_for_buyer, reserve_bundle_for_sale, \
  get_player_single_item, purchase_reservation_in_pve_v2, regroup_player_stacks

### TRADING API
from mainsite.process import check_offer_expired, OfferExpired, name_ci


@needs_user_auth
def search_users(request):
  if request.method == 'POST':
    string = json.loads(request.body or b'{}').get('string','')
    result = search_user(string, request.session["name"])

    return JsonResponse(result)
  else:
    return JsonResponse({"status": 0, "error": f"{request.method} not supported"})


@needs_user_auth
def trading_main_view(request):
  context = {"errors": [], 'active_menu': 'trading'}
  current_page = abs(int(request.GET.get("page", 1)))

  if request.session.get("trading_errors"):
    e = request.session.pop("trading_errors").split("\n")
    context["errors"] = [*filter(lambda x: x, e)]

  name = request.session["name"]
  offers = []

  for offer in MarketOffer.objects.filter(
      Q(player_a_id=name) | Q(player_b_id=name),
      offer_type=MarketOffer.TRADING
  ).order_by("-created_at"):
    try:
      if offer.state == offer.CREATED:
        check_offer_expired(offer)
    except OfferExpired:
      offer.state = offer.FAILED
      offer.failed_reason = "Offer expired"
      offer.save()
    finally:
      offers.append(offer)

  p = Paginator(offers, 6)

  context.update({
    "offers": p.page(current_page),
    "me": name,
    "states": dict(MarketOffer.STATES),
    "has_inventory": check_player_has_inventory(name),
  })

  return render(request, 'backend/user/trading/main.html', context)


@csrf_exempt
@needs_user_auth
def trading_make_offer(request):
  """
  TRADING MAIN view
  creates the offer object with both users and bundle objects
  """
  if request.method != "POST":
    return JsonResponse({"status": 0, "error": f"{request.method} not supported"})

  create_local_player_b = False
  player_b = None
  response = {'status': 0, 'active_menu': 'trading'}
  data = {}

  try:
    data = json.loads(request.body)
    if data.get("nick_name") == request.session["name"]:
      raise Exception("You cannot send a request to yourself")

    exists_in_pve = user_exists_in_pve(data.get("nick_name"))

    if not exists_in_pve.get('status'):
      raise Exception(f'ERROR: {exists_in_pve.get("error", "Unknown error")}')

    if exists_in_pve.get('data'):
      player_b = PlayerBase.objects.get(pk=data.get("nick_name", None))
    else:
      raise Exception("User does not exist")

  except PlayerBase.DoesNotExist as e:
    create_local_player_b = True

  except Exception as e:
    # if a random exception happens we do nothing
    traceback.print_exc()
    return JsonResponse({"status": 0, "error": str(e)})

  ## this is for users who haven't logged in
  if create_local_player_b:
    player_b = PlayerBase(nick_name=data.get("nick_name"))
    player_b.save()

  try:
    fields = {
      "player_a": PlayerBase.objects.get(pk=request.session["name"]),
      "player_b": player_b,
      "offer_type": MarketOffer.TRADING,
      "state": MarketOffer.CREATED,
    }
    new_offer = MarketOffer(**fields)
    new_offer.save()

    Bundle(offer=new_offer, player=new_offer.player_a).save()
    Bundle(offer=new_offer, player=new_offer.player_b).save()
  except Exception as e:
    traceback.print_exc()
    response['error'] = str(e)
  else:
    ## notify about new trade offed
    extra = {'url': reverse('trading_view_offer', kwargs={"offer_uuid": str(new_offer.uuid)})}
    general_notify(player_b.notifier_token, 'TRADING', 'NEW Trading invitation!!!', f'{fields["player_a"].nick_name} invited you to trade', extra)

    ## send response
    response['status'] = 1
    response['data'] = new_offer.uuid

  return JsonResponse(response)


@needs_user_auth
def trading_view_offer(request, offer_uuid):
  """view still open/editable trading offers"""
  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid, offer_type=MarketOffer.TRADING)

    if offer.state != offer.CREATED:
      return redirect('trading_view_offer_closed', offer_uuid=offer_uuid)

    check_offer_expired(offer)

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    items = get_player_items_for_sale(me)
    minerals = get_player_minerals(me)

    if not items.get("status"):
      raise Exception(items.get("error"))

    inventory = {"item": {}, "mineral": {}, "bits": 0}

    ## group items in inventory
    for item in items.get("data"):
      if item["current_carry_type"] == 'STATION':
        inventory["item"][str(item["id"])] = {
          "id": item["id"],
          "amount": int(item["amount"]),
          "name": item["item"]["name"],
          "image": item["item"]["image"],
          "image_background": item["item"]["image_background"],
          'details': get_perks_info(item.get("pack_data"), (item["item"].get("pack_type") or '').lower(), request.session),
          'can_recycle': int(item["permissions"]["recycle"])
        }

    ## group items in inventory
    for mineral in minerals.get("data"):
      if mineral["current_carry_type"] == 'STATION':
        inventory["mineral"][str(mineral["id"])] = {
          "id": mineral["id"],
          "amount": int(mineral["amount"]),
          "name": mineral["mineral"]["name"],
          "image": mineral["mineral"]["image"],
          "image_background": mineral["mineral"]["image_background"],
        }

    ## sort bundles
    if me == offer.player_a:
      they = offer.player_b
      i_submitted = offer.submitted_player_a
      peer_submitted = offer.submitted_player_b
    else:
      they = offer.player_a
      i_submitted = offer.submitted_player_b
      peer_submitted = offer.submitted_player_a

    my_bundle = json.loads(offer.bundle_set.get(player=me).entries)
    their_bundle = json.loads(offer.bundle_set.get(player=they).entries)

    if not (offer.submitted_player_a and offer.submitted_player_b):
      ## remove from reserver from inventory (if items haven't been reserved yet)
      for entry in my_bundle["item"]:
        if inventory["item"].get(entry["id"]):
          inventory["item"][entry["id"]]["amount"] -= entry["amount"]

      for entry in my_bundle["mineral"]:
        if inventory["mineral"].get(entry["id"]):
          inventory["mineral"][entry["id"]]["amount"] -= entry["amount"]

  except OfferExpired as e:
    offer.state = offer.FAILED
    offer.failed_reason = "Offer expired"
    offer.save()
    return redirect('trading_view_offer_closed', offer_uuid=offer_uuid)

  except Exception as e:
    print(type(e), e)
    traceback.print_exc()
    context = {'active_menu': 'trading'}

  else:
    context = {
      "items": list(inventory["item"].values()),
      "minerals": list(inventory["mineral"].values()),
      "bits": int(items.get("bits", 0)) - int(my_bundle.get('bits', 0)),
      "my_bundle": my_bundle,
      "their_bundle": their_bundle,
      "offer": offer,
      "me": me,
      "they": they,
      "i_submitted": i_submitted,
      "peer_submitted": peer_submitted,
      "pve": getenv("PVE_PUBLIC_URL", '')[:-1],
      'active_menu': 'trading'
    }

  return render(request, 'backend/user/trading/offer_open.html', context)


@csrf_exempt
@needs_user_auth
def trading_view_offer_closed(request, offer_uuid):
  """view offers that cannot be edited anymore, whether they're accepted/cancelled or not"""
  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid, offer_type=MarketOffer.TRADING)

    if offer.state == offer.CREATED:
      return redirect('trading_view_offer', offer_uuid=offer_uuid)

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    ## sort bundles
    if me == offer.player_a:
      they = offer.player_b
      my_choice = offer.choice_player_a
    else:
      they = offer.player_a
      my_choice = offer.choice_player_b

    my_bundle = json.loads(offer.bundle_set.get(player=me).entries)
    their_bundle = json.loads(offer.bundle_set.get(player=they).entries)

  except Exception as e:
    print(type(e), e)
    traceback.print_exc()
    context = {'active_menu': 'trading'}
  else:
    context = {
      "me": me,
      "they": they,
      "my_bundle": my_bundle,
      "their_bundle": their_bundle,
      "offer": offer,
      "states": dict(offer.STATES),
      "choices": dict(offer.CHOICES),
      "my_choice": my_choice,
      'active_menu': 'trading'
    }

  return render(request, 'backend/user/trading/offer_closed.html', context)


@csrf_exempt
@needs_user_auth
def trading_update_offer(request, offer_uuid):
  """
  update offer bundle for an individual user
  """
  if request.method != "POST":
    return JsonResponse({"status": 0, "error": f"{request.method} not supported"})

  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid)

    if offer.submitted_player_a and offer.submitted_player_b:
      raise Exception("This offer cannot be modified anymore")

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    body = json.loads(request.body)
    action = body.get("action")
    data = body.get("data")
    entries_type = ("item", "mineral", "asset")

    ## convert data type to the proper type
    data.update({"amount": abs(int(data.get("amount", '0')))})

    if request.session["name"] not in (offer.player_a_id, offer.player_b_id):
      raise Exception("Forbidden access. Your are not part of this trade")

    if not data:
      raise Exception("data parameter is mandatory")

    if not action:
      raise Exception("action parameter is mandatory")

    check_offer_expired(offer)

    ## reset submitted status for both
    offer.submitted_player_a = False
    offer.submitted_player_b = False
    offer.touched = False
    offer.save()

    ## retrieve user bundle entries
    bundle = offer.bundle_set.get(player_id=request.session["name"])
    entries = json.loads(bundle.entries)

    keys = entries.keys()
    for key in entries_type:
      if key not in keys:
        entries[key] = []

    if not entries:
      entries = {"item": [], "asset": [], "mineral": [], "bits": 0}

    if action == "ADD":
      found = False
      for entry in entries[data["type"]]:
        if entry["id"] == data["id"]:
          found = True
          entry.update(data)
          break

      if not found:
        entries[data["type"]].append(data)

    elif action == "REMOVE":
      for entry in entries[data["type"]]:
        if entry.get("id") == data.get("id"):
          i = entries[data["type"]].index(entry)
          entries[data["type"]].pop(i)

    elif action == "UPDATE_BITS":
      entries["bits"] = int(data.get("amount"))

    else:
      raise Exception("Incorrect action parameter")

    bundle.entries = json.dumps(entries)
    bundle.save()

  except OfferExpired:
    return JsonResponse({"status": 0, "error": 'OFFER_EXPIRED'})

  except Exception as e:
    traceback.print_exc()
    return JsonResponse({"status": 0, "error": str(e)})

  try:
    trading_notify(offer_uuid, action, {'item': data, 'identifier': request.session["name"]})
  except Exception as e:
    print(e, type(e))
    traceback.print_exc()
  else:
    return JsonResponse({"status": 1, "data": data})


@csrf_exempt
@needs_user_auth
def trading_submit(request, offer_uuid):
  """Lock the bundles and submit if necessary, before confirmation"""
  if request.method != "POST":
    return JsonResponse({"status": 0, "data": f"{request.method} not supported"})

  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid)

    check_offer_expired(offer)

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    if offer.submitted_player_a and offer.submitted_player_b:
      raise Exception("This offer cannot be modified anymore")

    if offer.player_a == me:
      offer.submitted_player_a = True
    elif offer.player_b == me:
      offer.submitted_player_b = True
    else:
      raise Exception("You are not allowed to interact here")

    if offer.submitted_player_a and offer.submitted_player_b:
      offer.state = offer.SUBMITTED

    offer.touched = False
    offer.save()

  except OfferExpired:
    return JsonResponse({"status": 0, "error": 'OFFER_EXPIRED'})

  except Exception as e:
    traceback.print_exc()
    return JsonResponse({"status": 0, "error": str(e)})

  try:
    trading_notify(offer_uuid, 'BUNDLE_LOCKED', {'identifier': request.session["name"]})
  except Exception as e:
    traceback.print_exc()
    print(e, type(e))

  return JsonResponse({"status": 1, "data": "OK"})


@csrf_exempt
@needs_user_auth
def trading_offer_resolve(request, offer_uuid):
  """Accept or Cancel trading offer"""
  if request.method != "POST":
    return JsonResponse({"status": 0, "data": f"{request.method} not supported"})

  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid)
    post = json.loads(request.body)

    check_offer_expired(offer)

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    if post.get("choice") not in (offer.ACCEPTED, offer.CANCELLED):
      raise Exception(f"Option not available: {post.get('choice')}")

    if not (offer.submitted_player_a and offer.submitted_player_b) and offer.state != offer.RESERVED:
      raise Exception("Cannot accept a trade until both parties submit their offers")

    if offer.state in offer.DEFINITIVE_STATUS:
      msg = dict(offer.CHOICES)
      raise Exception(msg[offer.state])

    if offer.player_a_id == request.session["name"]:
      offer.choice_player_a = post.get("choice")
    elif offer.player_b_id == request.session["name"]:
      offer.choice_player_b = post.get("choice")

    offer.save()
    offer.refresh_from_db()

    if offer.CANCELLED in (offer.choice_player_a, offer.choice_player_b):
      offer.state = offer.CANCELLED
      offer.touched = False
    elif offer.ACCEPTED == offer.choice_player_a and offer.ACCEPTED == offer.choice_player_b:
      offer.state = offer.ACCEPTED
      offer.touched = False

    offer.save()

    if offer.state != offer.RESERVED:
      trading_notify(offer.uuid, offer.state, {"identifier": request.session["name"]})
  except Exception as e:
    traceback.print_exc()
    return JsonResponse({"status": 0, "error": str(e)})

  return JsonResponse({"status": 1, "data": "OK"})


@csrf_exempt
@needs_user_auth
def cancel_trading(request, offer_uuid):
  """Accept or Cancel trading offer"""
  if request.method != "POST":
    return JsonResponse({"status": 0, "data": f"{request.method} not supported"})

  try:
    me = PlayerBase.objects.get(pk=request.session["name"])
    offer = MarketOffer.objects.get(uuid=offer_uuid)

    check_offer_expired(offer)

    if me not in (offer.player_a, offer.player_b):
      request.session["trading_errors"] = request.session.get("trading_errors", "") + "You are not part of that trade\n"
      return redirect("trading_main_view")

    if offer.state in offer.DEFINITIVE_STATUS:
      msg = dict(offer.CHOICES)
      raise Exception(msg[offer.state])

    if offer.player_a_id == request.session["name"]:
      offer.choice_player_a = offer.CANCELLED
    elif offer.player_b_id == request.session["name"]:
      offer.choice_player_b = offer.CANCELLED

    offer.state = offer.CANCELLED

    offer.touched = False
    offer.save()

    if offer.state != offer.RESERVED:
      trading_notify(offer.uuid, offer.state, {"identifier": request.session["name"]})
  except Exception as e:
    traceback.print_exc()

  return redirect(request.META.get('HTTP_REFERER', '/'))


@needs_user_auth
def market_main_view(request):
  """
  MARKET MAIN view
  """
  setup = Setup.objects.last()
  context = {"errors": [], 'active_menu': 'market'}
  current_page = abs(int(request.GET.get("page", 1)))

  if request.session.get("market_errors"):
    e = request.session.pop("market_errors").split("\n")
    context["errors"] = [*filter(lambda x: x, e)]

  try:
    me = PlayerBase.objects.get(nick_name=request.session.get("name"))
    required_types = (MarketOffer.SELLING,)

    # get all active offers
    offers = []

    data_sort = request.GET.get("sort")
    data_order = request.GET.get("order")

    # get a first match
    if request.GET.get("q"):
      context["word"] = request.GET["q"]
      matching = MarketOffer.objects.annotate(name_ci=name_ci).filter(
          offer_type__in=required_types,
          state=MarketOffer.SUBMITTED
      ).filter(Q(name_ci__icontains=request.GET["q"])).select_related("player_a")
    else:
      matching = MarketOffer.objects.filter(
          offer_type__in=required_types,
          state=MarketOffer.SUBMITTED
      ).select_related("player_a")

    ## sort by name
    if data_sort == "name":
      if data_order == 'reverse':
        matching = matching.order_by("-name_for_sale")
      else:
        matching = matching.order_by("name_for_sale")
    elif data_sort == "expiration":
      ## sort by default
      if data_order == 'reverse':
        matching = matching.order_by("-expires_at")
      else:
        matching = matching.order_by("expires_at")

    elif not data_sort:
      ## sort by default
      if data_order == 'reverse':
        matching = matching.order_by("updated_at")
      else:
        matching = matching.order_by("-updated_at")

    for offer in matching:
      if timezone.now() >= offer.expires_at:
        ## mark expired
        offer.state = offer.FAILED
        offer.failed_reason = "Market offer expired"
        offer.save()
        continue
      ## else
      entry = json.loads(offer.bundle_set.first().entries).get("item")
      offers.append({
        "obj": offer,
        "entry": entry.pop() if entry else {},
        "mine": offer.player_a == me,
        "pve": getenv("PVE_PUBLIC_URL", '')[:-1],
        "expires": offer.expires_at - timezone.now(),
      })

    ## sort by bits and quantity
    if data_sort in ("bits", "quantity"):
      if data_sort == "bits":
        if data_order == "reverse":
          offers = sorted(offers, key=lambda d: d['entry']['asking'])
        else:
          offers = sorted(offers, key=lambda d: d['entry']['asking'], reverse=True)
      else:
        if data_order == "reverse":
          offers = sorted(offers, key=lambda d: d['entry']['amount'])
        else:
          offers = sorted(offers, key=lambda d: d['entry']['amount'], reverse=True)

    p = Paginator(offers, setup.market_search_results)
    context["offers"] = p.page(current_page)
    context["sort"] = data_sort
    context["order"] = data_order
  except Exception as e:
    traceback.print_exc()
    print(type(e), e)
    context["errors"].append(str(e))

  return render(request, 'backend/user/market/list.html', context)


@needs_user_auth
def market_create_selling_offer(request):
  player = PlayerBase.objects.get(nick_name=request.session.get("name"))
  pve = getenv("PVE_PUBLIC_URL", '')[:-1]

  if request.method == 'POST':
    try:
      ## check the parameters are OK
      item_amount = abs(int(request.POST['amount']))
      if item_amount < 1:
        raise Exception("You cannot sell less than 1 item")

      asking = abs(int(request.POST['asking']))
      if asking < 1:
        raise Exception("Price cannot be less than 1")

      if "id" not in request.POST:
        raise Exception("You have to select an item to sell")

      ## store data and create offer
      item_info = get_player_single_item(player, request.POST["id"])

      if item_info.get("error"):
        raise Exception(item_info.get("error"))

      item = item_info.get("data")

      payload = {'item': [{
               'id': int(request.POST['id']),
               'name': request.POST['name'],
               'amount': item_amount,
               'asking': asking,
               'details': get_perks_info(item.get("pack_data"), (item["item"].get("pack_type") or '').lower(), request.session),
               'image': f"{pve}{item['item']['image']}" if item['item'].get("image") else None,
             }]}

      offer = MarketOffer(player_a=player, offer_type=MarketOffer.SELLING, state=MarketOffer.CREATED, name_for_sale=request.POST["name"])
      offer.save()

      bundle = offer.bundle_set.create(player=player, entries=json.dumps(payload))
      bundle.save()

      ## make items reservation
      response = reserve_bundle_for_sale({
        "offer_id": offer.id,
        "player": {
          'id': offer.player_a.id,
          'asking': abs(int(payload["item"][0]["asking"])),
          'items': [{
            'stack_id': int(payload["item"][0]["id"]),
            'amount': abs(int(payload["item"][0]["amount"]))
          }]
        }
      })

      if response.get("status"):
        rid = response.get("data", {}).get("id", -1)
        if rid != -1:
          offer.pve_reservation_id = rid
          offer.state = offer.SUBMITTED
        else:
          offer.state = offer.FAILED
      else:
        if response.get('connection'):
          offer.should_check_remote = True
        offer.failed_reason = "[ON RESERVATION]" + response.get("error")
        offer.state = offer.FAILED

      offer.save()
    except Exception as e:
      request.session["market_errors"] = request.session.get("market_errors", "") + str(e) + "\n"
    finally:
      return redirect("market_main_view")
  else:
    pve_items = get_player_items_for_sale(player)
    items = []
    for item in pve_items.get("data", []):
      try:
        print(item["current_carry_type"])
        items.append({
          'id': int(item['id']),
          'name': item['item']['name'],
          'amount': int(item['amount']),
          'details': get_perks_info(item.get("pack_data"), (item["item"].get("pack_type") or '').lower(), request.session),
          'image': f"{pve}{item['item']['image']}" if item['item'].get('image') else None,
        })
      except Exception as e:
        traceback.print_exc()

    return render(request, 'backend/user/market/sell.html', {"items": items, 'active_menu': 'market'})


@needs_user_auth
def market_purchase_v2(request, uid):
  if request.method != "POST":
    return HttpResponse("Request method not supported")

  try:
    player = PlayerBase.objects.get(nick_name=request.session.get('name'))
    offer = MarketOffer.objects.get(uuid=uid)

    if offer.state == offer.FAILED:
      raise Exception("Offer does not exist anymore")

    if offer.player_b and offer.player_b != player:
      raise Exception("Offer not available")

    check_offer_expired(offer)

    offer.player_b = player
    offer.state = offer.RESERVED
    offer.save()
    offer.refresh_from_db()

    response = purchase_reservation_in_pve_v2(offer)
    if response.get('status'):
      offer.state = offer.COMPLETED
      offer.save()
    else:
      if response.get('connection'):
        offer.should_check_remote = True
      elif response.get("error") == "NOT_ENOUGH_BITS":
        offer.state = offer.SUBMITTED
        offer.save()
        raise Exception("Not enough bits to purchase this item")
      else:
        offer.state = offer.FAILED
        offer.failed_reason = response.get("error")

      offer.save()
      raise Exception(response["error"])

  except OfferExpired as e:
    return JsonResponse({"status": 0, "error": 'OFFER_EXPIRED'})
  except Exception as e:
    traceback.print_exc()
    return JsonResponse({"status": 0, "error": str(e)})

  return JsonResponse({"status": 1, "data": offer.state, 'active_menu': 'market'})


@needs_user_auth
def market_purchase_history(request):
  player = PlayerBase.objects.get(pk=request.session.get("name"))

  my_purchases = player.their_offers\
    .filter(offer_type=MarketOffer.SELLING,
            state__in=(MarketOffer.ACCEPTED,
                       MarketOffer.COMPLETED,
                       MarketOffer.FAILED))\
    .select_related("player_a")\
    .order_by("-updated_at")

  purchased = []
  for purchase in my_purchases:
    purchased.append({
      "state": purchase.get_state_display(),
      "failed_reason": purchase.failed_reason,
      "created_at": purchase.created_at,
      "updated_at": purchase.updated_at,
      "item": json.loads(purchase.bundle_set.get(player=purchase.player_a).entries).get("item").pop()
    })

  created = []
  for creation in player.my_offers.filter(offer_type=MarketOffer.SELLING).order_by("-updated_at"):
    created.append({
      "state": creation.get_state_display(),
      "true_state": creation.state,
      "uuid": creation.uuid,
      "failed_reason": creation.failed_reason,
      "created_at": creation.created_at,
      "updated_at": creation.updated_at,
      "item": json.loads(creation.bundle_set.get(player=creation.player_a).entries).get("item").pop()
    })

  return render(request, "backend/user/market/history.html", {"purchased": purchased, "created": created, 'active_menu': 'market'})


@needs_user_auth
def regroup_stacks(request):
  if request.method != "POST":
    return HttpResponse(f"{request.method} not supported")

  try:
    player = PlayerBase.objects.get(nick_name=request.session.get('name'))
    regroup_response = regroup_player_stacks(player)

    if not regroup_response.get("status"):
      raise Exception(regroup_response.get("error"))
  except Exception as e:
    traceback.print_exc()
    return HttpResponse(str(e))
  else:
    return redirect(request.META.get('HTTP_REFERER', '/'))


@needs_user_auth
def cancel_market_sale(request):
  if request.method != 'POST':
    return HttpResponse(f"{request.method} not supported")

  try:
    print(request.POST)
    player = PlayerBase.objects.get(nick_name=request.session.get("name"))
    offer = player.my_offers.get(offer_type=MarketOffer.SELLING, uuid=request.POST.get("offer"), state=MarketOffer.SUBMITTED)

    offer.touched = False
    offer.state = offer.CANCELLED
    offer.save()
  except Exception as e:
    traceback.print_exc(file=stderr)
    print(e, type(e), file=stderr)

  return redirect(request.META.get('HTTP_REFERER', '/'))
