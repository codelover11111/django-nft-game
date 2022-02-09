from django import template

register = template.Library()

@register.filter()
def set_invisible(value):
  return '' if value else 'invisible'

@register.filter()
def set_disabled(value):
  return 'disabled' if value else ''
