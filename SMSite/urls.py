"""SMSite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from mainsite import views
from mainsite import market_views as market
from mainsite import admin_tx_views as admin_tx
from mainsite import crown_view as crown
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.landpage),

    # dashboards
    # categories
    path('mgmt/market/categories/', views.admin_list_categories),
    path('mgmt/market/category/new/', views.admin_create_category),
    path('mgmt/market/category/update/<int:id>/', views.admin_update_category),
    path('mgmt/market/category/delete/<int:id>/', views.admin_delete_category),
    # products
    path('mgmt/market/products/', views.admin_list_products),
    path('mgmt/market/product/new/', views.admin_create_product),
    path('mgmt/market/product/update/<int:id>/', views.admin_update_product),
    path('mgmt/market/product/duplicate/<int:id>/',
         views.admin_duplicate_product),
    path('mgmt/market/product/delete/<int:id>/', views.admin_delete_product),
    path('mgmt/market/product/preview/<int:id>/', views.preview_product),
    path('api/products/export/', views.export_product),
    # tags
    path('mgmt/market/tags/', views.get_tags),
    path('mgmt/market/tag/new', views.create_tag),
    path('mgmt/market/tag/delete', views.delete_tag),
    # observer campaigns
    path('mgmt/campaigns/', views.admin_list_campaigns),
    path('mgmt/campaign/', views.admin_leaderboard),

    # transactions under revision
    path('mgmt/tx/revision/', admin_tx.transactions_for_revision),
    path('mgmt/tx/suspects/<int:id>/', admin_tx.get_matching_suspects),
    path('mgmt/tx/update/<int:id>/', admin_tx.update_tx_match),

    # signin
    path('mgmt/', views.admin_dashboard),
    path('mgmt/signin/', views.admin_dashboard_signin),

    # settings
    path('mgmt/site_settings/', views.site_settings),

    # order management
    path('mgmt/orders/', views.order_management),
    path('mgmt/orders/delete/<int:id>/', views.admin_delete_order),
    path('api/orders/delivery/', views.order_delivery),
    path('api/orders/confirmpayment/', views.order_payment_confirm),

    # news blog posts
    path('mgmt/blog/posts/', views.admin_list_posts),
    path('mgmt/blog/post/new/', views.admin_create_post),
    path('mgmt/blog/post/<int:id>/', views.admin_update_post),
    path('mgmt/blog/post/delete/<int:id>/', views.admin_delete_post),

    path('mgmt/blog/preview/<int:id>/', views.preview_blog),

    # shop
    path('shop/', views.shop),
    path('shop/product/<int:id>/', views.product),
    path('shop/cartitems/add', views.add_cart_items),
    path('shop/cartitems/view/', views.list_cart_items),
    path('api/cartitems/delete/', views.delete_cart_item),
    path('api/cartitems/get/', views.get_cart_items),
    path('api/getProductCountByCustomer/', views.get_product_count_by_customer),

    # checkout
    path('checkout/', views.checkout),

    # blog
    path('news/', views.blog),
    path('news/<str:slug>/', views.blog),

    # user dashboard
    path('user/', views.user_dashboard),
    #    path('user/items/regroup/', market.regroup_stacks),
    path('user/refresh/wallet/', views.refresh_wallet),
    path('user/update/email/', views.user_update_email),
    path('user/update/password/', views.user_update_password),
    # trading
    path('user/trading/', market.trading_main_view, name="trading_main_view"),
    path('user/trading/makeoffer/', market.trading_make_offer),
    path('user/trading/<str:offer_uuid>/',
         market.trading_view_offer, name="trading_view_offer"),
    path('user/trading/<str:offer_uuid>/closed/',
         market.trading_view_offer_closed, name="trading_view_offer_closed"),
    path('user/trading/<str:offer_uuid>/update/', market.trading_update_offer),
    path('user/trading/<str:offer_uuid>/submit/', market.trading_submit),
    path('user/trading/<str:offer_uuid>/resolve/', market.trading_offer_resolve),
    path('user/trading/<str:offer_uuid>/cancel/', market.cancel_trading),
    path('user/search/', market.search_users),
    # market
    path('user/market/', market.market_main_view, name="market_main_view"),
    path('user/market/cancel/', market.cancel_market_sale,
         name="cancel_market_sale"),
    path('user/market/history/', market.market_purchase_history,
         name="market_purchase_history"),
    path('user/market/create/sell/',
         market.market_create_selling_offer, name="market_create_sell"),
    path('user/market/purchase/<str:uid>/',
         market.market_purchase_v2, name="market_purchase"),

    # exchange
    path('user/items/', views.items_list),
    path('user/exchange/item/<int:item_batch_id>/', views.exchange_item_info),
    path('user/tokens/', views.tokens_list),
    path('user/transactions/queue/', views.transactions_queue),
    path('queue/status/', views.queue_status),
    # team
    path('mgmt/team/members/', views.admin_list_team_member),
    path('mgmt/team/member/new/', views.admin_add_team_member),
    path('mgmt/team/member/<int:id>/', views.admin_update_team_member),
    path('mgmt/team/member/delete/<int:id>/', views.admin_delete_team_member),

    path('team/members/', views.team_members),

    ## tutorial (admin)
    path('mgmt/tutorial/tutorials/', views.admin_list_tutorials),
    path('mgmt/tutorial/new/', views.admin_create_tutorial),
    path('mgmt/tutorial/<int:id>/', views.admin_update_tutorial),
    path('mgmt/tutorial/delete/<int:id>/', views.admin_delete_tutorial),

    # tutorial
    path('tutorial/', views.tutorial),

    # download
    path('download/', views.download),

    # users
    path('mgmt/users/', views.admin_list_users),

    # subscription
    path('subscription/', views.subscription),

    # authentication
    path('signin/', views.signin),
    path('signup/', views.signup),
    path('2fa/', views.tfa),
    path('2fa/email/', views.tfa_email),
    #    path('signup/', views.signup_testing),
    path('signout/', views.signout),

    # email confirmation
    path('confirm/<str:token>/', views.confirm_email),

    # password recovery and reset
    path('recovery/', views.password_recovery),
    path('reset/<str:token>/', views.password_reset),

    # public
    path('leaderboard/<int:id>/', views.leaderboard),
    path('b/leaderboard/', views.summary_leaderboard),

    path('api/checkout-crypto-session/<uid>/',
         views.create_checkout_crypto_session),
    path('api/checkout-stripe-session/<uid>/',
         views.create_checkout_stripe_session),
    path('payment-success/', views.payment_success),
    path('payment-failed/', views.payment_failed),

    # static files on development
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),

    # crown deposti/withdraw/
    path('user/crown/', crown.index),
    path('user/get_contract_data/', crown.get_contract_data),
    path('user/record_transaction/', crown.record_transaction),
    path('user/withdraw/', crown.withdraw),
    path('user/get_binance_contract_data/', crown.get_binance_contract_data)
]
