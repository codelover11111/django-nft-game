from django import template
from pytz import timezone

register = template.Library()

DEFAULT_FORMAT="%b %-d, %Y, %H:%M %Z"
EST = timezone('EST')
UTC = timezone('UTC')

@register.filter()
def to_est(datetime, arg=DEFAULT_FORMAT):
  return EST.normalize(datetime.astimezone(EST)).strftime(arg)

@register.filter()
def to_utc(datetime, arg=DEFAULT_FORMAT):
  return UTC.normalize(datetime.astimezone(UTC)).strftime(arg)

@register.filter()
def delta(deltatime):
  hours = int(deltatime.total_seconds() / 60 / 60 % 24)
  minutes = int(deltatime.total_seconds() / 60 % 60)
  seconds = int(deltatime.total_seconds() % 60)
  return "%02d:%02d.%02d" % (hours, minutes, seconds)
