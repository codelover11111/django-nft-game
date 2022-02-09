from django import template

register = template.Library()

@register.filter()
def pull(dictio, key):
  return dictio.get(key)
