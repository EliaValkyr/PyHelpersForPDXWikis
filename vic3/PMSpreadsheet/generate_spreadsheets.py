from vic3.PMSpreadsheet.pm_spreadsheet import print_production_method_data
from PyHelpersForPDXWikis.localsettings import OUTPATH
from vic3.game import vic3game

outpath = OUTPATH / vic3game.short_game_name / vic3game.version / "Spreadsheets"
print_production_method_data(outpath)
