from django import template

from polls import utils

register = template.Library()


@register.filter
def time_ago(value):
    return utils.time_ago(value)


@register.filter
def time_left(value):
    return utils.time_left(value)
