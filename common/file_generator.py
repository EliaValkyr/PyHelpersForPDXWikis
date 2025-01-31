import inspect
import sys
from common.paradox_lib import Game
from pyradox.filetype.table import make_table, WikiDialect


try:  # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import OUTPATH
except:  # when used by ck2utils
    from localpaths import outpath
    OUTPATH = outpath

class FileGenerator:

    def __init__(self, game: Game):
        self.game = game
        self.parser = game.parser

        self.outpath = OUTPATH / game.short_game_name / game.version
        if not self.outpath.exists():
            self.outpath.mkdir(parents=True)

    def run(self, command_line_args):
        """call all generators which were specified on the command line or all if none were specified"""
        if len(command_line_args) > 1:
            for arg in command_line_args[1:]:
                method_name = 'generate_' + arg
                if hasattr(self, method_name):
                    self._write_text_file(arg, getattr(self, method_name)())
                else:
                    print('Method {} not found in {}'.format(method_name, self.__class__.__name__))
        else:
            for method_name, method in inspect.getmembers(self):
                if method_name.startswith('generate_'):
                    if len(inspect.signature(method).parameters) == 0:  # skip functions which require a parameter
                        self._write_text_file(method_name.removeprefix('generate_'), method())

    def _write_text_file(self, name: str, content: str | list | dict):
        if isinstance(content, dict):
            for name_suffix, data in content.items():
                self._really_write_file(f'{name}_{name_suffix}', data)
        elif isinstance(content, list):
            self._really_write_file(name, '\n'.join(content))
        else:
            self._really_write_file(name, content)

    def _really_write_file(self, name: str, content: str):
        output_file = self.outpath / '{}{}.txt'.format(self.game.short_game_name, name)
        with output_file.open('w') as f:
            f.write(content)

    def _write_lines_to_text_file(self, name: str, lines: list[str]):
        self._write_text_file(name, '\n'.join(lines))

    def make_wiki_table(self, data, column_specs=None, table_style='', sortable=True, one_line_per_cell=False,
                        merge_identical_cells_in_column=False, remove_empty_columns=False, row_id_key=None, **kwargs):
        class dialect(WikiDialect):
            pass
        dialect.row_cell_begin = lambda s: ''

        if one_line_per_cell:
            dialect.row_cell_delimiter = '\n|'
        else:
            dialect.row_cell_delimiter = ' || '

        if row_id_key is None:
            dialect.row_begin = '| '
            dialect.row_delimiter = '|-\n'
        else:
            dialect.row_begin = lambda row: f'|- id="{row[row_id_key]}"\n| '
            dialect.row_delimiter = '\n'

        if remove_empty_columns:
            for key in list(data[0].keys()):
                is_empty = True
                for row in data:
                    if row[key].strip() != '':
                        is_empty = False
                        break
                if is_empty:
                    for row in data:
                        del row[key]

        if column_specs is None:
            column_specs = self.get_column_specs(data, row_id_key)

        if isinstance(data, list):
            data = dict(zip(range(len(data)), data))

        if merge_identical_cells_in_column:
            row_count = len(data)
            for i in range(row_count - 1):
                for key, column_spec in column_specs:
                    if key in data[i]:
                        same_rows = 0
                        while i+same_rows+1<row_count and data[i][key] == data[i+same_rows+1][key]:
                            del data[i+same_rows+1][key]
                            same_rows += 1
                        if same_rows > 0:
                            data[i][key] = f'rowspan="{same_rows+1}" | {data[i][key]}'

        return make_table(data, dialect, column_specs=column_specs, table_style=table_style, sortable=sortable, **kwargs)

    @staticmethod
    def get_column_specs(data, row_id_key=None):
        """generate a simple column specs for the table generator. All keys of the data array are used as table headers"""
        return [(k, '%%(%s)s' % k) for k in data[0].keys() if k != row_id_key]

    @staticmethod
    def warn(message: str):
        print('WARNING: {}'.format(message), file=sys.stderr)

    def get_SVersion_header(self, scope=None):
        """generate a SVersion wiki template for the current version

        for example {{SVersion|1.33}}

        @param scope a string which is used as the second parameter to the template
        @see https://eu4.paradoxwikis.com/Template:SVersion
        """
        version_header = '{{SVersion|' + self.game.major_version
        if scope:
            version_header += '|' + scope
        version_header += '}}'
        return version_header

    def get_version_header(self):
        """generate a Version wiki template for the current version

        for example {{Version|1.33}}
        """
        return '{{Version|' + self.game.major_version + '}}'