import re
from vic3.game import vic3game


# Returns the display name of an item (building, PM, good, etc.) after resolving all the nested localizations.
def get_display_name(elem) -> str:
    # recursively resolve $nested$ localizations
    text = vic3game.parser.formatter.resolve_nested_localizations(elem.display_name)
    # delete @icon! references
    return ' '.join(re.sub(r'@([^!]*)!', '', text).split())

