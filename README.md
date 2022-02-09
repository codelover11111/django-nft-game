Space Misfits Website & Marketplace
===

### Settings
```env
PVE_URL='http://spacemisfits...'
ARENA_KEY="YourSecretKey"
ARENA_KEY_NUMBER=1234
TOKEN='secrethandhaketoken'

EMAIL_HOST = "spacemisfits..."
EMAIL_PORT = 123
EMAIL_HOST_USER = "email@spacemisfits..."
EMAIL_HOST_PASSWORD = "secret_password"
EMAIL_USE_SSL = True

## address for the emails link
THIS_URL="http://localhost:9000/"

## notification address
NOTIF_LOCAL_URL="https://notification.url/"
NOTIF_URL="notification.url"

## mailchimp credentials
MAILCHIMP_API_KEY="4838be..."
MAILCHIMP_DATA_CENTER="us1"
MAILCHIMP_EMAIL_LIST_ID="a76..."

## wallet address
WALLET_ADDRESS="0xABD3c..."

## stripe credentials
STRIPE_PUBLISHABLE_KEY="pk_sVr8Uc..."
STRIPE_SECRET_KEY="sk_ZFrJX..."

## mysql credentials
# per database (remove to use sqlite)
default_database="smsite_db"
blacklist_database="smsite_blacklist"
# general
dbuser="user.."
dbpass="pass..."
dbhost="db.domain"
dbport=00000
sslmode="REQUIRED"
```

### uWSGI
First install `uwsgi` using `pip install uwsgi`

Run the application like this
```bash
uwsgi -s localhost:8000 --module SMSite.wsgi --enable-threads -M -i --vacuum --daemonize server.log --pidfile file.pid
```

for testing purpose add `--protocol=http`:
```bash
uwsgi --protocol=http -s localhost:8000 --module SMSite.wsgi --enable-threads -M
```

### Nginx configuration
```ignorelang
# the upstream component nginx needs to connect to
upstream SMSite {
    # server unix:///path/to/your/mysite/mysite.sock; # for a file socket
    server 127.0.0.1:8000; # for a web port socket (we'll use this first)
}

# configuration of the server
server {
    # the port your site will be served on
    listen      80;
    # the domain name it will serve for
    server_name example.com; # substitute your machine's IP address or FQDN
    charset     utf-8;

    # max upload size
    client_max_body_size 75M;   # adjust to taste

    # Django media
    location /media  {
        alias /home/ann/SMSite/SMSite/media;  # your Django project's media files - amend as required
    }

    location /static {
        alias /home/ann/SMSite/SMSite/static; # your Django project's static files - amend as required
    }

    # Finally, send all non-media requests to the Django server.
    location / {
        uwsgi_pass  SMSite;
        include     /etc/nginx/uwsgi_params; # the uwsgi_params file you installed
    }
}
```
