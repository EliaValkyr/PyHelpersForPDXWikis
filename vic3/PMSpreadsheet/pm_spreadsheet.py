from collections import defaultdict
import re
import sys

from vic3.PMSpreadsheet.goods_spreadsheet import get_goods_order
from vic3.game import vic3game
from vic3.vic3lib import Building, BuildingGroup, ProductionMethod, ProductionMethodGroup, PopType, Good, Modifier

goods: dict[str, Good] = vic3game.parser.goods
poptypes: dict[str, PopType] = vic3game.parser.pop_types


def get_header_keys() -> list[str]:
	return ['input', 'output', 'employment', 'shares']


def get_header_key_labels() -> list[str]:
	return ['Input goods', 'Output goods', 'Employment', 'Shares']


# Returns the display name of an item (building, PM, good, etc.) after resolving all the nested localizations.
def get_display_name(elem) -> str:
	# recursively resolve $nested$ localizations
	text = vic3game.parser.formatter.resolve_nested_localizations(elem.display_name)
	# delete @icon! references
	return ' '.join(re.sub(r'@([^!]*)!', '', text).split())


# Parses the modifier name, and decomposes it in three parts.
def parse_modifier_name(pm: ProductionMethod, scaled_by: str, modifier_name: str) -> tuple[str, str, {str, PopType, Good}]:
	# Remove common elements from the modifier name. Currently, all modifiers start with "building_".
	m = re.fullmatch(r'building_(.+)', modifier_name)
	assert m, f'UNKNOWN MODIFIER'
	modifier_name = m.group(1)

	# try the various types we know of

	# Modifier: pop type shares.
	if m := re.fullmatch(r'(.+)_shares_add', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching'
		return 'poptype', 'shares', m.group(1) if m.group(1) in {'government', 'workforce'} else poptypes[m.group(1)]

	# Modifier: pop type employment.
	if m := re.fullmatch(r'employment_(.+)_add', modifier_name):
		# For some reason, these PMs have workforce_scaled employment modifiers, instead of level_scaled.
		is_vineyards = pm.name == 'pm_vineyards' or pm.name.startswith('pm_vineyards_building_')
		is_anchorage = pm.name == 'pm_anchorage'
		is_expected = 'workforce_scaled' if is_vineyards or is_anchorage else 'level_scaled'
		assert scaled_by == is_expected, 'scale type not matching'
		return 'poptype', 'employment', poptypes[m.group(1)]

	# Modifier: input/output goods.
	if m := re.fullmatch(r'(input|output)_(.+)_add', modifier_name):
		# For some reason, these PMs have unscaled goods modifiers, instead of workforce_scaled.
		is_no_home_workshops = pm.name.startswith('pm_home_workshops_no_building_')
		is_expected = 'unscaled' if is_no_home_workshops else 'workforce_scaled'
		assert scaled_by == is_expected, 'scale type not matching'
		return 'goods', m.group(1), goods[m.group(2)]

	# Ignored modifier: mortality multiplier.
	if m := re.fullmatch(r'(.+)_mortality_mult', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching'
		return 'poptype', 'mortality', poptypes[m.group(1)]

	# Ignored modifier: subsistence output.
	if m := re.fullmatch(r'subsistence_output_add', modifier_name):
		assert scaled_by == 'unscaled', 'scale type not matching'
		return 'subsistence_output', 'subsistence_output', 'subsistence_output'

	assert False, f'UNKNOWN MODIFIER'


# determine row order

building_category_order = ['urban', 'rural', 'development']
assert set(building_category_order) == set(bg.category for bg in vic3game.parser.building_groups.values() if bg.category)

bg_index = {k: i for i, k in enumerate(vic3game.parser.building_groups)}


def get_top_level_bg(building: Building) -> BuildingGroup:
	bg: BuildingGroup = building.building_group
	while bg.parent_group:
		assert bg.category == bg.parent_group.category
		bg = bg.parent_group
	return bg


def get_building_key(building: Building) -> int:
	bg: BuildingGroup = get_top_level_bg(building)
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


# collect rows (one per PM)
def create_output_rows() -> list[tuple[list[str], dict[str, dict[any, any]], str]]:
	rows = []
	for building in sorted(vic3game.parser.buildings.values(), key=get_building_key):
		top_level_bg = get_top_level_bg(building)

		sanity_checks_building(building)

		if not should_add_building(building):
			continue

		construction_cost: int = 0 if building.required_construction is None else building.required_construction

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
				]

				# Get the minting from the building's country modifiers.
				# country_modifiers: dictionary from modifier_name -> tuple[scaled_by, modifier].
				country_modifiers: dict[str, tuple[str, Modifier]] = {modifier.name: (scaled_by, modifier) for scaled_by, modifiers in pm.country_modifiers.items() for modifier in modifiers}
				minting: tuple[str, Modifier] = country_modifiers.get('country_minting_add')
				minting_value: str = minting[1].value if minting else ''

				# Add new row for the PM, with the headers, the PM's modifiers (i.e. input/output goods, employment, shares), and the minting.
				rows.append((headers, dict(parsed_modifiers), minting_value))
	return rows


# Determines the ordering of the columns that represent PM's modifiers.
def get_modifier_columns_order() -> list[list[any]]:
	goods_order = get_goods_order()

	# Sort pop types by strata, then by file order.
	pop_type_strata_order: list[str] = ['poor', 'middle', 'rich']
	assert set(pop_type.strata for pop_type in poptypes.values()) == set(pop_type_strata_order)
	pop_type_order: list[PopType] = [pop_type for strata in pop_type_strata_order for pop_type in poptypes.values() if pop_type.strata == strata]
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
		'#',
	]

	column_order: list[list[any]] = get_modifier_columns_order()

	# First header row, with the main headers.
	print(
		*main_headers,
		*(header for key_label, subheader_list in zip(get_header_key_labels(), column_order) for header in [key_label, *('' for _ in range(len(subheader_list)-1))]),
		'Minting',
		sep='\t',
		file=file)

	# Second header row, with the subheaders (good's names, etc).
	print(
		*('' for _ in main_headers),
		*(get_subheader_label(subheader) for subheader_list in column_order for subheader in subheader_list),
		'',  # Minting
		sep='\t',
		file=file)


def print_body(file) -> None:
	rows = create_output_rows()
	column_order: list[list[any]] = get_modifier_columns_order()
	for i, (header, modifiers, minting) in enumerate(rows):
		print(
			*header,
			i+1,
			*(modifiers.get(key, {}).get(subheader, '') for key, subheader_list in zip(get_header_keys(), column_order) for subheader in subheader_list),
			minting,
			sep='\t',
			file=file)


def print_production_method_data(dir_name: str) -> None:
	file_name = dir_name / "production_methods.txt"
	file = open(file_name, 'w')
	print_headers(file)
	print_body(file)



