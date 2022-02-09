import json
import traceback
from os import getenv
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from mainsite.custom_auth import needs_user_auth
from django.conf import settings
from pycoingecko import CoinGeckoAPI
from datetime import datetime
import requests
from web3 import Web3
import time
import decimal
from mainsite.models import *

@needs_user_auth
def index(request):
    nick_name = request.session['name']
    if not OffchainCrownCredit.objects.filter(player_id=nick_name).exists():
        request.session.clear()
        return redirect('/')
    player_offchain_balance = OffchainCrownCredit.objects.get(player_id=nick_name)
    data = {}
    data['active_menu'] = 'crown'
    data['pool_wallet_addresss'] = settings.CONTRACT_POOL_WALLET_ADDRESS
    data['offchain_hrc_balance'] = player_offchain_balance.offchain_hrc_balance.normalize()
    data['offchain_erc_balance'] = player_offchain_balance.offchain_erc_balance.normalize()
    data['offchain_bsc_balance'] = player_offchain_balance.offchain_bsc_balance.normalize()
    data['withdraw_tax'] = float(settings.DEFAULT_TAX_PERCENT) * 100
    data['networks'] = [
        {'name': 'Harmony Network', 'value': 'hrc'},
        {'name': 'Binance Smart Chain', 'value': 'bsc'},
        {'name': 'Ethereum Network', 'value': 'erc'},
    ]
    return render(request, 'backend/user/crown/dashboard.html', data)

@csrf_exempt
@needs_user_auth
def get_binance_contract_data(request):
    result = {'result': 'error'}
    try:
        params = request.POST
        amount = float(params['amount'])
        chain_id = params['chain_id']
        if not check_binance_chain_by_id(chain_id):
            result['error_type'] = 'not_binance_chain'
            result['error_msg'] = "Please select one of Binance network via metamask and retry."
            return JsonResponse(result)

        crown_addr = Web3.toChecksumAddress(settings.BEP20_CROWN_ADDRESS)
        web3_http_provider = Web3(Web3.HTTPProvider(check_binance_chain_by_id(chain_id)['rpc_url']))
        contract = web3_http_provider.eth.contract(crown_addr, abi=settings.BEP20_CROWN_ABI)
        value = int(amount * pow(10, settings.BEP20_CROWN_DECIMALS))
        dest_address = Web3.toChecksumAddress(settings.CONTRACT_POOL_WALLET_ADDRESS)
        result['data'] = contract.functions.transfer(dest_address, value)._encode_transaction_data()
        # result['gas'] = hex(settings.CROWN_GAS_LIMIT)
        result['result'] = 'success'
        return JsonResponse(result)
    except Exception as e:
        print('get_crown_transfer_data: exception: ' + str(e))
        result['error_type'] = 'exception'
        result['error_msg'] = str(e)
        return JsonResponse(result)

@csrf_exempt
@needs_user_auth
def get_contract_data(request):
    result = {'result': 'error'}
    try:
        params = request.POST
        amount = float(params['amount'])
        chain_id = params['chain_id']
        if not check_harmony_chain_by_id(chain_id):
            result['error_type'] = 'not_harmony_chain'
            result['error_msg'] = "Please select one of Harmony network via metamask and retry."
            return JsonResponse(result)

        crown_addr = Web3.toChecksumAddress(settings.HRC20_CROWN_ADDRESS)
        web3_http_provider = Web3(Web3.HTTPProvider(check_harmony_chain_by_id(chain_id)['rpc_url']))
        contract = web3_http_provider.eth.contract(crown_addr, abi=settings.HRC20_CROWN_ABI)
        value = int(amount * pow(10, settings.HRC20_CROWN_DECIMALS))
        dest_address = Web3.toChecksumAddress(settings.CONTRACT_POOL_WALLET_ADDRESS)
        # result['gasPrice'] = get_gas_price()
        # if result['gasPrice'] == None:
        #     return HttpResponse(json.dumps(result))
        result['data'] = contract.functions.transfer(dest_address, value)._encode_transaction_data()
        # result['gas'] = hex(settings.CROWN_GAS_LIMIT)
        result['result'] = 'success'
        return JsonResponse(result)
    except Exception as e:
        print('get_crown_transfer_data: exception: ' + str(e))
        result['error_type'] = 'exception'
        result['error_msg'] = str(e)
        return JsonResponse(result)

@csrf_exempt
@needs_user_auth
def withdraw(request):
    result = {'result': 'error'}
    try:
        params = request.POST
        # check player's offchain balance
        nick_name = request.session['name']
        type = params['type']
        player_offchain_balance = OffchainCrownCredit.objects.get(player_id=nick_name)
        current_hrc_balance = player_offchain_balance.offchain_hrc_balance
        current_bsc_balance = player_offchain_balance.offchain_bsc_balance
        original_amount = float(params['amount'])
        if type == 'hrc' and current_hrc_balance < decimal.Decimal(original_amount):
            result['error_type'] = 'balance_not_enough'
            result['error_msg'] = "Your offchain balance isn't much enough to withdraw this amount"
            return JsonResponse(result)
        if type == 'bsc' and current_bsc_balance < decimal.Decimal(original_amount):
            result['error_type'] = 'balance_not_enough'
            result['error_msg'] = "Your offchain balance isn't much enough to withdraw this amount"
            return JsonResponse(result)
        player_address = params['player_account']
        chain_id = params['chain_id']

        # check player's current chain is harmony chain or not
        if type == 'hrc' and not check_harmony_chain_by_id(chain_id):
            result['error_type'] = 'not_harmony_chain'
            result['error_msg'] = "Please select one of Harmony network via metamask and retry."
            return JsonResponse(result)
        if type == 'bsc' and not check_binance_chain_by_id(chain_id):
            result['error_type'] = 'not_harmony_chain'
            result['error_msg'] = "Please select one of Binance Smart Chain network via metamask and retry."
            return JsonResponse(result)
        # initialize contract object
        amount = get_withdraw_amount(request, original_amount, type)

        if type == 'hrc':
            value = int(amount * pow(10, settings.HRC20_CROWN_DECIMALS))
            player_address = Web3.toChecksumAddress(player_address)
            crown_addr = Web3.toChecksumAddress(settings.HRC20_CROWN_ADDRESS)
            web3 = Web3(Web3.HTTPProvider(check_harmony_chain_by_id(chain_id)['rpc_url']))
            contract = web3.eth.contract(crown_addr, abi=settings.HRC20_CROWN_ABI)
            nonce = web3.eth.getTransactionCount(settings.CONTRACT_POOL_WALLET_ADDRESS)
            # build transaction
            gasprice = get_harmony_gas_price(check_harmony_chain_by_id(chain_id)['rpc_url'])
            txp = {"chainId": check_harmony_chain_by_id(chain_id)['chainid'], "nonce": nonce, "gas": settings.CROWN_GAS_LIMIT, "gasPrice": gasprice}
            txn = contract.functions.transfer(player_address, value).buildTransaction(txp)
        if type == 'bsc':
            value = int(amount * pow(10, settings.BEP20_CROWN_DECIMALS))
            player_address = Web3.toChecksumAddress(player_address)
            crown_addr = Web3.toChecksumAddress(settings.BEP20_CROWN_ADDRESS)
            web3 = Web3(Web3.HTTPProvider(check_binance_chain_by_id(chain_id)['rpc_url']))
            contract = web3.eth.contract(crown_addr, abi=settings.BEP20_CROWN_ABI)
            nonce = web3.eth.getTransactionCount(settings.CONTRACT_POOL_WALLET_ADDRESS)
            # build transaction
            gasprice = get_eth_gas_price_v2(check_binance_chain_by_id(chain_id)['rpc_url'])
            txp = {"chainId": check_binance_chain_by_id(chain_id)['chainid'], "nonce": nonce, "gas": settings.BEP20_CROWN_GAS_LIMIT, "gasPrice": gasprice}
            txn = contract.functions.transfer(player_address, value).buildTransaction(txp)

        # sign transaction and broadcast
        signed_txn = web3.eth.account.sign_transaction(txn, settings.CONTRACT_POOL_ACCOUNT_PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_receipt = web3.eth.wait_for_transaction_receipt(tx_hash, settings.LIMIT_WAIT_TIME)

        # ----- check if transaction is success ----- #
        if txn_receipt == None or 'status' not in txn_receipt or txn_receipt['status'] != 1 or 'transactionIndex' not in txn_receipt:
            result['error_type'] = 'transaction_error'
            result['error_msg'] = "Something went wrong."
            return JsonResponse(result)

        # deduct offchain balance
        if type == 'hrc':
            new_balance = current_hrc_balance - decimal.Decimal(original_amount)
            new_param = {}
            new_param['offchain_hrc_balance'] = new_balance
            for key, value in new_param.items():
                setattr(player_offchain_balance, key, value)
            player_offchain_balance.save()
        if type == 'bsc':
            new_balance = current_bsc_balance - decimal.Decimal(original_amount)
            new_param = {}
            new_param['offchain_bsc_balance'] = new_balance
            for key, value in new_param.items():
                setattr(player_offchain_balance, key, value)
            player_offchain_balance.save()

        # save transaction
        new_param = {}
        new_param['player'] = PlayerBase.objects.get(pk=nick_name)
        new_param['from_address'] = settings.CONTRACT_POOL_WALLET_ADDRESS
        new_param['to_address'] = player_address
        new_param['value'] = decimal.Decimal(amount)
        new_param['hash'] = tx_hash.hex()
        new_param['type'] = type
        txh_obj = TransactionHistory(**new_param)
        txh_obj.save()

        result['result'] = 'success'
        return JsonResponse(result)
    except Exception as e:
        result['error_type'] = 'exception'
        result['error_msg'] = str(e)
        return JsonResponse(result)

def get_rpc(chain_id):
    result = None
    for chain in settings.HARMONY_NETWORKS:
        if hex(chain['chainid']) == chain_id:
            result = chain
    return result


def check_harmony_chain_by_id(chain_id):
    result = False
    for chain in settings.HARMONY_NETWORKS:
        if hex(chain['chainid']) == chain_id:
            result = chain
    return result
def check_binance_chain_by_id(chain_id):
    result = False
    for chain in settings.BINANCE_NETWORKS:
        if hex(chain['chainid']) == chain_id:
            result = chain
    return result

def get_eth_gas_price_v2(rpc_url):
    web3_http_provider = Web3(Web3.HTTPProvider(rpc_url))
    res = requests.get(settings.CRONW_GAS_URL).json()
    gas_price = int(res[settings.CRONW_GAS_LEVEL] / 10)
    gas_price = int(web3_http_provider.toWei(gas_price, 'gwei'))
    return gas_price

def get_harmony_gas_price(rpc_url):
    data = {"jsonrpc": "2.0", "method": "hmy_gasPrice", "params": [], "id": 1}
    res = requests.post(rpc_url, json=data).json()
    return int(res['result'], 16)

def get_withdraw_amount(request, amount, type):
    tax_percent = float(settings.DEFAULT_TAX_PERCENT)
    if type == 'hrc':
        res = list(WithdrawTax.objects.filter(token_type='hrc').values())
        if len(res) == 1:
            tax_percent = float(res[0]['tax_percent'])
    if type == 'bsc':
        res = list(WithdrawTax.objects.filter(token_type='bep').values())
        if len(res) == 1:
            tax_percent = float(res[0]['tax_percent'])
    amount = amount * (1 - tax_percent)
    return amount

@csrf_exempt
@needs_user_auth
def record_transaction(request):
    payload = {'result': 'error'}
    try:
        params = request.POST
        txhash = params['txhash']
        chain_id = params['chain_id']
        type = params['type']
        if type == 'hrc':
            web3 = Web3(Web3.HTTPProvider(check_harmony_chain_by_id(chain_id)['rpc_url']))
        if type == 'bsc':
            web3 = Web3(Web3.HTTPProvider(check_binance_chain_by_id(chain_id)['rpc_url']))
        txn_receipt = web3.eth.wait_for_transaction_receipt(txhash, settings.LIMIT_WAIT_TIME)

        # ----- check if transaction is success ----- #
        if txn_receipt == None or 'status' not in txn_receipt or txn_receipt['status'] != 1 or 'transactionIndex' not in txn_receipt:
            payload['error_type'] = 'transaction_error'
            payload['error_msg'] = "Something went wrong."
            return JsonResponse(payload)

        from_address = params['from_address']
        d_am = params['d_am']
        nick_name = request.session['name']
        player_offchain_balance = OffchainCrownCredit.objects.get(player_id=nick_name)

        new_param = {}
        if type == 'hrc':
            current_balance = player_offchain_balance.offchain_hrc_balance
            new_balance = current_balance + decimal.Decimal(d_am)
            new_param['offchain_hrc_balance'] = new_balance
        if type == 'bsc':
            current_balance = player_offchain_balance.offchain_bsc_balance
            new_balance = current_balance + decimal.Decimal(d_am)
            new_param['offchain_bsc_balance'] = new_balance

        for key, value in new_param.items():
            setattr(player_offchain_balance, key, value)
        player_offchain_balance.save()

        new_param = {}
        new_param['player'] = PlayerBase.objects.get(pk=nick_name)
        new_param['from_address'] = from_address
        new_param['to_address'] = settings.CONTRACT_POOL_WALLET_ADDRESS
        new_param['value'] = decimal.Decimal(d_am)
        new_param['hash'] = txhash
        new_param['type'] = type
        txh_obj = TransactionHistory(**new_param)
        txh_obj.save()
        payload = {}
        payload['result'] = 'success'
        return JsonResponse(payload)
    except Exception as e:
        payload['error_type'] = 'exception'
        payload['error_msg'] = str(e)
        return JsonResponse(payload)