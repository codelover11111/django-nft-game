import json
import traceback

from django.db.models import Func
from django.utils import timezone

from .models import EmailConfirmationRequest, PlayerBase, PasswordRecoveryRequest
from django.core.mail import send_mail
from smtplib import SMTPException
from django.utils.timezone import make_aware
import os

import requests
import datetime

CURRENT_ADDRESS=os.getenv("THIS_URL")
EMAIL_ADDR=os.getenv("EMAIL_HOST_USER")


### general email sending process
def send_email_to_user(user: PlayerBase, subject: str, message: str):
  try:
    done = send_mail(subject, message, EMAIL_ADDR, [user.email])
    print("[DEBUG EMAIL]", done)
    if done:
      return "OK"
  except SMTPException as e:
    print("[SMTP ERROR]", e)
    raise e
  except Exception as e:
    print("[EMAIL SEND ERROR]", type(e), e)
    raise e

  raise Exception("Email couldn't be sent")


## user email confirmation email
def send_email_confirmation(user: PlayerBase):
  try:
    confirmation = EmailConfirmationRequest(player=user)
    confirmation.save()
  except Exception as e:
    return e

  subject = "[Space Misfits] Confirm your email address"
  message = f"""Confirm your email address through this link:
  
  {CURRENT_ADDRESS}confirm/{confirmation.token}/
  
  Enjoy,
  
  from the Team of Sapce Misfits
  """

  return send_email_to_user(user, subject, message)


## password recovery email
def send_password_recovery(user: PlayerBase):
  try:
    ## clear all password recoveries
    user.passwordrecoveryrequest_set.all().delete()
    ## generate a new recovery request
    recovery = PasswordRecoveryRequest(player=user)
    recovery.save()
  except Exception as e:
    return e

  subject = "[Space Misfits] Reset your password"
  message = f"""Go to this address to reset your password:

  {CURRENT_ADDRESS}reset/{recovery.token}/

  Enjoy,

  from the Team of Space Misfits
  """

  return send_email_to_user(user, subject, message)


## general expiration check for models with "created_at" field
## default time is 24hs
## should be DEPRECATED. used only on password reset
def has_expired(model, time=86400):
  return (make_aware(datetime.datetime.now()).timestamp() - model.created_at.timestamp()) > time


### PVE CONSTANTS
TOKEN = os.getenv('TOKEN')
PVE_URL = os.getenv('PVE_URL')
ARENA_KEY = os.getenv('ARENA_KEY')
ARENA_KEY_NUMBER = int(os.getenv('ARENA_KEY_NUMBER'))


### PVE API requests
def api_get(url, **params):
  ses = requests.Session() # session to store csrf and handshake session
  ses.cookies['app_version'] = TOKEN

  status = {
    "status": 0,
    "error": False,
  }

  ## request a handshake
  req = ses.get(PVE_URL + 'handshake/')
  if not (req.ok and req.text == 'handshake'):
    status["error"] = f"Error. Handshake: {req.text}"
    return status

  # so far so good. handshake done, let's register
  params = {
    **params,
    # 'momentum': momentum,
    'csrfmiddlewaretoken': ses.cookies.get('csrftoken'),
  }

  req = ses.get(PVE_URL + 'api/' + url, params=params)

  ## server error
  if not req.ok:
    status["error"] = f'[Remote Server Response]: {req.status_code}'
    return status

  try:
    status = req.json()
  except Exception as e:
    status["error"] = str(e)

  return status


### PVE API requests
def api_post(url, **params):
  ses = requests.Session() # session to store csrf and handshake session
  ses.cookies['app_version'] = TOKEN

  status = {
    "status": 0,
    "error": False,
  }

  ## request a handshake
  req = ses.get(PVE_URL + 'handshake/')
  if not (req.ok and req.text == 'handshake'):
    status["error"] = f"Error. Handshake: {req.text}"
    return status

  # so far so good. handshake done, let's register
  params = {**params, 'csrfmiddlewaretoken': ses.cookies.get('csrftoken'),}

  req = ses.post(PVE_URL + 'api/' + url, data=params)

  ## server error
  if not req.ok:
    status["error"] = f'[Remote Server Response]: {req.status_code}'
    return status

  try:
    status = req.json()
  except Exception as e:
    status["error"] = str(e)

  return status


### websocket notifier connection
NOTIF_LOCAL_URL = os.getenv('NOTIF_LOCAL_URL')


def notifier_post(url, params):
  # session to store csrf and handshake session
  ses = requests.Session()
  # ses.cookies['app_version'] = TOKEN

  status = {
    "status": 0,
    "error": False,
  }

  ## set headers
  headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
  ## send the request
  req = ses.post(NOTIF_LOCAL_URL+'internal/api'+url, data=json.dumps(params), headers=headers)

  ## server error
  if not req.ok:
    status["error"] = f'[Remote Server Response]: {req.status_code}'
    return status

  try:
    status = req.json()
  except Exception as e:
    traceback.print_exc()
    print(type(e), e)
    status["error"] = str(e)

  return status


def jsoff_load(string):
  """Parse Ivan's fake JSON without quotes"""
  try:
    if string:
      return dict([_.split(":") for _ in string[1:-1].split(',')])
  except Exception as e:
    traceback.print_exc()

  return {}


class OfferExpired(Exception):
  pass


def check_offer_expired(offer):
  if timezone.now() >= offer.expires_at and offer.state in (offer.RESERVED, offer.SUBMITTED):
    raise OfferExpired("Offer expired")


name_ci = Func(
  'name_for_sale',
  function='utf8mb4_general_ci',
  template='(%(expressions)s) COLLATE "%(function)s"'
)