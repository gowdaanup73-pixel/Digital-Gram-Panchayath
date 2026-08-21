from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css_class):
    return field.as_widget(attrs={'class': css_class})

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}