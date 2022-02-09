import datetime
import traceback

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .custom_auth import *
from .models import Transaction, SuspiciousTransaction
from .enjin import get_single_tx_info


@needs_admin_auth
def transactions_for_revision(request):
  context = {}

  try:
    context['transactions'] = Transaction.objects.filter(status='UNDER_REVISION')
  except Exception as e:
    print("[TXs LIST]", type(e), e)
    traceback.print_exc()
    context['error'] = str(e)

  return render(request, 'backend/mgmt/transactions.html', context=context)


@csrf_exempt
@needs_admin_auth
def get_matching_suspects(request, id):
  context = { 'txid': id, 'suspects': [] }

  tx = Transaction.objects.get(pk=id)
  print(type(tx.transaction_time))

  tx_time = tx.transaction_time-tx.transaction_time.milisecond if tx.transaction_time == type(datetime.datetime) else tx.created_at
  context['suspects'] = SuspiciousTransaction.objects.filter(createdAt__gte=tx_time,
                                                             value=tx.q_tokens,
                                                             tokenId=tx.token_id,
                                                             related=False)

  return render(request, 'backend/mgmt/_suspects_partial.html', context=context)


@needs_admin_auth
def update_tx_match(request, id):
  if request.method == 'POST':
    try:
      tx = Transaction.objects.get(pk=id)
      sus_id = int(request.POST.get('suspect_id', 0))

      if not sus_id:
        raise Exception('No suspect id')

      if sus_id == -1:
        tx.status = 'FAILED'
      elif sus_id:
        sus = get_single_tx_info(sus_id)
        # update transaction
        tx.app_transaction_id = sus.get('id', tx.app_transaction_id)
        tx.eth_transaction_id = sus.get('transactionId', tx.eth_transaction_id)
        tx.status = sus.get('state', tx.status)
        # update suspicios record
        SuspiciousTransaction.objects.filter(id=sus_id).update(related=True)
      tx.save()
    except Exception as e:
      print("[UPDATE TX MATCH]", type(e), e)
      traceback.print_exc()

  return redirect(request.META.get('HTTP_REFERER'))