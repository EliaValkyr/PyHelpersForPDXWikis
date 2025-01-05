import re
from collections import defaultdict

from vic3.game import vic3game
from vic3.vic3lib import PopType, Law
from vic3.PMSpreadsheet.utils import get_display_name

pop_types: dict[str, PopType] = vic3game.parser.pop_types
laws: dict[str, Law] = vic3game.parser.laws
economic_laws = [law for _, law in laws.items() if law.group == 'lawgroup_economic_system']


def get_pop_types_order() -> list[PopType]:
    # Sort pop types by strata, then by file order (based on the profession_to_strata map)
    # Sort the professions based on their strata
    strata_order = ['upper', 'middle', 'lower']  # This is the desired order of strata
    profession_to_strata = {
        'academics': 'middle',
        'aristocrats': 'upper',
        'bureaucrats': 'middle',
        'capitalists': 'upper',
        'clergymen': 'middle',
        'clerks': 'lower',
        'engineers': 'middle',
        'farmers': 'middle',
        'laborers': 'lower',
        'machinists': 'lower',
        'officers': 'middle',
        'peasants': 'lower',
        'shopkeepers': 'middle',
        'slaves': 'lower',
        'soldiers': 'lower'
    }
        # Set the strata for each pop_type based on the profession_to_strata map
    for key, pop_type in pop_types.items():
        # Set the strata from the map
        pop_type.strata = profession_to_strata.get(key, 'lower')  # Default to 'lower' if not found

    # We can create a sorted list of pop_types by strata
    sorted_pop_types = sorted(pop_types.items(), key=lambda item: strata_order.index(profession_to_strata.get(item[0], 'lower')))
    
    # Return the sorted pop types (sorted by strata and then by key)
    return [pop_type for key, pop_type in sorted_pop_types]



def get_investment_pool_contributions() -> dict[str, float]:
    base_modifiers = vic3game.parser.named_modifiers['base_values'].modifiers
    contributions: dict[str, float] = defaultdict(float)

    for modifier in base_modifiers:
        if m := re.fullmatch(r'state_(.+)_investment_pool_contribution_add', modifier.name):
            contributions[m.group(1)] = modifier.value
    return contributions


def get_ip_efficiency_per_law():
    result = defaultdict(dict)
    for law in economic_laws:
        for modifier in law.modifiers:
            if m := re.fullmatch(r'state_(.+)_investment_pool_efficiency_mult', modifier.name):
                pop_type = m.group(1)
                result[pop_type][law.name] = modifier.value
    return result


def print_pop_type_data(dir_name: str) -> None:
    file_name = dir_name / "pop_types.txt"
    file = open(file_name, 'w')

    headers: list[str] = [
        'Name',
        'Display Name',
        'Strata',
        'Wage Multiplier',
        'Investment Pool Contribution',
        *(law.display_name for law in economic_laws),
    ]

    print(
        *headers,
        sep='\t',
        file=file
    )

    ip_contributions = get_investment_pool_contributions()
    ip_efficiencies = get_ip_efficiency_per_law()

    for pop_type in get_pop_types_order():
        print(
            pop_type.name,
            get_display_name(pop_type),
            pop_type.strata,
            pop_type.wage_weight,
            ip_contributions[pop_type.name],
            *(ip_efficiencies[pop_type.name].get(law.name, 0) for law in economic_laws),
            sep='\t',
            file=file
        )

    print(
        "government",
        "Government",
        "none",
        0,
        1,
        *(0 for _ in range(len(economic_laws))),
        sep='\t',
        file=file
    )
