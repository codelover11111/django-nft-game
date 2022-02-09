import datetime

from django.db import models
from uuid import uuid4
import json

from django.utils import timezone
from mptt.models import MPTTModel, TreeForeignKey


## player
class PlayerBase(models.Model):
  nick_name = models.CharField(max_length=30, primary_key=True, unique=True)
  email = models.CharField(max_length=64, null=True, unique=True)
  id = models.PositiveBigIntegerField(default=0, db_index=True)
  # enjin data
  user_id = models.BigIntegerField(default=None, null=True, blank=True, db_index=True)
  identity_id = models.BigIntegerField(default=None, null=True, blank=True)
  wallet = models.CharField(max_length=43, null=True, blank=True)
  can_exchange = models.BooleanField(default=True)
  ## websocket notifier data
  notifier_token = models.CharField(max_length=256, blank=True, null=True)
  notifier_token_expiration = models.DateTimeField(null=True, blank=True)
  ## two-step verification data
  tfa_token = models.CharField(max_length=32, blank=True, null=True)
  tfa_email_code = models.CharField(max_length=6, null=True, blank=True)

class EmailConfirmationRequest(models.Model):
  token = models.UUIDField(default=uuid4, primary_key=True, null=False, editable=False)
  confirmed = models.BooleanField(default=False)
  created_at = models.DateTimeField(auto_now_add=True)
  player = models.ForeignKey(PlayerBase, null=True, on_delete=models.CASCADE)


class PasswordRecoveryRequest(models.Model):
  token = models.UUIDField(default=uuid4, primary_key=True, null=False, editable=False)
  created_at = models.DateTimeField(auto_now_add=True)
  player = models.ForeignKey(PlayerBase, null=True, on_delete=models.CASCADE)


## administration
class Manager(models.Model):
  username = models.CharField(max_length=30, unique=True)
  full_name = models.CharField(max_length=64, null=True, blank=True)
  email = models.CharField(max_length=30, unique=True, null=True, blank=True)
  password = models.CharField(max_length=89)

  def get_name(self):
    if self.full_name:
      return self.full_name
    else:
      return self.username


### blog
class BlogPost(models.Model):
  cover = models.ImageField(upload_to="images/", null=True, blank=True)
  preview = models.ImageField(upload_to="images/", null=True, blank=True)

  title = models.CharField(max_length=128, unique=True)
  slug = models.SlugField(max_length=32, unique=True)
  author = models.ForeignKey(Manager, on_delete=models.CASCADE)
  content = models.TextField()
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now= True)

  class Meta:
    ordering = ['-created_at']

  def __str__(self):
    return self.title

### team

class Team(models.Model):
  image = models.ImageField(upload_to="images/team/", null=True, blank=True)

  name = models.CharField(max_length=128, unique=True)
  role = models.CharField(max_length=128)
  position = models.IntegerField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now= True)

  class Meta:
    ordering = ['created_at', 'position']

  def __str__(self):
    return self.name
  
### team

class Tutorial(models.Model):
  poster = models.ImageField(upload_to="images/tutorial/", null=True, blank=True)
  video = models.FileField(upload_to="videos/tutorial/", null=True, blank=True)

  title = models.CharField(max_length=128, unique=True)
  description = models.TextField()
  length = models.CharField(max_length=20)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    ordering = ['-created_at']

  def __str__(self):
    return self.title

## categories

class Categories(MPTTModel):
  name = models.CharField(max_length=200)
  slug = models.SlugField(max_length=32, unique=True)
  icon = models.ImageField(upload_to="categories/", null=True, blank=True)
  parent = TreeForeignKey(
      'self',
      blank=True,
      null=True,
      related_name='child',
      on_delete=models.CASCADE
  )

  class Meta:
    ordering=['tree_id', 'lft']
    unique_together = ('slug', 'parent',)    
    verbose_name_plural = "categories"   

  def get_name(self):
    full_path = [self.name]            
    k = self.parent
    while k is not None:
      full_path.append(k.name)
      k = k.parent

    return ' -> '.join(full_path[::-1])

  def __str__(self):                           
    full_path = [self.name]            
    k = self.parent
    while k is not None:
      full_path.append(k.name)
      k = k.parent

    return ' -> '.join(full_path[::-1])


### products

class Products(models.Model):
  STATUS = (
    (0,"Inactive"),
    (1,"Active")
  )

  title = models.CharField(max_length=128, unique=True)
  description = models.TextField()
  image = models.ImageField(upload_to="products/", null=True, blank=True)
  category = models.ForeignKey(Categories, on_delete=models.CASCADE, related_name='category')
  price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
  put_quantity = models.IntegerField(default=0)
  out_quantity = models.IntegerField(default=0)
  status = models.IntegerField(choices=STATUS, default=1)
  is_limit = models.IntegerField(choices=STATUS, default=0)
  limit_quantity = models.IntegerField(default=0)
  ## attributes
  attributes = models.TextField(default='{}')

  ## product introduction
  pi_title = models.CharField(max_length=128)
  pi_description = models.TextField()
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now= True)

  class Meta:
    ordering = ['-created_at']

  def attributes_json(self):
    return json.loads(self.attributes)


class Cart(models.Model):
  STATUS = (
    (0,"Draft"),
    (1,"Paid")
  )

  customer = models.ForeignKey(PlayerBase, null=True, on_delete=models.CASCADE, related_name='customer')
  status = models.IntegerField(choices=STATUS, default=0)
  total_price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)


class CartItem(models.Model):
  cart = models.ForeignKey(Cart, null=True, on_delete=models.CASCADE, related_name='cart')
  product = models.ForeignKey(Products, null=True, on_delete=models.CASCADE, related_name='product')
  quantity = models.IntegerField(default=0)
  price = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)


class OrderDetail(models.Model):
  PAYMENT_STATUS = (
    (0,"Stripe"),
    (1,"Crypto")
  )
  customer_email = models.EmailField()
  cart = models.ForeignKey(Cart, null=True, on_delete=models.CASCADE, related_name='order_cart')
  amount = models.IntegerField(default=0)
  payment_intent = models.CharField(max_length=200, null=True, blank=True)
  transaction = models.CharField(max_length=200, null=True, blank=True)
  enjin_address = models.CharField(max_length=200, null=True, blank=True)
  payment_type = models.IntegerField(choices=PAYMENT_STATUS, default=0)
  has_paid = models.BooleanField(default=False)
  has_delivered = models.BooleanField(default=False)
  is_delete = models.BooleanField(default=False)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now_add=True)
  class Meta:
    ordering = ['-created_at']


### site settings

class Settings(models.Model):
  """
  Website main settings
  """
  download_link = models.CharField(max_length=256, null=True, blank=True, default='')
  
  ## explore block
  explore_title = models.CharField(max_length=256, null=True, blank=True, default='')
  explore_description = models.CharField(max_length=256, null=True, blank=True, default='')

  ## build block
  build_title = models.CharField(max_length=256, null=True, blank=True, default='')
  build_description = models.CharField(max_length=256, null=True, blank=True, default='')

  ## fight block
  fight_title = models.CharField(max_length=256, null=True, blank=True, default='')
  fight_description = models.CharField(max_length=256, null=True, blank=True, default='')

  ## trade block
  trade_title = models.CharField(max_length=256, null=True, blank=True, default='')
  trade_description = models.CharField(max_length=256, null=True, blank=True, default='')

  ## videos block
  videos_title = models.CharField(max_length=256, null=True, blank=True, default='')
  videos_description = models.CharField(max_length=256, null=True, blank=True, default='')

  video_title = models.CharField(max_length=256, null=True, blank=True, default='')
  video_link = models.CharField(max_length=256, null=True, blank=True, default='')

  video_author = models.CharField(max_length=256, null=True, blank=True, default='')
  video_author_link = models.CharField(max_length=256, null=True, blank=True, default='')

  video_thumbnail = models.ImageField(upload_to="images/", null=True, blank=True)


  ## faq
  faq_title = models.CharField(max_length=256, null=True, blank=True, default='')
  faq_description = models.CharField(max_length=256, null=True, blank=True, default='')

  faq_content = models.TextField(default='{}')

  ## trade block
  news_title = models.CharField(max_length=256, null=True, blank=True, default='')
  news_description = models.CharField(max_length=256, null=True, blank=True, default='')

  ## join
  join_title = models.CharField(max_length=256, null=True, blank=True, default='')
  join_description = models.CharField(max_length=256, null=True, blank=True, default='')

  telegram_link = models.CharField(max_length=256, null=True, blank=True, default='')
  discord_link = models.CharField(max_length=256, null=True, blank=True, default='')

  ## newsletter
  newsletter_description = models.CharField(max_length=256, null=True, blank=True, default='')

  def faq_json(self):
    return json.loads(self.faq_content)


## ENJIN
class Transaction(models.Model):
  # transaction_id
  app_transaction_id = models.BigIntegerField(default=-1)
  eth_transaction_id = models.CharField(max_length=67, null=True, blank=True)

  transaction_time = models.DateTimeField(null=True, blank=True)

  reservation_id = models.BigIntegerField(default=-1)
  reservation_updated = models.BooleanField(default=False)

  item_id = models.BigIntegerField(default=0,null=True, blank=True)
  item_name = models.CharField(max_length=164, null=True, default='', blank=True)
  q_items = models.FloatField(default=0.0)

  token_id = models.CharField(max_length=120, null=True, default='', blank=True)
  token_name = models.CharField(max_length=164, null=True, default='', blank=True)
  q_tokens = models.FloatField(default=0.0)

  ## if something happened during the exchange
  #  the transaction is marked as dirty
  dirty = models.BooleanField(default=False)
  nft = models.BooleanField(default=False)

  action = models.CharField(max_length=67, null=True, blank=True)
  player = models.ForeignKey(PlayerBase, on_delete=models.CASCADE, null=True, blank=True)

  status = models.CharField(max_length=32, default='', db_index=True, blank=True)
  details = models.TextField(default="{}")

  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  def __str__(self):
    return f"{self.app_transaction_id}: {self.status}"


class TokenInfo(models.Model):
  # general data
  id = models.CharField(max_length=64, default='', db_index=True, primary_key=True, unique=True)
  name = models.CharField(max_length=128, default='', blank=True)
  nonFungible = models.BooleanField(default=False)

  metadata = models.TextField(default=None, null=True, blank=True)

  updated_at = models.DateTimeField(auto_now=True)


class SuspiciousTransaction(models.Model):
  id = models.PositiveBigIntegerField(primary_key=True, db_index=True)
  title = models.CharField(max_length=256, blank=True)
  tokenId = models.CharField(max_length=64, blank=True)
  value = models.PositiveBigIntegerField(blank=True)
  type = models.CharField(max_length=64, null=True, blank=True)
  #state = models.CharField(max_length=64, null=True, blank=True)
  createdAt = models.DateTimeField()

  # this means the corresponding TX has been found
  related = models.BooleanField(default=False)


def get_time_in_24hs():
  return timezone.now() + datetime.timedelta(hours=24)


class MarketOffer(models.Model):
  TRADING = 'TRADING'
  SELLING = 'SELLING'
  BUYING = 'BUYING'

  TYPES = (
    (TRADING, 'Trading offer'),
    (SELLING, 'For Sale'),
    (BUYING, 'Looking to buy'),
  )

  CREATED = "CREATED"
  SUBMITTED = "SUBMITTED"
  RESERVED = "RESERVED"
  ACCEPTED = "ACCEPTED"
  COMPLETED = "COMPLETED"
  CANCELLED = "CANCELLED"
  UNCERTAIN = "UNCERTAIN"
  SUCCESS = "SUCCESS"
  FAILED = "FAILED"

  DEFINITIVE_STATUS = (ACCEPTED, CANCELLED, SUCCESS, FAILED)

  STATES = (
    (CREATED, 'New transaction offer created'),
    (SUBMITTED, 'Offer successfully submitted'),
    (RESERVED, 'Goods have been reserved'),
    (ACCEPTED, 'Accepted'),
    (COMPLETED, 'Closed. Finished succesfully'),
    (CANCELLED, 'Closed. Cancelled'),
    (UNCERTAIN, 'Status uncertain. Needs manual revision.'),
    (FAILED, 'Closed. Failed'),
  )

  CHOICES = (
    (SUBMITTED, "Transaction pending to be accepted"),
    (ACCEPTED, "Transaction accepted"),
    (CANCELLED, "Transaction rejected"),
  )

  uuid = models.UUIDField(default=uuid4, editable=False, db_index=True, unique=True)

  offer_type = models.CharField(max_length=32, choices=TYPES)
  state = models.CharField(max_length=32, choices=STATES)

  player_a = models.ForeignKey(PlayerBase, on_delete=models.CASCADE, related_name="my_offers")
  player_b = models.ForeignKey(PlayerBase, on_delete=models.CASCADE, related_name="their_offers", null=True)
  name_for_sale = models.TextField(default='', blank=True)

  pve_reservation_id = models.BigIntegerField(default=-1)
  ## NOTE: this should be 'change applied' instead of 'updated'.
  # this confirms if the reservation is up to date with the changes (returned/applied)
  pve_reservation_updated = models.BooleanField(default=False)
  should_check_remote = models.BooleanField(default=False)

  # check if player has submitted
  submitted_player_a = models.BooleanField(default=False)
  choice_player_a = models.CharField(max_length=16, choices=CHOICES, default=SUBMITTED)
  submitted_player_b = models.BooleanField(default=False)
  choice_player_b = models.CharField(max_length=16, choices=CHOICES, default=SUBMITTED)

  ## operation tax fee
  operation_fee = models.PositiveBigIntegerField(default=0)

  ## payment information
  payment_info = models.TextField(default="{}")

  ## Save error message
  failed_reason = models.TextField(default='', blank=True)
  ## check already modified flag
  touched = models.BooleanField(default=False)

  created_at = models.DateTimeField(auto_now_add=True)
  expires_at = models.DateTimeField(default=get_time_in_24hs)
  updated_at = models.DateTimeField(auto_now=True)


class Bundle(models.Model):
  """TRADING
  Format:
    { 'item': [{
        'id': int, # stack id, not item
        'amount'; int
      }, ...],
      'asset': [{
        'id': str,
        'amount': int,
        'index': str
      }]
    }
  """
  ## SELLING/BUYING
  # { 'item': [{ 'id': int, 'amount': int, 'asking': int, 'name': string }] }

  entries_struct = {"item": [], "asset": [], "mineral": [], "bits": 0}
  entries = models.TextField(default=json.dumps(entries_struct))

  player = models.ForeignKey(PlayerBase, on_delete=models.CASCADE, related_name="bundles")
  offer = models.ForeignKey(MarketOffer, on_delete=models.CASCADE)

  def __str__(self):
    return f"Bundle ({self.id}) | Offer ({self.offer.id}) - Player: {self.player.nick_name}"


class Blacklist(models.Model):
  """Store info for blocked users/IPs with suspicious behaviour"""
  ip = models.CharField(max_length=16, primary_key=True, db_index=True, unique=True)

  user_fail_strikes = models.PositiveSmallIntegerField(default=0)
  user_hopping_strikes = models.PositiveSmallIntegerField(default=0)
  short_time_strikes = models.PositiveSmallIntegerField(default=0)

  times_banned = models.PositiveIntegerField(default=0)

  latest_agent = models.CharField(max_length=1024, null=True, blank=True)
  latest_user_tried = models.CharField(max_length=30, null=True, blank=True)
  latest_request = models.DateTimeField(null=True, blank=True)

  banned_for = models.DurationField(null=True, blank=True)
  banned_at = models.DateTimeField(null=True, blank=True)
  banned_reason = models.CharField(max_length=256, null=True, blank=True)

  # TOLERANCES
  SHORT_TIME_TOLERANCE = 10
  USER_FAIL_TOLERANCE = 5
  USER_HOPPING_TOLERANCE = 5

  def add_user_fail(self, usr=None):
    fields = []
    if usr:
      if self.latest_user_tried and self.latest_user_tried != usr:
        self.user_hopping_strikes += 1
        self.user_fail_strikes = 0
      else:
        self.user_hopping_strikes = self.user_hopping_strikes
        self.user_fail_strikes += 1
      fields.extend(['user_hopping_strikes', 'user_fail_strikes'])

      self.latest_user_tried = usr
      fields.append('latest_user_tried')

    self.save(update_fields=fields)

  def clear_fails(self):
    self.user_fail_strikes = 0
    self.user_hopping_strikes = 0
    self.latest_user_tried = None
    self.save(update_fields=["user_fail_strikes","user_hopping_strikes","latest_user_tried"])

  def ban_release(self):
    self.user_fail_strikes = 0
    self.user_hopping_strikes = 0
    self.short_time_strikes = 0
    self.latest_user_tried = None
    self.latest_request = None
    self.banned_at = None
    self.banned_for = None
    self.save(update_fields=[
             "user_fail_strikes",
             "user_hopping_strikes",
             "short_time_strikes",
             "latest_user_tried",
             "latest_request",
             "banned_at",
             "banned_for"
    ], force_update=True)

  def request_touch(self):
    self.latest_request = timezone.now()
    self.save(update_fields=['latest_request'], force_update=True)

  def update_short_time(self, time):
    ## check time between requests
    if self.latest_request:
      difference = time - self.latest_request
      # print("[DEBUG] time difference", difference.seconds, file=sys.stderr)
      if difference.seconds < 1.5:
        self.short_time_strikes += 1
      else:
        self.short_time_strikes = 0
      self.save(update_fields=['short_time_strikes'], force_update=True)

  def auto_ban(self, reason):
    # print("[DEBUG] auto:", reason, file=sys.stderr)
    self.banned_reason = reason
    self.banned_at = timezone.now()
    self.banned_for = datetime.timedelta(days=3)
    self.times_banned += 1
    self.save(update_fields=['banned_at', 'banned_for', 'times_banned', 'banned_reason'], force_update=True)
    return True

  def check_banning(self, request, protections):
    ## check if marked for banning
    ## check request POST without referrer
    now = timezone.now()
    if request.method == 'POST':
      # print("[DEBUG] REFERER",request.META.get("HTTP_REFERER"), file=sys.stderr)
      if 'no referer' in protections and not request.META.get("HTTP_REFERER"):
        # print("[DEBUG] no referer", file=sys.stderr)
        self.banned_reason = "http post without referer"
        self.banned_at = now
        self.banned_for = datetime.timedelta(days=3)
        self.times_banned += 1
        self.save(update_fields=['banned_at', 'banned_for', 'times_banned', 'banned_reason'], force_update=True)
        return True

    ## check if short time reloads/requests surpass the tolerance
    if 'short time' in protections and self.short_time_strikes and self.short_time_strikes >= self.SHORT_TIME_TOLERANCE:
      # print("[DEBUG] short time", file=sys.stderr)
      self.banned_reason = "short time requests"
      self.short_time_strikes = 0
      self.banned_at = now
      self.banned_for = datetime.timedelta(days=3)
      self.times_banned += 1
      self.save(update_fields=['banned_at', 'banned_for', 'times_banned', 'banned_reason', 'short_time_strikes'], force_update=True)
      return True

    if 'user hopping' in protections and self.user_hopping_strikes and self.user_hopping_strikes >= self.USER_HOPPING_TOLERANCE:
      # print("[DEBUG] user hopping", file=sys.stderr)
      self.banned_reason = "user hopping"
      self.user_hopping_strikes = 0
      self.banned_at = now
      self.banned_for = datetime.timedelta(days=3)
      self.times_banned += 1
      self.save(update_fields=['banned_at', 'banned_for', 'times_banned', 'banned_reason', 'user_hopping_strikes'], force_update=True)
      return True

    if 'user fail' in protections and self.user_fail_strikes and self.user_fail_strikes >= self.USER_FAIL_TOLERANCE:
      # print("[DEBUG] user fail", file=sys.stderr)
      self.banned_reason = "user login fails"
      self.user_fail_strikes = 0
      self.banned_at = now
      self.banned_for = datetime.timedelta(days=3)
      self.times_banned += 1
      self.save(update_fields=['banned_at', 'banned_for', 'times_banned', 'banned_reason', 'user_fail_strikes'], force_update=True)
      return True


class TesterInvitation(models.Model):
  code = models.CharField(max_length=124, unique=True, db_index=True)
  consumed = models.BooleanField(default=False)
  created_at = models.DateTimeField(auto_now_add=True, editable=False)
  player = models.ForeignKey(PlayerBase, on_delete=models.CASCADE, null=True, blank=True)


class OffchainCrownCredit(models.Model):
  player = models.ForeignKey(PlayerBase, on_delete=models.CASCADE)
  offchain_hrc_balance = models.DecimalField(max_digits=36, decimal_places=18, default=0)
  offchain_bsc_balance = models.DecimalField(max_digits=36, decimal_places=18, default=0)
  offchain_erc_balance = models.DecimalField(max_digits=36, decimal_places=18, default=0)


class TransactionHistory(models.Model):
  player = models.ForeignKey(PlayerBase, on_delete=models.CASCADE)
  from_address = models.CharField(max_length=256, null=False, blank=False)
  to_address = models.CharField(max_length=256, null=False, blank=False)
  value = models.DecimalField(max_digits=36, decimal_places=18)
  hash = models.CharField(max_length=256, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  type = models.CharField(max_length=16, null=False, blank=False, default='hrc')


class Setup(models.Model):
  market_search_results = models.PositiveBigIntegerField(default=0)

class WithdrawTax(models.Model):
  TOKEN_TYPES = (
    ('bep', 'BSC Token'),
    ('erc', 'ERC Token'),
    ('hrc', 'HRC Token'),
  )
  tax_percent = models.FloatField(default=0.05)
  token_type = models.CharField(max_length=16, null=False, blank=False, choices=TOKEN_TYPES)
