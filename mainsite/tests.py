from django.test import TestCase

# Create your tests here.

from . import enjin
#from pprint import pprint
#from .models import *
#from .player_api import *

#from time import sleep


# def queryUser(name):
#   query="""
#   query GetUser($name: String!) {
#     EnjinUser(name: $name) {
#       id
#       name
#       identities {
#         id
#         appId
#         wallet { ethAddress }
#       }
#     }
#   }"""
#
#   pprint(enjin.do_query(query, { 'name': name }))
#
# pprint(queryUser("RosieNante"))

# print("", "" ,"## check if there's stock",'- - '*10, sep="\n")
# enjin.check_stock("3000000000001056")

# print("", "" ,"## check wrong id",'- - '*10, sep="\n")
# enjin.check_stock("3000000000000000")


# print("", "" ,"## check existing user",'- - '*10, sep="\n")
# enjin.get_player_info(PlayerBase.objects.get(nick_name="RosieNante"))


# print("", "" ,"## check non-existing user",'- - '*10, sep="\n")
# enjin.get_player_info(PlayerBase.objects.get(nick_name="pp"))


# print("", "" ,"## mint FT for existing user",'- - '*10, sep="\n")
# enjin.mint_ft_tokens("3000000000001056", 1, PlayerBase.objects.get(nick_name="RosieNante"), True)


# print("", "" ,"## mint FT for non-existing user",'- - '*10, sep="\n")
# enjin.mint_ft_tokens("3000000000001056", 1, PlayerBase.objects.get(nick_name="pp"), True)


# print("", "" ,"## mint FT wrong ID",'- - '*10, sep="\n")
# enjin.mint_ft_tokens("3000000000000000", 1, PlayerBase.objects.get(nick_name="RosieNante"), True)


# print("", "" ,"## mint NFT for existing user",'- - '*10, sep="\n")
# enjin.mint_nft_tokens("388000000000086b", PlayerBase.objects.get(nick_name="RosieNante"), True)


# print("", "" ,"## mint NFT for non-existing user",'- - '*10, sep="\n")
# enjin.mint_nft_tokens("388000000000086b", PlayerBase.objects.get(nick_name="pp"), True)


# print("", "" ,"## mint NFT wrong ID",'- - '*10, sep="\n")
# enjin.mint_nft_tokens("3000000000000000", PlayerBase.objects.get(nick_name="RosieNante"), True)


# print("", "" ,"## mint NFT without reserves",'- - '*10, sep="\n")
# result = enjin.mint_nft_tokens("388000000000086b", PlayerBase.objects.get(nick_name="RosieNante"))


# if result.get('transaction'):
#   count = 5
#   tid = result['transaction']['id']
#   print("transaction id", tid)

#   while count:
#     count -= 1
#     print(enjin.check_transaction_status(tid))
#     sleep(1)


# print("## CHECKING EXISTING ITEM WITH ID")
# print(enjin.check_available_stock("3000000000001056"))

# print("## CHECKING NON-EXISTING ITEM WITH ID")
# print(enjin.check_available_stock("asd"))


# print("- - - - "*10,"\n"*2)
# response = enjin.transfer_token_from_reserve(1, '3080000000000877', PlayerBase.objects.get(nick_name='RosieNante'))
# print("\n"*2)
# print("[FT Transfer]", response)


#response = enjin.send_nft(1, '3080000000000877', "0000000000000002", 11542, "0x94CC0bb7263FCc5d35D044F6d2273420f4fC029D")
#print("[NFT Transfer]", response)


# player = PlayerBase.objects.get(nick_name='RosieNante')

# response = get_player_items(player)
# print("[RESPONSE]", response)

# for i in response['data']:
#   if i['item']['data_string_1'] == 'exchangeable':
#     item = i
#     break

# if response['status']:
#   response2 = get_player_single_item(player, item['id'])
#   print("[RESPONSE 2]", response2)

# try:
#   result = enjin.exchange_items(player, response2['data'], 1)
#   print("[RESULT]", result)
# except Exception as e:
#   print("[EXCEPTION]", e.args[0])


# tokens = enjin.get_player_tokens(PlayerBase.objects.get(nick_name='RosieNante'))
# print("[TOKENS]", tokens)

# tokens = enjin.get_player_tokens(PlayerBase.objects.get(nick_name='pp'))
# print("[TOKENS]", tokens)


#   if response2['status']:
#     response3 = reserve_item_for_exchange(player, 1, response2['data']['id'])
#     print("[RESPONSE 3]", response3)

#     if response3['status']:
#       reservation_id = response3['data']['reservation_id']
#       response4 = update_player_items(reservation_id, 'ROLLED_BACK')
#       print("[RESPONSE 4]", response4)
