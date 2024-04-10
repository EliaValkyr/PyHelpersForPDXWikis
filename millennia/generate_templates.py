import sys
from itertools import groupby
from operator import attrgetter

from millennia.game import MillenniaFileGenerator


class TemplateGenerator(MillenniaFileGenerator):

    def create_html_list(self, elements, no_list_with_one_element=False):
        if len(elements) == 0 or elements == [[]]:
            return ''
        elif len(elements) == 1 and no_list_with_one_element:
            return elements[0]
        else:
            results = []
            for element in elements:
                if isinstance(element, list):
                    element = self.create_html_list(element, no_list_with_one_element)
                elif not isinstance(element, str):
                    element = str(element)
                results.append(f'<li>{element}</li>')
            return f'<ul>{"".join(results)}</ul>'

    def generate_technology_template(self, group_results=False):
        grouped_results = {}
        list_results = ['<includeonly>{{#switch:{{padleft:|1|{{lc:{{{2}}}}}}}']
        # result = ['<includeonly>{{#switch:{{lc:{{{2}}}}}']
        # current_first_letter = None
        default_case = '| #default = <span style="color: red; font-size: 11px;">(unrecognized string “{{{2}}}” for [[Template:Technology]])</span>[[Category:Pages with unrecognized template strings]]'
        for first_letter, techs in groupby(sorted(self.parser.technologies.values(), key=attrgetter('display_name')), key=lambda tech: tech.display_name[0].lower()):
            # print(first_letter, ', '.join([t.display_name for t in techs]))
            # exit()
            # print(first_letter, len([tech for tech in techs if not tech.is_age_advance]))
            # continue
            result = []
            result.append(f'|{first_letter} = ' + '{{#switch:{{lc:{{{2}}}}}')
            for tech in techs:
                if tech.is_age_advance:
                    continue
                result.append(f'| {tech.display_name.lower()} = {{{{Technology/{{{{{{1}}}}}}')
                data = self.get_tech_data(tech)
                for parameter, value in data.items():
                    result.append(f'|{parameter}= {value}')
                result.append('}}')
            result.append(default_case)
            result.append('}}')
            list_results.extend(result)
            grouped_results[first_letter] = result
        list_results.append(default_case)
        list_results.append('}}</includeonly><noinclude>{{template doc}}')
        list_results.append("""
== test ==
* a
*b
*c
*d
*e
*f
*g
*h
*i
*j
*k
*l

""")
        list_results.append('[[Category:Templates]]</noinclude>')
        if group_results:
            return grouped_results
        else:
            return list_results

    def generate_technology_template_all_in_one(self):
        # result = []
        techs = sorted(self.parser.technologies.values(), key=attrgetter('name'))
        result = ['<includeonly>{{#switch:{{{1}}}']
        default_case = '| #default = <span style="color: red; font-size: 11px;">(unrecognized string “{{{1}}}” for [[Template:Technology]])</span>[[Category:Pages with unrecognized template strings]]'
        for tech in techs:
            if tech.is_age_advance:
                continue
            data = self.get_tech_data(tech)
            text = '<div class="tooltip">[[File:Technology %s.png|24px|link=%s]] %s' % (data['name'], data['name'], data['name'])
            text += '<div class="tooltiptext" style="color: #A2A2A3; background: linear-gradient(to bottom, #0e111d,#172333); border: solid #7C582C; border-radius: 10px; width: 350px; padding: 5px;">'
            text += '<div style="float:left; margin-right: 5px;">[[File:Technology %s.png|48px]]</div><div><span style="color: #499fc1;">\'\'\'%s\'\'\'</span><br>' %( data['name'], data['name'])
            text += 'Base cost: <span style="color: #499fc1;>[[File:Resource knowledge.png|Knowledge|24px]] \'\'\'%d\'\'\'</span></div>' % data['cost']
            text += '<hr style="border-top: 1px solid #8a7f7a;"><span class="plainlist">%s</span>' % data['effects']
            text += '<span class="plainlist">Requires%s</span>' % data['age']
            text += '</div></div>'
            result.append(f'| {tech.display_name} = {text}')
        result.append(default_case)
        result.append('}}</includeonly><noinclude>{{template doc}}')
        result.append('[[Category:Templates]]</noinclude>')
        return result

    @staticmethod
    def escape_lua_string(string: str):
        """incomplete. only replaces backslashes and quotes and newlines for now"""
        replacements = {
            '\\': '\\\\',
            '"': '\\"',
            "'": "\\'",
            '\n': '<br>',
        }
        for old, new in replacements.items():
            string = string.replace(old, new)
        return string

    def generate_technology_module(self):
        result = ['''local p = {
    techs = {}
}
local techs = p.techs
''']
        for tech in sorted(self.parser.technologies.values(), key=attrgetter('name')):
            if tech.is_age_advance:
                continue
            data = self.get_tech_data(tech)
            parameters = [f'{parameter} = {value}' if isinstance(value, int) else f'{parameter} = "{self.escape_lua_string(value)}"' for parameter, value in data.items()]
            result.append(f'techs["{tech.display_name}"] = {{{", ".join(parameters)}}}')
        result.append('')
        result.append('return p')
        return result

    def get_tech_data(self, tech):
        data = {
            'name': tech.display_name,
            'effects': (f'Effects:{self.create_html_list([tech.other_effects])}' if tech.other_effects else '') +
                       (
                           f'Unlocks:{self.create_html_list([tech.get_unlock_list()])}'),
            'age': (f':' if len(tech.ages) == 1 else f'&nbsp;any of:') + self.create_html_list([[age.get_wiki_link_with_icon() for age in tech.ages]]),
            'cost': tech.cost,
        }
        return data


if __name__ == '__main__':
    generator = TemplateGenerator()
    generator.run(sys.argv)
