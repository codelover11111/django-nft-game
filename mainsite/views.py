import re
from os import getenv
from random import sample

from django.views.decorators.csrf import csrf_exempt

from .custom_auth import _notify_ban
from .templatetags.local_date import to_utc
from django.contrib.auth.hashers import check_password
from django.http import HttpResponseNotFound, JsonResponse
from django.utils.text import slugify
import stripe
from django.shortcuts import get_object_or_404, render

from django.conf import settings

from mailchimp_marketing import Client
from mailchimp_marketing.api_client import ApiClientError

from .process import *
from .custom_auth import *
from .models import *
from .player_api import *
from .enjin import *
import csv
import decimal
import pyotp
import time

ZTIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# DASHBOARDS
# admin
@needs_admin_auth
def admin_dashboard(request):
    return render(request, 'backend/mgmt/main.html')


def admin_dashboard_signin(request):
    if request.session.get('id', False) and request.session.get('is_admin', False):
        return redirect('/mgmt/')

    error = None

    if request.method == "POST":
        usr = request.POST.get("user", None)
        pwd = request.POST.get("pass", None)

        if usr and pwd:
            try:
                user = Manager.objects.get(username=usr)
                if not check_password(pwd, user.password):
                    raise
            except Exception:
                user = None
                error = 'Wrong user or passsword'

            if user:
                request.session.set_expiry(48 * 60 * 60)
                request.session['id'] = user.id
                request.session['name'] = user.username
                request.session['email'] = user.email
                request.session['is_admin'] = True

                return redirect('/mgmt/')
        else:
            error = "User and Password are mandatory"

    return render(request, 'backend/mgmt/signin.html', {"error_message": error})


@needs_admin_auth
def admin_list_campaigns(request):
    data = api_get('admin/campaigns/')
    context = {}

    if data.get('error'):
        context['error_message'] = data.get('error')

    context['campaigns'] = data.pop('campaigns')
    return render(request, 'backend/mgmt/campaigns.html', context)


@needs_admin_auth
def admin_leaderboard(request):
    data = api_get('admin/leaderboard/', id=request.GET.get('id'))
    context = {}

    if data.get('error'):
        context['error_message'] = data.get('error')

    context['campaign'] = data.pop('campaign')

    # retrieve players nicknames
    nicks = [_['nick'] for _ in context['campaign']['leaderboard']]

    # retrieve emails for users
    emails = {}
    for entry in PlayerBase.objects.filter(nick_name__in=nicks).values('nick_name', 'email'):
        emails[entry['nick_name']] = entry['email']

    # append emails to players' info
    for player in context['campaign']['leaderboard']:
        player['email'] = emails.get(player['nick'], '')

    context['campaign']['start'] = make_aware(
        datetime.datetime.strptime(context['campaign']['start'], ZTIME_FORMAT))
    if context['campaign'].get('end'):
        context['campaign']['end'] = make_aware(
            datetime.datetime.strptime(context['campaign']['end'], ZTIME_FORMAT))

    return render(request, 'backend/mgmt/leaderboard.html', context)


# admin blog
@needs_admin_auth
def admin_list_posts(request):
    posts = BlogPost.objects.all()

    return render(request, 'backend/mgmt/blog/posts.html', {"posts": posts})


@needs_admin_auth
def admin_create_post(request):
    context = {}

    if request.method == 'POST':
        slug = request.POST.get('slug', '')

        if not len(slug):
            slug = slugify(request.POST.get('title', ''))

        author = Manager.objects.get(id=request.session.get('id', None))

        post = BlogPost(
            title=request.POST.get('title'),
            content=request.POST.get('content', ''),
            slug=slug[:32],
            author=author,
            cover=request.FILES.get('cover', None),
            preview=request.FILES.get('preview', None),
        )

        try:
            post.save()
            return redirect('/mgmt/blog/posts/')
        except Exception as e:
            context['error'] = str(e)

    return render(request, 'backend/mgmt/blog/new_post.html', context)


@needs_admin_auth
def admin_update_post(request, id):
    context = {}

    try:
        context['post'] = BlogPost.objects.get(id=id)

        if request.method == 'POST':
            # ensure slug
            slug = request.POST.get('slug', '')[:32]

            if not len(slug):
                slug = slugify(request.POST.get('title', ''))

            if request.POST.get('title') != context['post'].title:
                context['post'].title = request.POST.get('title')

            if request.POST.get('content') != context['post'].content:
                context['post'].content = request.POST.get('content', '')

            if slug != context['post'].slug:
                context['post'].slug = slug

            if request.FILES.get('cover'):
                context['post'].cover = request.FILES.get('cover')

            if request.FILES.get('preview'):
                context['post'].preview = request.FILES.get('preview')

            context['post'].save()

            context['success'] = 'Post is updated successfully!'
    except Exception as e:
        context['error'] = str(e)
        # raise e

    return render(request, 'backend/mgmt/blog/update_post.html', context)


@needs_admin_auth
def admin_delete_post(request, id):
    try:
        obj = BlogPost.objects.get(id=id)

        if request.method == 'GET':
            obj.delete()

    except Exception as e:
        raise e

    return redirect("/mgmt/blog/posts/")


@needs_admin_auth
def preview_blog(request, id):
    posts = BlogPost.objects.all()
    by_date = {}

    post = BlogPost.objects.get(id=id)

    # append posts sorted by year
    for a_post in posts:
        if by_date.get(post.created_at.year, False):
            by_date[a_post.created_at.year]['titles'].append(a_post)
            by_date[a_post.created_at.year]['count'] += 1
        else:
            by_date[a_post.created_at.year] = {'count': 1, 'titles': [a_post]}

    return render(request, 'frontend/blog/main.html', {'post': post, 'by_date': by_date})


@needs_admin_auth
def admin_list_team_member(request):
    team = Team.objects.all()

    return render(request, 'backend/mgmt/team/members.html', {"team": team})


@needs_admin_auth
def admin_add_team_member(request):
    context = {}

    if request.method == 'POST':
        member = Team(
            name=request.POST.get('name'),
            role=request.POST.get('role', ''),
            position=request.POST.get('position', 1),
            image=request.FILES.get('image', None),
        )

        try:
            member.save()
            return redirect('/mgmt/team/members/')
        except Exception as e:
            context['error'] = str(e)

    return render(request, 'backend/mgmt/team/new_member.html', context)


@needs_admin_auth
def admin_update_team_member(request, id):
    context = {}

    try:
        context['member'] = Team.objects.get(id=id)

        if request.method == 'POST':
            if request.POST.get('name') != context['member'].name:
                context['member'].name = request.POST.get('name')

            if request.POST.get('role') != context['member'].role:
                context['member'].role = request.POST.get('role')

            if request.POST.get('position') != context['member'].position:
                context['member'].position = request.POST.get('position')

            if request.FILES.get('image'):
                context['member'].image = request.FILES.get('image')

            context['member'].save()

            context['success'] = 'Member is updated successfully!'
    except Exception as e:
        raise e
        context['error'] = str(e)

    return render(request, 'backend/mgmt/team/update_member.html', context)


@needs_admin_auth
def admin_delete_team_member(request, id):
    try:
        obj = Team.objects.get(id=id)

        if request.method == 'GET':
            obj.delete()

    except Exception as e:
        raise e

    return redirect("/mgmt/team/members")


def team_members(request):
    try:
        members = Team.objects.all().order_by('position', 'created_at')
    except Exception as e:
        members = []

    return render(request, 'frontend/team/main.html', {'members': members})


@needs_admin_auth
def admin_list_tutorials(request):
    tutorials = Tutorial.objects.all()

    return render(request, 'backend/mgmt/tutorial/tutorials.html', {"tutorials": tutorials})


@needs_admin_auth
def admin_create_tutorial(request):
    context = {}

    if request.method == 'POST':
        tutorial = Tutorial(
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            length=request.POST.get('length', ''),
            poster=request.FILES.get('poster', None),
            video=request.FILES.get('video', None),
        )

        try:
            tutorial.save()
            return redirect('/mgmt/tutorial/tutorials/')
        except Exception as e:
            context['error'] = str(e)

    return render(request, 'backend/mgmt/tutorial/new_tutorial.html', context)


@needs_admin_auth
def admin_update_tutorial(request, id):
    context = {}

    try:
        context['tutorial'] = Tutorial.objects.get(id=id)

        if request.method == 'POST':
            if request.POST.get('title') != context['tutorial'].title:
                context['tutorial'].title = request.POST.get('title')

            if request.POST.get('description') != context['tutorial'].description:
                context['tutorial'].description = request.POST.get(
                    'description')

            if request.POST.get('length') != context['tutorial'].length:
                context['tutorial'].length = request.POST.get('length')

            if request.FILES.get('poster'):
                context['tutorial'].poster = request.FILES.get('poster')

            if request.FILES.get('video'):
                context['tutorial'].video = request.FILES.get('video')

            context['tutorial'].save()

            context['success'] = 'Tutorial is updated successfully!'
    except Exception as e:
        raise e
        context['error'] = str(e)

    return render(request, 'backend/mgmt/tutorial/update_tutorial.html', context)


@needs_admin_auth
def admin_delete_tutorial(request, id):
    try:
        obj = Tutorial.objects.get(id=id)

        if request.method == 'GET':
            obj.delete()

    except Exception as e:
        raise e

    return redirect("/mgmt/tutorial/tutorials")


def tutorial(request):
    try:
        tutorials = Tutorial.objects.all()
    except Exception as e:
        tutorials = []

    return render(request, 'frontend/tutorial/main.html', {'tutorials': tutorials, 'active_menu': 'tutorial'})


def download(request):
    download_link = Settings.objects.latest('id').download_link

    return render(request, 'frontend/download/main.html', {'download_link': download_link, 'active_menu': 'download'})


@needs_admin_auth
def site_settings(request):
    try:
        context = {'settings': Settings.objects.latest('id')}
    except Exception as e:
        settings = Settings()
        settings.save()
        context = {'settings': settings}

    if request.method == "POST":
        try:
            data = {**request.POST}
            data.pop('csrfmiddlewaretoken')
            data.pop('video_thumbnail')  # avoid overwriting on update

            for key in data:
                data[key] = data[key].pop()

            # update all elements on the model
            result = Settings.objects.filter(
                id=context['settings'].id).update(**data)

            if request.FILES.get('video_thumbnail', None):
                context['settings'].video_thumbnail = request.FILES.get(
                    'video_thumbnail', None)
                context['settings'].save()

            context['settings'].refresh_from_db()
            context['success_message'] = 'Settings updated successfully!'
        except Exception as e:
            context['error_message'] = str(e)

    return render(request, 'backend/mgmt/site_settings.html', context)


# admin product

@needs_admin_auth
def admin_list_products(request):
    products = Products.objects.all()
    return render(request, 'backend/mgmt/product/products.html', {"products": products})


@needs_admin_auth
def admin_create_product(request):
    context = {"status": Products.STATUS}
    context['categories'] = Categories.objects.all()
    if request.method == 'POST':
        category = Categories.objects.get(id=request.POST.get('category'))
        product = Products(
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            price=request.POST.get('price'),
            put_quantity=request.POST.get('put_quantity'),
            limit_quantity=request.POST.get('limit_quantity'),
            is_limit=request.POST.get('is_limit'),
            image=request.FILES.get('image', None),
            category=category,
            status=request.POST.get('status'),
            attributes=request.POST.get('attributes'),
            pi_title=request.POST.get('pi_title'),
            pi_description=request.POST.get('pi_description', ''),
        )

        try:
            product.save()
            return redirect('/mgmt/market/products/')
        except Exception as e:
            context['error'] = str(e)

    return render(request, 'backend/mgmt/product/new_product.html', context)


@needs_admin_auth
def admin_update_product(request, id):
    context = {
        'status': Products.STATUS,
        'categories': Categories.objects.all()
    }

    try:
        context['product'] = Products.objects.get(id=id)

        if request.method == 'POST':

            if request.POST.get('title') != context['product'].title:
                context['product'].title = request.POST.get('title')

            if request.POST.get('description') != context['product'].description:
                context['product'].description = request.POST.get(
                    'description', '')

            if request.FILES.get('image'):
                context['product'].image = request.FILES.get('image')

            if Categories.objects.get(id=request.POST.get('category', 0)) != context['product'].category:
                context['product'].category = Categories.objects.get(
                    id=request.POST.get('category', 0))

            if request.POST.get('price') != context['product'].price:
                context['product'].price = request.POST.get('price')

            if request.POST.get('put_quantity') != context['product'].put_quantity:
                context['product'].put_quantity = request.POST.get(
                    'put_quantity')

            if request.POST.get('limit_quantity') != context['product'].limit_quantity:
                context['product'].limit_quantity = request.POST.get(
                    'limit_quantity')

            if int(request.POST.get('is_limit', 0)) != context['product'].is_limit:
                context['product'].is_limit = request.POST.get('is_limit')

            if int(request.POST.get('status', 0)) != context['product'].status:
                context['product'].status = request.POST.get('status')

            if request.POST.get('attributes') != context['product'].attributes:
                context['product'].attributes = request.POST.get('attributes')

            if request.POST.get('pi_title') != context['product'].pi_title:
                context['product'].pi_title = request.POST.get('pi_title')

            if request.POST.get('pi_description') != context['product'].pi_description:
                context['product'].pi_description = request.POST.get(
                    'pi_description', '')

            context['product'].save()

            context['success'] = 'Product updated successfully!'
    except Exception as e:
        raise e
        context['error'] = str(e)

    return render(request, 'backend/mgmt/product/update_product.html', context)


@needs_admin_auth
def admin_duplicate_product(request, id):
    context = {
        'status': Products.STATUS,
        'categories': Categories.objects.all()
    }

    try:
        context['product'] = Products.objects.get(id=id)

        if request.method == 'POST':
            category = Categories.objects.get(
                id=request.POST.get('category', 0))
            product = Products(
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                price=request.POST.get('price'),
                put_quantity=request.POST.get('put_quantity'),
                limit_quantity=request.POST.get('limit_quantity'),
                is_limit=request.POST.get('is_limit'),
                image=request.FILES.get('image', None) if request.FILES.get(
                    'image') else context['product'].image,
                category=category,
                status=request.POST.get('status'),
                attributes=request.POST.get('attributes'),
                pi_title=request.POST.get('pi_title'),
                pi_description=request.POST.get('pi_description', ''),
            )

            product.save()

            context['success'] = 'Product duplicated successfully!'
    except Exception as e:
        raise e
        context['error'] = str(e)

    return render(request, 'backend/mgmt/product/duplicate_product.html', context)


@needs_admin_auth
def admin_delete_product(request, id):
    try:
        obj = Products.objects.get(id=id)

        if request.method == 'GET':
            obj.delete()

    except Exception as e:
        raise e

    return redirect('/mgmt/market/products/')


@needs_admin_auth
def preview_product(request, id):
    product = Products.objects.get(id=id)
    return render(request, 'landpage/product.html', {'product': product, 'active_menu': 'shop'})


# admin category
@needs_admin_auth
def admin_list_categories(request):
    categories = Categories.objects.all()
    return render(request, 'backend/mgmt/category/categories.html', {"categories": categories})


@needs_admin_auth
def admin_create_category(request):
    context = {"categories": Categories.objects.all()}

    if request.method == 'POST':
        slug = request.POST.get('slug', '')

        if not len(slug):
            slug = slugify(request.POST.get('name', ''))

        parent = request.POST.get('parent', '')

        if not len(parent):
            category = Categories(
                name=request.POST.get('name'),
                icon=request.FILES.get('icon', None),
                slug=slug[:32]
            )
        else:
            category = Categories(
                name=request.POST.get('name'),
                slug=slug[:32],
                parent=Categories.objects.get(id=parent)
            )
        try:
            category.save()
            return redirect('/mgmt/market/categories/')
        except Exception as e:
            context['error'] = str(e)

    return render(request, 'backend/mgmt/category/new_category.html', context)


@needs_admin_auth
def admin_update_category(request, id):
    context = {
        'categories': Categories.objects.all()
    }

    try:
        context['category'] = Categories.objects.get(id=id)

        if request.method == 'POST':
            slug = request.POST.get('slug', '')[:32]
            parent = request.POST.get('parent', '')

            if not len(slug):
                slug = slugify(request.POST.get('name', ''))

            if request.POST.get('name') != context['category'].name:
                context['category'].name = request.POST.get('name')

            if slug != context['category'].slug:
                context['category'].slug = slug

            if request.FILES.get('icon'):
                context['category'].icon = request.FILES.get('icon')

            if parent != context['category'].parent:
                if len(parent):
                    context['category'].parent = Categories.objects.get(
                        id=parent)

            context['category'].save()

            context['success'] = 'Category updated successfully!'
    except Exception as e:
        raise e
        context['error'] = str(e)

    return render(request, 'backend/mgmt/category/update_category.html', context)


@needs_admin_auth
def admin_delete_category(request, id):
    try:
        obj = Categories.objects.get(id=id)

        if request.method == 'GET':
            obj.delete()
            # obj.objects.rebuild()

    except Exception as e:
        raise e

    return redirect('/mgmt/market/categories/')


@needs_admin_auth
def get_tags(request):
    return render(request, 'frontend/landpage/main.html')


@needs_admin_auth
def create_tag(request):
    return render(request, 'frontend/landpage/main.html')


@needs_admin_auth
def delete_tag(request):
    return render(request, 'frontend/landpage/main.html')


# admin order management
@needs_admin_auth
def order_management(request):
    orders = OrderDetail.objects.filter(is_delete=0)
    return render(request, 'backend/mgmt/orders.html', {"orders": orders})


@needs_admin_auth
def admin_delete_order(request, id):
    try:
        obj = OrderDetail.objects.get(id=id)

        if request.method == 'GET':
            obj.is_delete = 1
            obj.save()

    except Exception as e:
        raise e

    return redirect('/mgmt/orders/')


def order_delivery(request, *args, **kwargs):
    if request.method == 'POST':
        request_data = json.loads(request.body)
        order = OrderDetail.objects.get(id=request_data['order_id'])
        order.has_delivered = 1
        order.save()

        player = PlayerBase.objects.get(email=order.customer_email)

        cartItems = CartItem.objects.filter(cart_id=order.cart_id)

        order_detail = f"""
    """
        total_order_price = 0
        for cartItem in cartItems:
            product = Products.objects.get(id=cartItem.product_id)
            product.out_quantity = product.out_quantity + cartItem.quantity
            product.save()

            total_price = cartItem.quantity * cartItem.price
            total_order_price += total_price
            order_detail += f"""
      {cartItem.product.title}  |  {cartItem.quantity}  |  ${cartItem.price}  |  ${total_price}
      """

        subject = "[Space Misfits] Your order has been delivered!"
        message = f"""
    Thank you for your order and your support!

    We are letting you know that we have delivered your order to your provided ENJIN address.

    You have ordered:

    Product  |  Quantity  |  Price |  Total Price
    ---------------------------------------------

    {order_detail}

    ---------------------------------------------
                                    Total : ${total_order_price}
    
    """
        mail_result = send_email_to_user(player, subject, message)

        return JsonResponse({'status': 1})


def order_payment_confirm(request, *args, **kwargs):
    if request.method == 'POST':
        request_data = json.loads(request.body)
        order = OrderDetail.objects.get(id=request_data['order_id'])
        order.has_paid = 1
        order.save()
        return JsonResponse({'status': 1})


# - - - - - - -
# user
# - - - - - - -
@needs_user_auth
def user_dashboard(request):
    player = PlayerBase.objects.get(nick_name=request.session["name"])
    if player.emailconfirmationrequest_set.count():
        confirmation = player.emailconfirmationrequest_set.latest('created_at')
    else:
        confirmation = False

    context = {
        "player": player,
        "email_confirmed": confirmation and confirmation.confirmed,
        "pass_error": request.session.pop("password_error", None),
        "email_error": request.session.pop("email_error", None),
        "refresh_error": request.session.pop("refresh_error", None),
        "active_menu": "settings",
    }

    return render(request, 'backend/user/settings.html', context)


@needs_user_auth
def user_update_password(request):
    pwd1 = request.POST.get("password")
    pwd2 = request.POST.get("password_confirmation")

    if not pwd1 or len(pwd1) < 8:
        request.session["password_error"] = "Password must be at least 8 characters long"
        return redirect("/user/")

    if not re.match(r"^[a-zA-Z0-9_]*$", pwd1):
        request.session["password_error"] = "Password cannot contain special characters"
        return redirect("/user/")

    if pwd1 != pwd2:
        request.session["password_error"] = "Confirmation doesn't match"
        return redirect("/user/")

    result = pve_password_reset(request.session["name"], pwd1)

    if result != "OK":
        request.session["password_error"] = result
    else:
        request.session["password_error"] = "Password updated correctly"

    return redirect("/user/")


@needs_user_auth
def user_update_email(request):
    email = request.POST.get('email')
    if not email:
        request.session["email_error"] = "Email cannot be empty"
        return redirect("/user/")

    if PlayerBase.objects.filter(email=email).exists():
        request.session["email_error"] = "Email already used"
        return redirect("/user/")

    # if everything went well update the email address
    player = PlayerBase.objects.get(nick_name=request.session["name"])
    player.email = email
    player.save()

    try:
        error = send_email_confirmation(player)
        if error == "OK":
            request.session["email_error"] = "A confirmation link has been sent to the new address"
        else:
            request.session["email_error"] = error
    except Exception as e:
        request.session["email_error"] = str(e)

    return redirect("/user/")


@needs_user_auth
@protected(protections=('short time', 'no referer'))
def refresh_wallet(request, bl):
    try:
        player = PlayerBase.objects.get(pk=request.session["name"])
        get_player_info(player, True)
    except Exception as e:
        request.session['refresh_error'] = str(e)

    return redirect("/user/")


# exchange
@needs_user_auth
def items_list(request):
    context = {'active_menu': 'items'}

    try:
        inventory_check = check_player_has_inventory(request.session["name"])
        print(inventory_check)

        if not inventory_check["status"]:
            raise Exception(inventory_check["error"])

        context["has_inventory"] = inventory_check.get("data", False)

        player = PlayerBase.objects.get(nick_name=request.session["name"])
        response = get_player_items(player)

        if not response.get('status'):
            raise Exception(response.get('error', 'Unknown error'))

        context.update({
            'items': response.get("data"),
            'bits': int(response.get("bits")),
            'player': player
        })
    except Exception as e:
        context['error_message'] = str(e)

    return render(request, 'backend/user/exchange/items.html', context)


@needs_user_auth
@protected(protections=('short time', 'no referer',))
def exchange_item_info(request, item_batch_id, bl):
    context = {'has_wallet': -1, 'active_menu': 'items'}
    item_in_wallet = {}
    player = None
    token = None
    transaction = None

    try:
        player = PlayerBase.objects.get(nick_name=request.session["name"])
        if not player.can_exchange:
            redirect('/user/')

        # check if player has a linked wallet
        link_check = check_player_enj_wallet(player)
        if not link_check.get('status'):
            raise Exception(link_check.get('error'))

        # get item information from the server
        item_res = get_player_single_item(player, item_batch_id)
        if not item_res.get('status'):
            raise Exception(item_res.get('error'))

        # check item in wallet is exchangeable
        item_in_wallet = item_res['data']
        if not 'exchange' in item_in_wallet['item']['tokens_metadata']['permissions']:
            raise Exception('Item is not exchangeable')

        if not item_in_wallet['item']['tokens_metadata']['tokens']:
            raise Exception(
                'Item does not have an exchangeable token configured')

        # pick a random (or THE only) token information
        # comma after variable unpacks the array element
        item_token_id, = sample(
            item_in_wallet['item']['tokens_metadata']['tokens'], 1)

        if not item_token_id:
            raise Exception(
                'Item does not have an exchangeable token configured')

        token = get_token_info(item_token_id)

        # set context variables for the template
        context['item'] = item_in_wallet
        context['token'] = {
            'id': token.id,
            'name': token.name,
            'metadata': json.loads(token.metadata) if token.metadata else {},
            'nonFungible': token.nonFungible,
        }
        context['has_wallet'] = int(link_check.get('has_wallet', False))
    except TransportQueryError as e:
        traceback.print_exc()
        context['error_message'] = eval(str(e))['message']
    except Exception as e:
        traceback.print_exc()
        context['error_message'] = str(e)
        return render(request, 'backend/user/exchange/item.html', context)

    if request.method == 'POST':
        try:
            if int(request.POST.get('tokens_quantity', 0)) > context['item'].get('amount', 0):
                bl.auto_ban("Trying to exchange more items than available")
                return _notify_ban(bl)

            if int(request.POST.get('tokens_quantity', 0)) > 0:
                if int(request.POST['tokens_quantity']) > 100:
                    raise Exception(
                        "Cannot exchange more than 100 items at a time")

                q_tokens = int(request.POST['tokens_quantity'])
                q_items = q_tokens * \
                    int(float(
                        item_in_wallet['item']['tokens_metadata']['items_per_token']))

                if q_items > item_in_wallet.get('amount', 0):
                    raise Exception("Not enough items to exchange")

                # create transaction record
                transaction = Transaction(
                    player=player, action='ITEM EXCHANGE')
                # item info
                transaction.item_id = item_in_wallet['item']['id']
                transaction.item_name = item_in_wallet['item']['name']
                transaction.q_items = q_items
                # token info
                transaction.token_id = token.id
                transaction.token_name = token.name
                transaction.q_tokens = q_tokens
                transaction.nft = token.nonFungible

                transaction.save()
                transaction.refresh_from_db()
                # item reservation process
                result = reserve_item_for_exchange(
                    player, q_items, item_batch_id, transaction.id)

                if result.get('status'):
                    transaction.reservation_id = result['data']['reservation_id']
                    transaction.item_batch_id = item_batch_id
                    transaction.status = 'WAITING_FOR_EXCHANGE'
                    transaction.save()
                else:
                    transaction.status = 'FAILED_AT_RESERVATION'
                    transaction.save()
                    raise Exception(result.get('error', 'UNKNOWN ERROR'))

                context['success_message'] = "Your exchange request has been added to the queue"

                # refresh item data
                item_res = get_player_single_item(player, item_batch_id)
                if not item_res.get('status'):
                    context['item'] = None
                    context['token'] = None
                    raise Exception(item_res.get('error'))

                # update item content
                context['item'] = item_res['data']
            else:
                raise Exception(
                    "Tokens amount to exchange must be greater than zero")

        except TransportQueryError as e:
            traceback.print_exc()
            # roll back reservation if something happened with the transaction
            if transaction:
                transaction.status = 'FAILED'
                transaction.save()
            context['error_message'] = eval(str(e))['message']
        except Exception as e:
            traceback.print_exc()
            context['error_message'] = str(e)

    return render(request, 'backend/user/exchange/item.html', context)


@csrf_exempt
@needs_user_auth
def queue_status(request):
    response = {'status': 0}
    t_checkpoint = make_aware(
        datetime.datetime.now() - datetime.timedelta(seconds=3))

    try:
        player = PlayerBase.objects.get(pk=request.session['name'])
        transactions = list(player.transaction_set.filter(
            updated_at__gt=t_checkpoint).values('id', 'status', 'updated_at'))
    except Exception as e:
        response['error'] = str(e)
    else:
        response['data'] = []

        for tx in transactions:
            tx['updated_at'] = to_utc(tx['updated_at'])
            response['data'].append(tx)

        response['status'] = 1

    return JsonResponse(response)


@needs_user_auth
def tokens_list(request):
    context = {'active_menu': 'assets'}

    try:
        player = PlayerBase.objects.get(nick_name=request.session["name"])
        context['has_wallet'] = bool(player.wallet)
        context['tokens'] = get_player_tokens(player)
    except TransportQueryError as e:
        traceback.print_exc()
        context['error_message'] = eval(str(e)).get('message')
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        context['error_message'] = str(e)

    return render(request, 'backend/user/exchange/tokens.html', context)


@needs_user_auth
def transactions_queue(request):
    context = {'active_menu': 'transaction'}

    try:
        player = PlayerBase.objects.get(nick_name=request.session["name"])
        context['transactions'] = player.transaction_set.order_by(
            '-id').values()
        for t in context['transactions']:
            t['details'] = json.loads(t['details'])
    except Exception as e:
        context['error_message'] = str(e)

    return render(request, 'backend/user/exchange/queue.html', context)


@protected()
def signin(request, bl):
    if request.session.get('id', None):
        request.session.pop('id')
    if request.session.get('name', False):
        return redirect('/')

    status = {}  # placeholder
    context = {}

    if bl.user_fail_strikes:
        context['user_fail_warn'] = True

    if bl.user_hopping_strikes:
        context['user_hopping_warn'] = True

    if request.method == "POST":
        usr = request.POST.get("user", None)
        pwd = request.POST.get("pass", None)

        if usr and pwd:
            status = authenticate(usr, pwd)
            if not status["error"]:
                # request.session.set_expiry(48 * 60 * 60)
                request.session['id'] = status['user'].id
                request.session['user_name'] = status['user'].nick_name
                request.session['user_pass'] = pwd
                request.session['email'] = status['user'].email

                player = PlayerBase.objects.get(nick_name=usr)
                if not player.tfa_token:
                    player.tfa_token = pyotp.random_base32()
                    player.save(update_fields=('tfa_token',))
                return redirect('/2fa/')
            else:
                bl.add_user_fail(usr)
        else:
            status['error'] = "User and Password are mandatory"
            bl.add_user_fail()

    # store authentication error if any
    context["error_message"] = status.get('error')
    return render(request, 'backend/user/auth/signin.html', context)

@protected()
def tfa(request, bl):
    if not request.session.get('id'):
        return redirect('/signin')

    player = PlayerBase.objects.get(id=request.session.get('id'))
    totp = pyotp.TOTP(player.tfa_token)
    context = {}
    qr_code_url = totp.provisioning_uri(name='spacemisfits.com')
    context["qr_code_url"] = qr_code_url
    context["username"] = request.session.get('user_name')
    print(totp.now())

    if request.method == "POST":
        if not request.POST.get('tfa1') or not request.POST.get('tfa2') or not request.POST.get(
                'tfa3') or not request.POST.get('tfa4') or not request.POST.get('tfa5') or not request.POST.get('tfa6'):
            context['error_message'] = 'Verification codes are required.'
            return render(request, 'backend/user/auth/2fa.html', context)
        else:
            code = request.POST.get('tfa1') + request.POST.get('tfa2') + request.POST.get('tfa3') + request.POST.get(
                'tfa4') + request.POST.get('tfa5') + request.POST.get('tfa6')
            keycode = player.tfa_email_code
            if keycode == code or totp.verify(code): # check if code is same as email verification code or google authenticator code
                player = PlayerBase.objects.get(id=request.session.get('id'))
                status = authenticate(request.session.get('user_name'), request.session.get('user_pass'))
                request.session.set_expiry(48 * 60 * 60)
                # request.session['id'] = status['user'].id
                request.session['name'] = request.session.get('user_name')
                request.session['email'] = player.email
                request.session['notif_url'] = getenv('NOTIF_URL')

                player.notifier_token = uuid4().hex  # single user notification key
                player.tfa_email_code = None # initialize email verification code after login successfully
                player.save(update_fields=('notifier_token', 'tfa_email_code',))

                request.session["secret_key"] = player.notifier_token

                if not player.email:
                    request.session["email_error"] = "Please configure an email address to be able" \
                                                     " to reset your password in case you forget"

                try:
                    get_player_info(player, force_update=True)
                except Exception as e:
                    traceback.print_exc()

                bl.clear_fails()
                # success
                request.session["last_ping"] = datetime.datetime.timestamp(
                    timezone.now())

                if not OffchainCrownCredit.objects.filter(player_id=status['user'].nick_name).exists():
                    # initalialize player's offchain balance to 0
                    OffchainCrownCredit.objects.create(
                        player=status['user'], offchain_hrc_balance=0, offchain_erc_balance=0, offchain_bsc_balance=0)
                return redirect('/user/')
            else:
                context['error_message'] = 'Your verification code is incorrect or expired. Please try again.'

    return render(request, 'backend/user/auth/2fa.html', context)

def tfa_email(request):
    if not request.session.get('id'):
        return redirect('/')

    context = {}
    player = PlayerBase.objects.get(id=request.session.get('id'))
    totp = pyotp.TOTP(player.tfa_token)
    qr_code_url = totp.provisioning_uri(name='spacemisfits.com')
    context["qr_code_url"] = qr_code_url
    context["username"] = request.session.get('user_name')

    ## Generate key code for email with Counter-Based Token
    hotp = pyotp.HOTP(player.tfa_token)
    keycode = hotp.at(round(time.time())) ## Use time seconds for random key code
    player.tfa_email_code = keycode
    player.save(update_fields=('tfa_email_code',))

    ## Sending Verification Email
    try:
        subject = "[Space Misfits] Your verification code here!"
        message = f"""
            "Your verification code is """ + keycode
        send_mail(
            subject,
            message,
            getenv('EMAIL_HOST_USER'),
            [player.email],
            fail_silently = False
        )
        context['success_message'] = 'We sent an email with your authentication code. Please check your mailbox.'
    except SMTPException:
        context['error_message'] = 'Something went wrong. Please try again later.'

    return render(request, 'backend/user/auth/2fa.html', context)


def signout(request):
    if request.method == 'POST':
        request.session.clear()

    return redirect('/')


# REAL signup
def signup(request):
    error = None

    if request.session.get('name', False):
        return redirect('/')

    if request.method == "POST":
        name = request.POST.get("user")
        email = request.POST.get("email")
        pwd1 = request.POST.get("pass")
        pwd2 = request.POST.get("confirm_pass")

        if not (name and email and pwd1):
            error = "All fields are required"
            return render(request, 'backend/user/auth/signup.html', {"error_message": error})

        if not email:
            error = "Email field is required"
            return render(request, 'backend/user/auth/signup.html', {"error_message": error})

        if pwd1 != pwd2:
            error = "Passwords don't match"
            return render(request, 'backend/user/auth/signup.html', {"error_message": error})

        status = register(name, email, pwd1)

        if not status["error"]:
            # initalialize player's offchain balance to 0
            OffchainCrownCredit.objects.create(
                player=status['user'], offchain_hrc_balance=0, offchain_erc_balance=0, offchain_bsc_balance=0)
            # here we add email confirmation logic
            error = send_email_confirmation(status["user"])

            if error == "OK":
                return render(request, "frontend/landpage/notification.html", {"message": "Check your inbox to confirm the email address"})
        else:
            error = status["error"]

    return render(request, 'backend/user/auth/signup.html', {"error_message": error})


# TESTING signup with invitation
def signup_testing(request):
    error = None

    if request.session.get('name', False):
        return redirect('/')

    if request.method == "POST":
        name = request.POST.get("user")
        email = request.POST.get("email")
        pwd1 = request.POST.get("pass")
        pwd2 = request.POST.get("confirm_pass")
        code = request.POST.get("code")

        if not code or not TesterInvitation.objects.filter(code=code, consumed=False).exists():
            error = "Sorry, this party is with invitation in hand only."
            return render(request, 'backend/user/auth/signup_with_invitation.html', {"error_message": error})

        invitation = TesterInvitation.objects.get(code=code, consumed=False)

        if not (name and email and pwd1):
            error = "All fields are required"
            return render(request, 'backend/user/auth/signup_with_invitation.html', {"error_message": error})

        if not email:
            error = "Email field is required"
            return render(request, 'backend/user/auth/signup_with_invitation.html', {"error_message": error})

        if pwd1 != pwd2:
            error = "Passwords don't match"
            return render(request, 'backend/user/auth/signup_with_invitation.html', {"error_message": error})

        status = register(name, email, pwd1)

        if not status["error"]:
            # here we add email confirmation logic
            error = send_email_confirmation(status["user"])

            if error == "OK":
                invitation.consumed = True
                invitation.player = status["user"]
                invitation.save()
                return render(request, "frontend/landpage/notification.html", {"message": "Check your inbox to confirm the email address"})
        else:
            error = status["error"]

    return render(request, 'backend/user/auth/signup_with_invitation.html', {"error_message": error})


# password reset methods
def password_recovery(request):
    # request a password reset link
    if request.method == "POST":
        email = request.POST.get("email")

        # find user by email
        try:
            player = PlayerBase.objects.get(email=email)
        except Exception as e:
            print(e)
            return render(request, "frontend/landpage/notification.html", {"message": "An error occurred while trying to send the recovery link"})

        # check email validity
        try:
            confirmation = player.emailconfirmationrequest_set.latest(
                'created_at')
        except Exception as e:
            print(e)
            return render(request, "frontend/landpage/notification.html", {"message": "An error occurred while trying to send the recovery link"})

        if not confirmation.confirmed:
            return render(request, "frontend/landpage/notification.html", {"message": "An error occurred while trying to send the recovery link"})

        # send email
        result = send_password_recovery(player)
        if result == "OK":
            return render(request, "frontend/landpage/notification.html", {"message": "A recovery link has been sent to your email address"})

    return render(request, "backend/user/reset/password_recovery.html")


def password_reset(request, token):
    error = None

    try:
        recovery = PasswordRecoveryRequest.objects.get(token=token)
    except Exception as e:
        return render(request, "frontend/landpage/invalid_link.html")

    if has_expired(recovery):
        recovery.delete()
        return render(request, "frontend/landpage/invalid_link.html")

    if request.method == "POST":
        pwd1 = request.POST.get("password")
        pwd2 = request.POST.get("password_confirmation")

        if pwd1 and pwd2 and pwd1 == pwd2:
            result = pve_password_reset(recovery.player.nick_name, pwd1)
            if result == 'OK':
                recovery.delete()
                return render(request, 'backend/user/reset/password_reset_successful.html')
            else:
                error = result
        else:
            error = "Password confirmation doesn't match"

    # process reset password link
    return render(request, 'backend/user/reset/password_reset.html', {'error': error})


def confirm_email(request, token):
    try:
        confirmation = EmailConfirmationRequest.objects.get(token=token)
        confirmation.confirmed = True
        confirmation.save()
    except Exception as e:
        return render(request, "frontend/landpage/invalid_link.html")

    return render(request, "backend/user/reset/confirm_email.html")


@needs_admin_auth
def admin_list_users(request):
    users = PlayerBase.objects.all()

    return render(request, 'backend/mgmt/users/users.html', {"users": users})

###
# PUBLIC VIEWS
###
# MAIN PAGE


def landpage(request):
    context = {
        'content': Settings.objects.latest('id'),  # get model data as dict
        'posts': BlogPost.objects.all()[:4],
        'active_menu': 'home',
    }

    return render(request, 'frontend/landpage/main.html', context)


def summary_leaderboard(request):
    campaign = {
        'name': 'The Harvest',  # change to campaign name
        'description': 'Misfits set out to collect hidden data',  # change to campaign name
        # change to event date
        'start': make_aware(datetime.datetime(2021, 8, 20, 23, 0)),
        # change to event date
        'end': make_aware(datetime.datetime(2021, 8, 22, 23, 0)),
        'status': 'ENDED',  # change to event date
        'leaderboard': [
            {'position': 1, 'nick': "Andromeda", 'score': 656},
            {'position': 2, 'nick': "IceCraft", 'score': 479},
            {'position': 3, 'nick': "ElKappaG", 'score': 439},
            {'position': 4, 'nick': "SchlongGoblin", 'score': 403},
            {'position': 5, 'nick': "Dogira_Gooding", 'score': 346},
            {'position': 6, 'nick': "Shinigami", 'score': 324},
            {'position': 7, 'nick': "Bizzo258", 'score': 310},
            {'position': 8, 'nick': "themightyneon", 'score': 296},
            {'position': 9, 'nick': "pika5700", 'score': 269},
            {'position': 10, 'nick': "crazyuncletan", 'score': 214},
            {'position': 11, 'nick': "RumBelly_Clark", 'score': 199},
            {'position': 12, 'nick': "SNOOZEHEHE", 'score': 194},
            {'position': 13, 'nick': "Username", 'score': 177},
            {'position': 14, 'nick': "zeus_ion", 'score': 174},
            {'position': 15, 'nick': "Delusion", 'score': 170},
            {'position': 16, 'nick': "ChiefKin", 'score': 163},
            {'position': 17, 'nick': "everyone", 'score': 149},
            {'position': 18, 'nick': "ultraboss", 'score': 140},
            {'position': 19, 'nick': "PHOENIX01", 'score': 122},
            {'position': 20, 'nick': "FRIENDLY", 'score': 118},
            {'position': 21, 'nick': "bezerke987", 'score': 117},
            {'position': 22, 'nick': "Wowriorz", 'score': 84},
            {'position': 23, 'nick': "PanickedPanda", 'score': 71},
            {'position': 24, 'nick': "redsteel", 'score': 63},
            {'position': 25, 'nick': "CmdrProschy", 'score': 42},
            {'position': 26, 'nick': "Jrfantasma", 'score': 40},
            {'position': 27, 'nick': "vega2021", 'score': 33},
            {'position': 28, 'nick': "bigbearcommander", 'score': 32},
            {'position': 29, 'nick': "Boilerrr", 'score': 32},
            {'position': 30, 'nick': "twistyblade", 'score': 31},
            {'position': 31, 'nick': "oOMionOo", 'score': 29},
            {'position': 32, 'nick': "trojans04", 'score': 28},
            {'position': 33, 'nick': "Asantos96", 'score': 26},
            {'position': 34, 'nick': "Sinisterblow", 'score': 26},
            {'position': 35, 'nick': "Cryptozow", 'score': 23},
            {'position': 36, 'nick': "navidmehri", 'score': 21},
            {'position': 37, 'nick': "GameGeist", 'score': 17},
            {'position': 38, 'nick': "wendrao_", 'score': 17},
            {'position': 39, 'nick': "EndarSpyre", 'score': 17},
            {'position': 40, 'nick': "Helio188", 'score': 16},
            {'position': 41, 'nick': "Crackerjax", 'score': 16},
            {'position': 42, 'nick': "Kopho555", 'score': 13},
            {'position': 43, 'nick': "Formo2112", 'score': 13},
            {'position': 44, 'nick': "Roosevelt", 'score': 12},
            {'position': 45, 'nick': "inywer01", 'score': 11},
            {'position': 46, 'nick': "Astro007", 'score': 11},
            {'position': 47, 'nick': "russman6", 'score': 10},
            {'position': 48, 'nick': "Maverick", 'score': 8},
            {'position': 49, 'nick': "CroKiLlEr", 'score': 8},
            {'position': 50, 'nick': "Lusitanio", 'score': 8},
            {'position': 51, 'nick': "SubbyChevy", 'score': 7},
            {'position': 52, 'nick': "maku69_esp", 'score': 7},
            {'position': 53, 'nick': "TheConquerer", 'score': 7},
            {'position': 54, 'nick': "Shooter8u", 'score': 5},
            {'position': 55, 'nick': "immortal2021", 'score': 5},
            {'position': 56, 'nick': "kwongvee79", 'score': 5},
            {'position': 57, 'nick': "vozdepato", 'score': 4},
            {'position': 58, 'nick': "Valdemortsall", 'score': 4},
            {'position': 59, 'nick': "IntergalacticOvrlord", 'score': 4},
            {'position': 60, 'nick': "UtopiousSpoon", 'score': 3},
            {'position': 61, 'nick': "Lustafari", 'score': 3},
            {'position': 62, 'nick': "strgwyrnel", 'score': 3},
            {'position': 63, 'nick': "ArthemisFall", 'score': 3},
            {'position': 64, 'nick': "spacelord94", 'score': 2},
            {'position': 65, 'nick': "MrAnderson", 'score': 2},
            {'position': 66, 'nick': "TarkSpace", 'score': 2},
            {'position': 67, 'nick': "MarconiSantos", 'score': 2},
            {'position': 68, 'nick': "GugaGanjaBoy", 'score': 2},
            {'position': 69, 'nick': "Krazykraw", 'score': 2},
            {'position': 70, 'nick': "DaniPhoenix", 'score': 1},
            {'position': 71, 'nick': "Drogowit", 'score': 1},
            {'position': 72, 'nick': "gabrielthc", 'score': 1},
            {'position': 73, 'nick': "EirikTheViking", 'score': 1},
            {'position': 74, 'nick': "throw777", 'score': 1},
            {'position': 75, 'nick': "Chuck2010", 'score': 1}
        ],
    }

    return render(request, 'frontend/landpage/leaderboard.html', {"campaign": campaign})


def leaderboard(request, id):
    context = {}
    data = api_get('public/leaderboard/', id=id)

    if data['error']:
        return render(request, 'frontend/landpage/notification.html', {'message': 'Event not available'})

    context['campaign'] = data.pop('campaign')
    context['campaign']['start'] = make_aware(
        datetime.datetime.strptime(context['campaign']['start'], ZTIME_FORMAT))
    if context['campaign'].get('end'):
        context['campaign']['end'] = make_aware(
            datetime.datetime.strptime(context['campaign']['end'], ZTIME_FORMAT))

    return render(request, 'frontend/landpage/leaderboard.html', context)


def blog(request, slug=None):
    if not slug:
        posts = BlogPost.objects.all().order_by('-created_at')
        return render(request, 'frontend/blog/main.html', {'posts': posts, 'active_menu': 'news'})
    else:
        post = BlogPost.objects.get(slug=slug)
        return render(request, 'frontend/blog/single.html', {'post': post, 'active_menu': 'news'})


def subscription(request):
    response_data = {}
    if request.method == "POST":
        email = request.POST["email"]
        # Mailchimp Settings
        api_key = settings.MAILCHIMP_API_KEY
        server = settings.MAILCHIMP_DATA_CENTER
        list_id = settings.MAILCHIMP_EMAIL_LIST_ID

        """
     Contains code handling the communication to the mailchimp api
     to create a contact/member in an audience/list.
    """
        mailchimp = Client()
        mailchimp.set_config({
            "api_key": api_key,
            "server": server,
        })

        member_info = {
            "email_address": email,
            "status": "subscribed",
        }

        try:
            response = mailchimp.lists.add_list_member(list_id, member_info)
            response_data["result"] = "Successfully subscribed"
            response_data["status"] = "success"
        except ApiClientError as error:
            response_data["result"] = "Failed subscription"
            response_data["status"] = "error"
    else:
        response_data["result"] = "Failed subscription"
        response_data["status"] = "error"

    return HttpResponse(json.dumps(response_data), content_type="application/json")


def shop(request):
    context = {}
    context['categories'] = Categories.objects.filter(level=0)

    selectedSubCategory = request.GET.get('sub_category')
    selected_category = request.GET.get('category')
    if selected_category == '' or selected_category == None:
        selected_category = None
    else:
        selected_category = [int(x.strip())
                             for x in selected_category.split(',') if x]

    if selectedSubCategory == None:
        selectedSubCategory = 'All'

    child_ids = []
    context['sub_categories'] = []
    if selectedSubCategory == 'All':
        if selected_category != None:
            for parentId in selected_category:
                child_ids.append(parentId)
                for child in Categories.objects.filter(parent_id=parentId).values('id'):
                    child_ids.append(child['id'])
    else:
        child_ids.append(selectedSubCategory)

    context['product'] = (Products.objects.all() if selected_category ==
                          None else Products.objects.filter(category__in=child_ids))

    if selected_category != None:
        context['sub_categories'] = Categories.objects.filter(
            parent_id__in=selected_category)
        selectedCateIdStr = ","
        selectedCateIdStr = selectedCateIdStr.join(
            str(s) for s in selected_category)
    else:
        selectedCateIdStr = ""

    return render(
        request,
        'landpage/shop.html',
        {
            'products': context['product'],
            'categories': context['categories'],
            'subCategories': context['sub_categories'],
            'selected_category': selected_category,
            'selectedSubCategory': selectedSubCategory,
            'selectedCateIdStr': selectedCateIdStr,
            'active_menu': 'shop',
        }
    )


@needs_user_auth
def checkout(request):
    context = {'active_menu': 'shop'}
    context['key'] = settings.STRIPE_PUBLISHABLE_KEY
    context['wallet_address'] = settings.WALLET_ADDRESS

    cart = Cart.objects.filter(
        customer_id=request.session['name'], status=0).first()
    if cart:
        cartItem = CartItem.objects.filter(cart_id=cart.id).extra(
            select={'title': 'mainsite_products.title',
                    'image': 'mainsite_products.image'},
            tables=['mainsite_products'],
            where=['mainsite_cartitem.product_id=mainsite_products.id']
        ).values('quantity', 'price', 'id', 'title', 'image')
        context['cartItems'] = list(cartItem)
        context['total_price'] = cart.total_price
    else:
        context['cartItems'] = []
        context['total_price'] = 0
    return render(request, 'landpage/checkout.html', context)


@needs_user_auth
def product(request, id):
    product = Products.objects.get(id=id)
    return render(request, 'landpage/product.html', {'product': product, 'active_menu': 'shop'})


@needs_user_auth
def list_cart_items(request):
    context = {'active_menu': 'shop'}
    context['key'] = settings.STRIPE_PUBLISHABLE_KEY
    context['wallet_address'] = settings.WALLET_ADDRESS

    cart = Cart.objects.filter(
        customer_id=request.session['name'], status=0).first()
    if cart:
        cartItem = CartItem.objects.filter(cart_id=cart.id).extra(
            select={'title': 'mainsite_products.title',
                    'image': 'mainsite_products.image'},
            tables=['mainsite_products'],
            where=['mainsite_cartitem.product_id=mainsite_products.id']
        ).values('quantity', 'price', 'id', 'title', 'image')
        context['cartItems'] = list(cartItem)
        context['total_price'] = cart.total_price
    else:
        context['cartItems'] = []
        context['total_price'] = 0
    return render(request, 'landpage/view_cart.html', context)


def add_cart_items(request, *args, **kwargs):
    if request.method == 'POST':
        user_id = request.POST['user_id']
        product_id = request.POST['product_id']
        quantity = request.POST['quantity']
        total_price = request.POST['total_price']
        price = request.POST['price']

        cart = Cart.objects.filter(customer_id=user_id, status=0).first()

        if cart:
            cart.total_price = total_price
            cart.save()
            cartItem = CartItem.objects.filter(
                cart_id=cart.id, product_id=product_id)

            if cartItem:
                cartItem = CartItem.objects.get(
                    cart_id=cart.id, product_id=product_id)
                cartItem.quantity = int(quantity)
                cartItem.price = price
                cartItem.save()
            else:
                new_cartItem = CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=quantity,
                    price=price
                )
                new_cartItem.save()
        else:
            cart = Cart(
                status=0,
                total_price=total_price,
                customer_id=user_id
            )
            cart.save()

            cartItem = CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
                price=price
            )

            cartItem.save()
        data = {'code': 'success'}
        return JsonResponse(data)
    return HttpResponseNotFound('<h1>Page not found</h1>')


def get_cart_items(request, *args, **kwargs):
    if request.method == 'GET':
        request_type = request.GET["type"]
        context = {}
        if request_type == 'getByUsername':
            user_id = request.GET["user_id"]
            cart = Cart.objects.filter(customer_id=user_id, status=0).first()
            if cart:
                cartItem = CartItem.objects.filter(cart_id=cart.id).extra(
                    select={'title': 'mainsite_products.title',
                            'image': 'mainsite_products.image'},
                    tables=['mainsite_products'],
                    where=['mainsite_cartitem.product_id=mainsite_products.id']
                ).values('quantity', 'price', 'product_id', 'title', 'image', 'created_at')
                context['my-cart'] = list(cartItem)
            else:
                context['my-cart'] = []
        else:
            cartId = request.GET["cart_id"]
            cartItem = CartItem.objects.filter(cart_id=cartId).extra(
                select={'title': 'mainsite_products.title',
                        'image': 'mainsite_products.image'},
                tables=['mainsite_products'],
                where=['mainsite_cartitem.product_id=mainsite_products.id']
            ).values('quantity', 'price', 'product_id', 'title', 'image', 'created_at')
            context['my-cart'] = list(cartItem)
        return JsonResponse({"myCart": context['my-cart']})


def delete_cart_item(request, *args, **kwargs):
    if request.method == 'POST':
        request_data = json.loads(request.body)
        cartItem = CartItem.objects.get(id=request_data['cartItem_id'])
        cartItem_price = cartItem.quantity * cartItem.price
        cartItem_product_id = cartItem.product_id
        #print("cartItem_price", cartItem_price)
        cart = Cart.objects.get(id=cartItem.cart_id)
        cart.total_price = cart.total_price - cartItem_price
        #print("total_price", cart.total_price - cartItem_price)
        cart.save()
        cartItem.delete()
        return JsonResponse({'status': 1, 'product_id': cartItem_product_id})


def get_product_count_by_customer(request, *args, **kwargs):
    if request.method == 'GET':
        count = 0
        user_id = request.GET["user_id"]
        product_id = request.GET["product_id"]
        carts = Cart.objects.filter(customer_id=user_id)

        cartIds = []
        for cart in carts:
            cartIds.append(cart.id)

        if cart:
            cartItems = CartItem.objects.filter(
                cart_id__in=cartIds, product_id=product_id)
            for cartItem in cartItems:
                count += int(cartItem.quantity)

        return JsonResponse({"count": count})


@csrf_exempt
def create_checkout_stripe_session(request, *args, **kwargs):
    if request.method == 'POST':
        uid = kwargs.get('uid')
        request_data = json.loads(request.body)
        domain_url = settings.THIS_URL
        stripe.api_key = settings.STRIPE_SECRET_KEY

        cart = get_object_or_404(Cart, customer_id=uid, status=0)
        cartItems = CartItem.objects.filter(cart_id=cart.id)
        line_items = []
        amount = 0
        for cartItem in cartItems:
            amount += int(cartItem.price * 100) * cartItem.quantity
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': cartItem.product.title,
                    },
                    'unit_amount': int(cartItem.price * 100),
                },
                'quantity': cartItem.quantity,
            })

        checkout_session = stripe.checkout.Session.create(
            # Customer Email is optional,
            # It is not safe to accept email directly from the client side
            customer_email=request_data['email'],
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=domain_url + \
            'payment-success?session_id={CHECKOUT_SESSION_ID}&type=Stripe',
            cancel_url=domain_url + 'payment-failed/',
        )

        order = OrderDetail.objects.filter(cart_id=cart.id, has_paid=0).first()
        if order is None:
            order = OrderDetail()
            order.customer_email = request_data['email']
            order.cart = cart
            order.payment_intent = checkout_session['payment_intent']
            order.enjin_address = request_data['enjin_address']
            order.amount = amount
            order.save()
        else:
            order.customer_email = request_data['email']
            order.cart = cart
            order.payment_intent = checkout_session['payment_intent']
            order.enjin_address = request_data['enjin_address']
            order.amount = amount
            order.save()

        return JsonResponse({'sessionId': checkout_session.id})


@csrf_exempt
def create_checkout_crypto_session(request, *args, **kwargs):
    if request.method == 'POST':
        uid = kwargs.get('uid')
        request_data = json.loads(request.body)

        cart = get_object_or_404(Cart, customer_id=uid, status=0)
        cartItems = CartItem.objects.filter(cart_id=cart.id)
        amount = 0
        for cartItem in cartItems:
            amount += int(cartItem.price * 100) * cartItem.quantity

        order = OrderDetail()
        order.customer_email = request_data['email']
        order.cart = cart
        order.transaction = request_data['transaction']
        order.enjin_address = request_data['enjin_address']
        order.payment_type = 1
        order.amount = amount
        order.save()

        return JsonResponse({'status': "OK"})


def export_product(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'

    products = Products.objects.all()

    writer = csv.writer(response)
    writer.writerow(['NAME', 'SUPPLY', 'PRICE'])
    for product in products:
        writer.writerow([product.title, product.put_quantity -
                        product.out_quantity, "$ " + str(decimal.Decimal(product.price))])

    return response


def test(request):
    context = {}
    context['key'] = settings.STRIPE_PUBLISHABLE_KEY
    return render(request, 'landpage/subscription.html', context)


def payment_success(request):
    session_id = request.GET.get('session_id')
    payment_type = request.GET.get('type')
    order = ''
    if payment_type == 'Stripe':
        if session_id is None:
            return HttpResponseNotFound()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = session.payment_intent
        order = get_object_or_404(
            OrderDetail, payment_intent=session.payment_intent)
    else:
        order = get_object_or_404(OrderDetail, transaction=session_id)

    order.has_paid = True
    order.save()

    cart = Cart.objects.get(id=order.cart_id)
    if cart.status == 0:
        cart.status = 1
        cart.save()

    context = {}
    cartItems = CartItem.objects.filter(cart_id=cart.id)
    context['cartItems'] = cartItems
    context['total_amount'] = cart.total_price
    context['payment_type'] = payment_type

    player = PlayerBase.objects.get(email=order.customer_email)
    subject = "[Space Misfits] Thank you for your order!"
    message = f"""
  Thank you for your purchase!
  
  We are currently processing your order and we will make delivery within 2 business days!
  """

    mail_result = send_email_to_user(player, subject, message)

    return render(request, 'landpage/payment_success.html', context)


def payment_failed(request):
    return render(request, 'landpage/payment_failed.html')
