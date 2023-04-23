import re
import ast


def sort_into_query_Dict(query_Dict, operation_Dict, term, level):
    first_operation = operation_Dict[[*operation_Dict.keys()][0]] if len(operation_Dict) != 0 else ('', level - 1)
    cur_operation = operation_Dict[[*operation_Dict.keys()][-1]] if len(operation_Dict) != 0 else ('', level - 1)

    if (cur_operation[1] - first_operation[1]) in [0, 1]:
        cur_operation = operation_Dict[[*operation_Dict.keys()][-1]]
        query_Dict[cur_operation[0]].append({term["matching_operator"]: {term["field"]: term["value"]}})
    else:
        raise ValueError("too nested!")

    return query_Dict


def parse_query(ori_string):
    query_dict = {}
    query_actions = {'must': 'and', 'must_not': 'not', 'should': 'or'}

    term = {"field": '', "value": "", "logical_operator": "", "matching_operator": "", "found": 0, "dict": {}}
    operation_dict = {}
    level = 0

    ori_string = re.sub(r"\s*\(", "(", ori_string)  # cleanup string
    ori_string = re.sub(r"''", "' '", ori_string)
    ori_string = re.sub(r'""', '" "', ori_string)
    ori_string = re.sub(r'\s*=\s*', '=', ori_string)
    ori_string = ori_string.strip()

    if ori_string.count('(') != ori_string.count(')'):
        print('mismatch: query seems to be invalid')
        raise ValueError("mismatch")

    while len(ori_string) > 0:
        position = {}
        term = {"field": '', "value": "", "logical_operator": "", "found": 0, "dict": {}}

        char_pos = ori_string.find('(')
        position[char_pos.__str__() if char_pos > -1 else ('_nv' + char_pos.__str__())] = {'char': "(", 'pos': char_pos}
        char_pos = ori_string.find(')')
        position[char_pos.__str__() if char_pos > -1 else ('_nv' + char_pos.__str__())] = {'char': ")", 'pos': char_pos}

        position = {k: v for k, v in position.items() if not k.startswith('_nv')}
        position = sorted(position.items())

        char_tpl = position.pop(0)
        char_tpl = char_tpl[1]

        if char_tpl['pos'] == 0 and char_tpl['char'] in ['(', ')']:  # special char at beginning
            if char_tpl['char'] == '(':
                level += 1
                ori_string = ori_string[1:]
                continue
            elif char_tpl['char'] == ')':
                level -= 1
                cur_operation = operation_dict[[*operation_dict.keys()][-1]] if len(operation_dict) != 0 else (
                    '', level - 1)
                if cur_operation[1] > level:
                    operation_dict.popitem()

            ori_string = ori_string[1:].strip()
            continue

        sub_string = ori_string[0:char_tpl['pos']]
        if sub_string in ['and', 'not', 'or']:
            if sub_string == 'or':
                operation = 'should'
            elif sub_string == 'not':
                operation = 'must_not'
            else:
                operation = 'filter'  # ignore scores for must (and)

            first_operation = operation_dict[[*operation_dict.keys()][0]] if len(operation_dict) != 0 else (
                '', level - 1)
            if (level - first_operation[1]) > 1:
                raise ValueError("too nested")
            else:
                operation_dict[sub_string + '_' + level.__str__()] = (operation, level)
                query_dict[operation_dict[sub_string + '_' + level.__str__()][0]] = []

        if sub_string.find('term') > -1:
            term['matching_operator'] = 'term'
            sub_string = sub_string[4:].strip()
            query_dict = deconstruct_constraint(level, operation_dict, query_dict, sub_string, term)
        elif sub_string.find('phrase') > -1:
            term['matching_operator'] = 'match_phrase'
            sub_string = sub_string[6:].strip()
            query_dict = deconstruct_constraint(level, operation_dict, query_dict, sub_string, term)

        ori_string = ori_string[char_tpl['pos']:]

    return query_dict


def deconstruct_constraint(level, operation_dict, query_dict, sub_string, term):
    if sub_string.find('field') == -1:
        raise ValueError("should contain field")
    sub_string = sub_string[5:].strip()
    if sub_string[0] == '=':
        term["logical_operator"] = '='
    sub_string = sub_string[1:].strip()
    if sub_string[0] in ['"', "'"]:
        enclose = sub_string[0]
        if (sub_string.count(enclose) % 2) == 0:
            sub_string = sub_string[1:]
            pos = sub_string.find(enclose)
    else:
        pos = sub_string.find(" ")
    term["field"] = sub_string[0:pos]
    term["value"] = sub_string[pos + 1:].strip()
    if term["value"][0] == term["value"][-1] and term["value"][0] in ["'", '"']:
        term["value"] = term["value"][1:-1]
    if term["value"] != "" and term["field"] != "":
        query_dict = sort_into_query_Dict(query_dict, operation_dict, term, level)
    return query_dict


def parse_facets(ori_string):
    filter_dict = {}
    parsed_dict = ast.literal_eval(ori_string.strip())  # doubles will be lost

    for k, v in parsed_dict.items():
        size = int(v["size"]) if 'size' in v.keys() else 10
        sort_way = list(v["sort"].keys())[0] if 'sort' in v.keys() and isinstance(v["sort"], dict) and \
                                                list(v["sort"].keys())[0] in ["count", "value"] else 'count'
        if sort_way == "count":
            sort_way = "_count"
        else:
            sort_way = "_key"
        sort_dir = v["sort"][list(v["sort"].keys())[0]] if 'sort' in v.keys() and isinstance(v["sort"], dict) and \
                                                           v["sort"][list(v["sort"].keys())[0]] in ["asc",
                                                                                                    "desc"] else 'desc'
        filter_dict[k] = {"terms": {"field": k + ".keyword", "size": size, "order": {sort_way: sort_dir}}}

    return filter_dict


def parse_aggregation(data):
    aggregation_dict = {}

    if 'aggregations' in data.keys():
        for k, v in data["aggregations"].items():
            if 'buckets' in v.keys():
                aggregation_dict[k] = {"buckets": []}
                for item in v["buckets"]:
                    aggregation_dict[k]["buckets"].append({"value": item["key"], "count": item["doc_count"]})

    return aggregation_dict
