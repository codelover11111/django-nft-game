"""
This is the module to interact with the PVE authentication methods.
"""
import datetime
import sys
import traceback

import requests, math, json, os
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from .models import PlayerBase, OffchainCrownCredit

from .models import Blacklist


TOKEN = os.getenv('TOKEN')
PVE_URL = os.getenv('PVE_URL')
ARENA_KEY = os.getenv('ARENA_KEY')
ARENA_KEY_NUMBER = int(os.getenv('ARENA_KEY_NUMBER'))

MSG_TEXT = {
  "WRONG_USER_OR_PASS": "Wrong username or password",
  "WRONG_DOMAIN": "Invalid operation",
  "WRONG_PARAMS": "Wrong parameters",
  "None": None,
}


def authenticate(name, pwd):
  momentum = ord(ARENA_KEY[0]) * ARENA_KEY_NUMBER / ord(name[-1]) * math.sqrt(ord(pwd[0]))
  data = {
    'user': name,
    'password': pwd,
    'momentum': momentum,
    'key': len(name+pwd),
  }
  r = requests.post(PVE_URL+'api/login/', data=json.dumps(data))

  status = {
    "error": False,
    "user": None
  }

  if not r.ok:
    status["error"] = f"Error code: {r.status_code}"
    return status

  response = r.json()

  if response.get("MSG") != "OK":
    msg = response.get('MSG', 'None')

    status["error"] = MSG_TEXT[msg]
    return status

  # create or return local user
  if not PlayerBase.objects.filter(nick_name=name).exists():
    status["user"] = PlayerBase(nick_name=name)
    status["user"].save()
  else:
    status["user"] = PlayerBase.objects.get(nick_name=name)

  ## return user by default
  return status



def register(name, email, pwd):
  ## return object
  status = {
    "error": False,
    "user": None
  }

  # check if user exists locally or email is registered
  if PlayerBase.objects.filter(nick_name=name).exists():
    status["error"] = "Username already exists"
    return status

  if PlayerBase.objects.filter(email=email).exists():
    status["error"] = "Email is already used"
    return status

  ## remote registration process
  ses = requests.Session() # session to store csrf and handshake session
  ses.cookies['app_version'] = TOKEN


  ## request a handshake
  req = ses.get(PVE_URL + 'handshake/')
  if not (req.ok and req.text == 'handshake'):
    status["error"] = f"Error. Handshake: {req.text}"
    return status

  # so far so good. handshake done, let's register
  data = {
    'user': name,
    'pass': pwd,
    'token': TOKEN,
    'csrfmiddlewaretoken': ses.cookies.get('csrftoken'),
  }

  req = ses.post(PVE_URL + 'register/', data=data)
  print("[DEBUG REGISTER RESPONSE]", req.text)

  ## server error
  if not req.ok:
    status["error"] = f'[Remote Server Response]: {req.status_code}'
    return status

  ## request error
  if req.text != 'OK':
    if req.text == "error Nickname Already Exist":
      status["error"] = "Username already exists"
    elif req.text == "error on password":
      status["error"] = "Password cannot contain special characters"
    else:
      status["error"] = req.text

    return status

  ## we're safe to create a user
  try:
    status['user'] = PlayerBase(nick_name=name, email=email)
    status['user'].save()
  except Exception as e:
    status["error"] = f"Error creating user: {e}"

  ## if everything went ok
  return status


def pve_password_reset(name, pwd):
  ses = requests.Session() # session to store csrf and handshake session
  ses.cookies['app_version'] = TOKEN

  momentum = ord(ARENA_KEY[0]) * ARENA_KEY_NUMBER / ord(name[-1]) * math.sqrt(ord(pwd[0]))

  status = {
    "error": False,
    "user": None
  }

  ## request a handshake
  req = ses.get(PVE_URL + 'handshake/')
  if not (req.ok and req.text == 'handshake'):
    status["error"] = f"Error. Handshake: {req.text}"
    return status

  # so far so good. handshake done, let's register
  data = {
    'user': name,
    'pass': pwd,
    'momentum': momentum,
    'csrfmiddlewaretoken': ses.cookies.get('csrftoken'),
  }

  req = ses.post(PVE_URL + 'api/passreset/', data=data)

  print("[DEBUG REGISTER RESPONSE]", req.text)

  ## server error
  if not req.ok:
    status["error"] = f'[Remote Server Response]: {req.status_code}'
    return status

  data = req.json()
  print("[DEBUG DATA]", data)

  ## request error
  if not data['status']:
    status['error'] = f"[PVE Response]: {data['error']}"
    return status

  return "OK"


### DECORATORS
## Authentication decorator
def needs_user_auth(func):
  def inner(request, **kw):
    if request.session.get("name") and (datetime.datetime.timestamp(timezone.now()) - request.session.get("last_ping")) > datetime.timedelta(minutes=15).total_seconds():
      logout(request)
      return redirect("/signin/")
    request.session["last_ping"] = datetime.datetime.timestamp(timezone.now())

    if not request.session.get("name", None) or request.session.get('is_admin', None):
        return redirect("/signin/")
    else:
        return func(request, **kw)

  return inner


## Authentication decorator
def needs_admin_auth(func):
  def inner(request, **kw):
    if request.session.get("name", None) and request.session.get('is_admin', None):
      return func(request, **kw)
    else:
      return redirect("/")

  return inner


## Protection decorator
#  blacklist unconventional behaviour

### Client IP Address
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _notify_ban(bl):
  # banned
  response = HttpResponse(f"Your IP is under review for inappropriate behaviour. Reason: {bl.banned_reason}")
  response.status_code = 406
  return response


def protected(protections=('short time', 'user hopping', 'user fail', 'no referer',)):
  def protected_inner(func):
    """Blacklist strange behaviour
    directed to the protected endpoints"""
    def inner(request, **kw):
      ## check if ip is blocked
      ip = get_client_ip(request)

      bl, is_new = Blacklist.objects.get_or_create(ip=ip)
      now = timezone.now()

      ## if not banned check if there's reason to
      if not (bl.banned_for and bl.banned_at):
        if bl.check_banning(request, protections):
          return _notify_ban(bl)
      else:
        ## check banned status by banned timestamp
        # print("[DEBUG]", bl.banned_at, bl.banned_for, timezone.now(), file=sys.stderr)
        if (bl.banned_at + bl.banned_for) < now:
          # not banned anymore. clear the banned timestamp
          bl.ban_release()
        else:
          return _notify_ban(bl)

      if not is_new:
        # print("[DEBUG] ip is known", file=sys.stderr)
        bl.update_short_time(now)

      bl.request_touch()

      kw['bl'] = bl
      return func(request, **kw)

    return inner
  return protected_inner


def check_last_activity(f):
  def check_inner(request, **kw):
    if (timezone.now() - request.session.get("last_ping")) > datetime.timedelta(minutes=5):
      logout(request)
    request.session["last_ping"] = timezone.now()
    return f(request, **kw)

  return check_inner