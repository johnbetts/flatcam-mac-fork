# ##########################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# Snapmaker Artisan CNC preprocessor                       #
# Inherits from Marlin and prepends the Luban-required     #
# ;header_type: cnc header so Luban does not warn about    #
# inconsistent job type when loading the G-code file.      #
# MIT Licence                                              #
# ##########################################################

from preprocessors.Marlin import Marlin


class Snapmaker_Artisan(Marlin):

	def start_code(self, p):
		xmin = '%.*f' % (p.coords_decimals, p['options']['xmin'])
		xmax = '%.*f' % (p.coords_decimals, p['options']['xmax'])
		ymin = '%.*f' % (p.coords_decimals, p['options']['ymin'])
		ymax = '%.*f' % (p.coords_decimals, p['options']['ymax'])

		# Luban reads these header comments to identify the job type.
		# Without header_type: cnc, Luban warns that the file is inconsistent
		# with the CNC toolhead and shows the "Inconsistent Job Type" dialog.
		luban_header = (
			';Header Start\n'
			';header_type: cnc\n'
			';min_x(mm): {xmin}\n'
			';max_x(mm): {xmax}\n'
			';min_y(mm): {ymin}\n'
			';max_y(mm): {ymax}\n'
			';Header End\n'
		).format(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)

		return luban_header + Marlin.start_code(self, p)
