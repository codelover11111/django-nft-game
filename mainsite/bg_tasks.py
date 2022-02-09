import json
import traceback
from sys import stderr
from threading import Thread, Event
import datetime

from django.utils.timezone import make_aware

from .models import Transaction, SuspiciousTransaction, MarketOffer
from .enjin import check_transactions_status, exchange_for_tokens, get_latest_transactions, TransportQueryError
from .exceptions import CoolDownError

from requests.exceptions import ConnectionError, ConnectTimeout

import concurrent.futures as con
import os

from .process import api_post

TTIME_FORMAT="%Y-%m-%dT%H:%M:%S%z"


def updatefile(file):
  file.flush()
  os.fsync(file.fileno())


def resync_market_reservation_in_pve(tx_id, tx_type, action,):
  try:
    response = api_post('trading/reserve/resync/', data=json.dumps({
      "tx_id": tx_id,
      "tx_type": tx_type,
      "action": action,
    }))
    return response
  except ConnectionError as e:
    print("CONNECTION ERROR", e, file=stderr)
    return {'status': 0, 'connection': True, 'error': 'Connection failed while trying to communicate with the main service',
            'source': 'function'}
  except Exception as e:
    print("EXCEPTION IN API", type(e), file=stderr)
    return {'status': 0, 'error': str(e), 'source': 'function'}


class BgMon(Thread):
  """BgMon checks the status of saved transacions
  and updates it in case it changes"""
  def __init__(self):
    super(BgMon, self).__init__()
    self.DEFINITIVE_STATUS = ('CANCELED_USER',
                              'CANCELED_PLATFORM',
                              'DROPPED',
                              'FAILED',
                              'EXECUTED',
                              '',
                              'UNDER_REVISION',
                              'WAITING_FOR_EXCHANGE',
                              'ERROR_ON_SUBMIT',
                              'FAILED_AT_RESERVATION',)
    self.tx_list = []
    self.running = True
    self.event = Event()

  def run(self):
    ## set event to true for initial polling
    self.event.set()
    with open("BackgroundMonitor.log", 'a') as errfile:
      print(datetime.datetime.now(), "DAEMON STARTED", file=errfile)
      updatefile(errfile)
      while self.running:
        ## while we're at it, if there are no entries we just set it up
        print(datetime.datetime.now(), "[BGMON event status]", self.event.is_set(), file=errfile)
        self.tx_list = [] # ensure tx_list is clean

        if self.event.is_set() or Transaction.objects.exclude(status__in=self.DEFINITIVE_STATUS).count():
          self.event.clear()
          all_tx = list(Transaction.objects.exclude(status__in=self.DEFINITIVE_STATUS).values_list('app_transaction_id', flat=True)[:1000])
          while all_tx:
            self.tx_list.append(all_tx[:100])
            del all_tx[:100]
          print(datetime.datetime.now(), "[BGMON batches to process]", len(self.tx_list), file=errfile)
          updatefile(errfile)

        ## take a break if there are not transactions
        if not self.tx_list:
          self.event.wait(3600)
          continue

        for batch in self.tx_list:
          try:
            #print(datetime.datetime.now(), "[BGMON list]", len(batch), file=errfile)
            ## check status on enjin
            status_list = check_transactions_status(batch)
            #print(datetime.datetime.now(), "[BGMON] status list", status_list, file=errfile)
            tx_status = list( filter( lambda x: x.get('state') in self.DEFINITIVE_STATUS, status_list ) )
            print(datetime.datetime.now(), "[BGMON filtered]", len(tx_status), file=errfile)
          except Exception as e:
            traceback.print_exc(file=errfile)
            print(datetime.datetime.now(), "[BGMON fetching error]", type(e), e, file=errfile)
            ## return an empty array if something went wrong, and print the error just in case
            tx_status = []

          ## continue if there are no transactions
          if not tx_status:
            updatefile(errfile)
            continue

          for tx in tx_status:
            try:
              ## update transaction. we do it this way so we can send a signal for post_save
              tx_obj = Transaction.objects.get(app_transaction_id=tx.get('id'))
              if tx_obj.status != tx.get('state'):
                tx_obj.status = tx.get('state')
                tx_obj.save(update_fields=['status','updated_at'])
                print(datetime.datetime.now(), "[BGMON updated]", tx, file=errfile)
            except Exception as e:
              traceback.print_exc(file=errfile)
              print(datetime.datetime.now(), "[BGMON update error]", type(e), e, file=errfile)
            finally:
              updatefile(errfile)
          self.event.wait(1)

        self.event.wait(2)


class TransactionQueueDaemon(Thread):
  """Transaction Queue daemon is the controller of exchanges
  checks for transactions waiting to be exchanged and sends
  a batch, every n-time, to the Enjin endpoint.
  """
  def __init__(self):
    super(TransactionQueueDaemon, self).__init__()
    self.batch = []
    self.running = 1
    self.REQUIRED_STATUS = ('WAITING_FOR_EXCHANGE',)
    self.limit = 9
    self.event = Event()

  def run(self):
    self.event.set() ## set event to true for initial polling
    with open("TransactionMonitor.log", 'a') as errfile:
      print(datetime.datetime.now(), "DAEMON STARTED", file=errfile)
      updatefile(errfile)

      while self.running:
        #print(datetime.datetime.now(), "[TXMONITOR] top of the loop", file=errfile)
        if self.event.is_set():
          self.batch = list(Transaction.objects.filter(status__in=self.REQUIRED_STATUS, dirty=False).values_list('id',flat=True)[:self.limit])
          self.event.clear()
          #print(datetime.datetime.now(), "[TXMONITOR batch query]", len(self.batch), file=errfile)

        if not self.batch:
          self.event.wait(3600)
          continue

        with con.ThreadPoolExecutor(max_workers=self.limit) as executor:
          futures = []
          start = make_aware(datetime.datetime.now())
          start -= datetime.timedelta(microseconds=start.microsecond) ## round the time
          n = len(self.batch)
          check_latest_transactions = False

          while self.batch:
            futures.append(executor.submit(exchange_for_tokens, self.batch.pop()))

          for future in con.as_completed(futures):
            enj_tx = None
            try:
              enj_tx = future.result()
            except (ConnectTimeout, ConnectionError) as e:
              print(datetime.datetime.now(), "[TX MON ERROR]", type(e), e, file=errfile)
              traceback.print_exc(file=errfile)
              check_latest_transactions = True

            except TransportQueryError as e:
              print(datetime.datetime.now(), "[TX MON ERROR tqr]", e, file=errfile)
              traceback.print_exc(file=errfile)
              error = eval(str(e))
              if not error.get('code') in [422, 90001]:
                check_latest_transactions = True

            except CoolDownError as e:
              print(datetime.datetime.now(), "[TX MON ERROR cooldown]", e, file=errfile)

            except Exception as e:
              print(datetime.datetime.now(), "[TX MON ERROR] getting result", type(e), e, file=errfile)
              traceback.print_exc(file=errfile)
              check_latest_transactions = True

            else:
              print(datetime.datetime.now(), "[TX MON confirmed TX save]", enj_tx, file=errfile)

          ## mark the finish time of he loop
          end = make_aware(datetime.datetime.now())
          print(datetime.datetime.now(), "[FINISHED BATCH]", n, (end-start).total_seconds(), file=errfile)

          ## end of transactions requests loop. update log content
          updatefile(errfile)

          ## retrieve latest transactions (wait and repeat in case of failure)
          tx_list = None
          while check_latest_transactions:
            print("RETRIEVING LATEST TRANSACTIONS...")
            try:
              tx_list = get_latest_transactions()
            except Exception as e:
              print(datetime.datetime.now(), "[TX MON ERROR missing txs]", type(e), e, file=errfile)
              traceback.print_exc(file=errfile)
              self.event.wait(2)
            else:
              print("latest transactions retrieved")
              check_latest_transactions = False

          updatefile(errfile)
          ## end of transactions retrieving loop

          ## get our markers
          tx_ids_batch = list(Transaction.objects.exclude(app_transaction_id=-1).order_by('-id').values_list('app_transaction_id', flat=True)[:100])
          oldest_transaction = Transaction.objects.values().first()
          latest_suspect = SuspiciousTransaction.objects.values().last()
          sus_ids_batch = list(SuspiciousTransaction.objects.all().values_list('id', flat=True))

          while tx_list:
            t = tx_list.pop()
            t['createdAt'] = datetime.datetime.strptime(t['createdAt'], TTIME_FORMAT)

            ## we don't need to go further than the oldest transaction saved
            if oldest_transaction and t['createdAt'] < oldest_transaction['created_at']:
              break

            ## nor need to go further than the latest suspect found
            if latest_suspect and t['createdAt'] < latest_suspect['createdAt']:
              break

            ## we don't need what we already have linked
            if t['id'] in tx_ids_batch:
              continue

            ## we only save what we haven't saved
            if t['id'] not in sus_ids_batch:
              print("CHECKING", t['id'])
              ## add to Suspicious transactions list if not in the latest saved
              try:
                SuspiciousTransaction.objects.update_or_create(**t)
                print("[MSG] Suspicious transaction saved", t, file=errfile)
              except Exception as e:
                print("[ERROR] Failed to create this transaction", type(e), e, file=errfile)

          updatefile(errfile)
          ## general wait
          self.event.wait(2)

          tx = None
          if Transaction.objects.filter(status__in=self.REQUIRED_STATUS).count():
            self.event.set()


class ReservationLimboMon(Thread):
  """Reservation limbo will check the transactions again to see if anyone
  is missing an update to avoid missing items when transactions fail (forced release)
  """
  def __init__(self):
    super(ReservationLimboMon, self).__init__()
    self.running = 1
    self.wait_time = 30 # two minutes
    self.event = Event()
    self.DEFINITIVE_STATUS = ('CANCELED_USER',
                              'CANCELED_PLATFORM',
                              'DROPPED',
                              'FAILED',
                              'EXECUTED',
                              '',
                              'UNDER_REVISION',
                              'ERROR_ON_SUBMIT',
                              'FAILED_AT_RESERVATION',)

  def run(self):
    with open("InLimbo.log", 'a') as errfile:
      print(datetime.datetime.now(), "[LIMBO] starting", file=errfile)
      updatefile(errfile)
      while self.running:
        for t in Transaction.objects.filter(status__in=self.DEFINITIVE_STATUS, reservation_updated=False):
          try:
            t.save()
            print(datetime.datetime.now(), "[UPDATING RESERVATION STATUS]", t.id, file=errfile)
          except Exception as e:
            print(datetime.datetime.now(), "[LIMBO ERROR]", type(e), e, file=errfile)
            traceback.print_exc(file=errfile)
        updatefile(errfile)
        self.event.wait(self.wait_time)


class MarketReservationResync(Thread):
  """Resyncronize the remote and local reservations
  """
  def __init__(self):
    super(MarketReservationResync, self).__init__()
    self.running = 1
    self.wait_time = 5
    self.event = Event()

  def run(self):
    with open("MarketReservationResync.log", 'a') as errfile:
      print(datetime.datetime.now(), "[RESYNC] starting", file=errfile)
      updatefile(errfile)
      while self.running:
        for offer in MarketOffer.objects.filter(should_check_remote=True, offer_type=MarketOffer.TRADING):
          try:
            if offer.state in (offer.CANCELLED, offer.FAILED):
              action = 'RETURN'
            elif offer.state == offer.ACCEPTED:
              action = 'APPLY'
            else:
              raise Exception(f"nothing to do for {offer.id}")

            response = resync_market_reservation_in_pve(offer.id, offer.offer_type, action)
            if response.get('status'):
              data = response.get('data')
              print(response)
              if data.get('reservation_id') == -1:
                offer.state = offer.FAILED
              else:
                offer.pve_reservation_id = data.get('reservation_id')
                if offer.state == offer.ACCEPTED:
                  offer.state = offer.COMPLETED
              offer.should_check_remote = False
              offer.pve_reservation_updated = True

            offer.touched = False
            offer.save()
            print(datetime.datetime.now(), "[RESYNCING RESERVATION]", offer.id, file=errfile)
          except Exception as e:
            print(datetime.datetime.now(), "[RESYNC ERROR]", offer.id, type(e), e, file=errfile)
            traceback.print_exc(file=errfile)
        updatefile(errfile)
        self.event.wait(self.wait_time)


## transactions daemon
tx_mon = TransactionQueueDaemon()
tx_mon.daemon = True

## background status check daemon
bg_mon = BgMon()
bg_mon.daemon = True

## reservation limbo monitoring daemon
rs = ReservationLimboMon()
rs.daemon = True

## reservation limbo monitoring daemon
mk_sync = MarketReservationResync()
mk_sync.daemon = True


## monitors initializer
def start_mon(*mons):
  for mon in mons:
    mon.start()

