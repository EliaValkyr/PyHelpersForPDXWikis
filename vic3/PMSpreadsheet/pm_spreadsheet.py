from collections import defaultdict
import re
import sys

from vic3.PMSpreadsheet.goods_spreadsheet import get_goods_order
from vic3.PMSpreadsheet.pop_types_spreadsheet import get_pop_types_order
from vic3.PMSpreadsheet.utils import get_display_name
from vic3.game import vic3game
from vic3.vic3lib import Building, BuildingGroup, ProductionMethod, ProductionMethodGroup, PopType, Good, Modifier, Law, Technology

goods: dict[str, Good] = vic3game.parser.goods
poptypes: dict[str, PopType] = vic3game.parser.pop_types

laws: dict[str, Law] = vic3game.parser.laws
economic_laws = [law for _, law in laws.items() if law.group == 'lawgroup_economic_system']


def get_law_keys() -> list[str]:
	return [law.name for law in economic_laws]


def get_law_key_labels() -> list[str]:
	return [law.display_name for law in economic_laws]


def get_header_keys() -> list[str]:
	return ['input', 'output', 'employment', 'shares']


def get_header_key_labels() -> list[str]:
	return ['in_', 'out_', 'emp_', 'shr_']


# Parses the modifier name, and decomposes it in three parts.
def parse_modifier_name(pm: ProductionMethod, scaled_by: str, modifier_name: str) -> tuple[str, str, {str, PopType, Good}]:
	# Remove common elements from the modifier name. Currently, all modifiers start with "building_".
	m = re.fullmatch(r'(?:building_|goods_)(.+)', modifier_name)
	assert m, f'UNKNOWN MODIFIER'
	modifier_name = m.group(1)

	# try the various types we know of

	# Modifier: pop type shares.
	if m := re.fullmatch(r'(.+)_shares_add', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching, expected unscaled'
		return 'poptype', 'shares', m.group(1) if m.group(1) in {'government', 'workforce'} else poptypes[m.group(1)]

	# Modifier: pop type employment.
	if m := re.fullmatch(r'employment_(.+)_add', modifier_name):
		# For some reason, these PMs have workforce_scaled employment modifiers, instead of level_scaled.
		is_vineyards = pm.name == 'pm_vineyards' or pm.name.startswith('pm_vineyards_building_')
		is_anchorage = pm.name == 'pm_anchorage'
		is_expected = 'workforce_scaled' if is_vineyards or is_anchorage else 'level_scaled'
		assert scaled_by == is_expected, 'scale type not matching, expected workforce_scaled'
		return 'poptype', 'employment', poptypes[m.group(1)]

	# Modifier: input/output goods.
	if m := re.fullmatch(r'(input|output)_(.+)_add', modifier_name):
		assert scaled_by == 'workforce_scaled', 'scale type not matching, expected unscaled'
		return 'goods', m.group(1), goods[m.group(2)]

	# Ignored modifier: mortality multiplier.
	if m := re.fullmatch(r'(.+)_mortality_mult', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching, expected unscaled'
		return 'poptype', 'mortality', poptypes[m.group(1)]

	# Ignored modifier: subsistence output.
	if m := re.fullmatch(r'subsistence_output_add', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching, expected unscaled'
		return 'subsistence_output', 'subsistence_output', 'subsistence_output'

	assert False, f'UNKNOWN MODIFIER'

# Returns a list with all the parent building groups of a building (building groups form a tree-like structure).
def get_bg_parents(building: Building) -> list[BuildingGroup]:
	bg_list = []
	bg: BuildingGroup = building.building_group
	bg_list.append(bg)
	while bg.parent_group:
		assert bg.category == bg.parent_group.category
		bg = bg.parent_group
		bg_list.append(bg)
	return bg_list


# Returns the top-level building group of a building: the group that does not have a parent group.
def get_top_level_bg(building: Building) -> BuildingGroup:
	return get_bg_parents(building)[-1]


# Determines a key for sorting the buildings.
def get_building_key(building: Building) -> int:
	building_category_order = ['urban', 'rural', 'development']
	bg: BuildingGroup = get_top_level_bg(building)
	assert set(building_category_order) == set(bg.category for bg in vic3game.parser.building_groups.values() if bg.category)
	return building_category_order.index(bg.category)


# Determines which buildings should be skipped from the output.
def should_add_building(building: Building):
	return not building.building_group.is_military and not building.building_group.name == 'bg_monuments'


def sanity_checks_building(building: Building):
	pm_list: list['ProductionMethod'] = building.production_methods
	pm_name_list: set[str] = set(pm.name for pm in pm_list)
	assert len(pm_name_list) == len(pm_list)
	pm_name_list_2 = {pm for pm_group in building.production_method_groups for pm in vic3game.parser.production_method_groups[pm_group].production_methods}
	assert pm_name_list == pm_name_list_2


# Returns the minimum era when a building can be built.
def get_building_era(building: Building) -> int:
	return min((tech.era for tech in building.required_technologies), default=0)


# Returns the minimum era when a PM can be built.
def get_pm_era(pm: ProductionMethod) -> int:
	def get_era(elem: ProductionMethod | Law) -> int:
		return max(
			min((tech.era for tech in elem.required_technologies), default=0),
			min((get_era(law) for law in elem.unlocking_laws), default=0)
		)
	return get_era(pm)


# Returns the list of economic laws under which the Investment Pool can be used to build the given building.
def get_investment_pool_laws(building: Building) -> list[Law]:
	bg_list = get_bg_parents(building)
	return [law for law in economic_laws for bg in law.build_from_investment_pool if bg in bg_list]


# Creates the rows of the body: one row per PM.
def create_output_rows() -> list[tuple[list[str], dict[str, dict[any, any]], str, list[Law]]]:
	rows = []
	for building in sorted(vic3game.parser.buildings.values(), key=get_building_key):
		top_level_bg = get_top_level_bg(building)

		sanity_checks_building(building)

		if not should_add_building(building):
			continue

		construction_cost: int = 0 if building.required_construction is None else building.required_construction
		investment_pool_laws = [] if construction_cost == 0 else get_investment_pool_laws(building)
		building_era = get_building_era(building)

		for pm_group_key in building.production_method_groups:
			pm_group: ProductionMethodGroup = vic3game.parser.production_method_groups[pm_group_key]

			# List of all the PMs in the group.
			pm_list: list[ProductionMethod] = [vic3game.parser.production_methods[pm_key] for pm_key in pm_group.production_methods]

			# Dictionary from pm_display_name -> pm.
			# If there are multiple PMs in the same group with the same display name, add indexes to them.
			# This happens e.g. in Shipyards (there are two PMs named Military Building).
			pm_dict: dict[str, list[ProductionMethod]] = defaultdict(list)
			for pm in pm_list:
				pm_dict[get_display_name(pm)].append(pm)
			pm_dict = {pm: (name if len(pms) == 1 else f'{name} [#{i + 1}]') for name, pms in pm_dict.items() for i, pm in enumerate(pms)}

			for pm in pm_list:
				# Parse the modifier names, organize them into types, and verify their scale type.
				parsed_modifiers: dict[str, dict[str, any]] = defaultdict(dict)
				for scaled_by, modifier_list in pm.building_modifiers.items():
					for modifier in modifier_list:
						try:
							kind, *rest = parse_modifier_name(pm, scaled_by, modifier.name)
						except Exception as exc:
							print(f'[{building.display_name} / {pm.display_name}] skipping {repr(scaled_by)} modifier {repr(modifier.name)}: {exc}', file=sys.stderr)
						else:
							if kind in {'goods', 'poptype'} and rest[0] in get_header_keys():
								key, item = rest
								assert item not in parsed_modifiers[key]
								assert type(modifier.value) in {int, float}
								parsed_modifiers[key][item] = modifier.value

				# Add workforce shares across all pop types.
				workforce_shares = parsed_modifiers['shares'].pop('workforce', 0)
				if workforce_shares:
					for pop_type in poptypes.values():
						parsed_modifiers['shares'][pop_type] = parsed_modifiers['shares'].get(pop_type, 0) + workforce_shares

				pm_era = get_pm_era(pm)
				era = max(building_era, pm_era)

				# Prepare the header of the row, with the names of the building, PM group and PM, etc.
				headers = [
					top_level_bg.category,
					get_display_name(top_level_bg),
					building.name,
					get_display_name(building),
					pm_group.name,
					get_display_name(pm_group),
					pm.name,
					pm_dict[pm],  # The list of PMs has size 1: its display name.
					construction_cost,
					building.building_group.is_government_funded,
					era
				]

				# Get the minting from the building's country modifiers.
				# country_modifiers: dictionary from modifier_name -> tuple[scaled_by, modifier].
				country_modifiers: dict[str, tuple[str, Modifier]] = {modifier.name: (scaled_by, modifier) for scaled_by, modifiers in pm.country_modifiers.items() for modifier in modifiers}
				minting: tuple[str, Modifier] = country_modifiers.get('country_minting_add')
				minting_value: str = minting[1].value if minting else ''

				# Add new row for the PM, with the headers, the PM's modifiers (i.e. input/output goods, employment, shares), the minting and the IP laws.
				rows.append((headers, dict(parsed_modifiers), minting_value, investment_pool_laws))
	return rows


# Determines the ordering of the columns that represent PM's modifiers.
def get_modifier_columns_order() -> list[list[any]]:
	goods_order = get_goods_order()
	pop_type_order = get_pop_types_order()
	pop_shares_order: list[str] = pop_type_order + ['government'] # Add a column for government shares.

	return [goods_order, goods_order, pop_type_order, pop_shares_order]


def get_subheader_label(subheader: any) -> str:
	if subheader == 'government':
		return 'Government'
	return get_display_name(subheader)


def print_headers(file) -> None:
	main_headers: list[str] = [
		'Category',
		'Top BG Display Name',
		'Building Name',
		'Building Display Name',
		'PMG Name',
		'PMG Display Name',
		'PM Name',
		'PM Display Name',
		'Construction Cost',
		'Government Funded',
		'Era',
		'#',
	]

	column_order: list[list[any]] = get_modifier_columns_order()

	# First header row, with the main headers.
	print(
		*main_headers,
		*(prefix + get_subheader_label(subheader).lower() for key_label, subheader_list in zip(get_header_key_labels(), column_order) for prefix, subheader in zip([key_label] * len(subheader_list), subheader_list)),
		'Minting',
		*(law.name for law in economic_laws),
		sep='\t',
		file=file)

	# Second header row, with the subheaders (good's names, etc).
	print(
		*('' for _ in main_headers),
		*(get_subheader_label(subheader) for subheader_list in column_order for subheader in subheader_list),
		'',  # Minting
		*(law.display_name for law in economic_laws),
		sep='\t',
		file=file)


def print_body(file) -> None:
	rows = create_output_rows()
	column_order: list[list[any]] = get_modifier_columns_order()
	for i, (header, modifiers, minting, investment_pool_laws) in enumerate(rows):
		print(
			*header,
			i+1,
			*(modifiers.get(key, {}).get(subheader, '') for key, subheader_list in zip(get_header_keys(), column_order) for subheader in subheader_list),
			minting,
			*map(lambda law: law in investment_pool_laws, economic_laws),
			sep='\t',
			file=file)


def print_production_method_data(dir_name: str) -> None:
	file_name = dir_name / "production_methods.txt"
	file = open(file_name, 'w')
	print_headers(file)
	print_body(file)



