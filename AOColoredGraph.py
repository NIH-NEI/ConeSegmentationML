import datetime

class Rule:
    Item = None
    Other = None
    Stringified = None

    def __init__(self, item, other, stringified, rule_num):
        self.Item = item
        self.Other = other
        self.Stringified = stringified
        self.RuleNum = rule_num

    def __eq__(self, another):
        return hasattr(another, 'Item') and \
               hasattr(another, 'Other') and \
               self.Item == another.Item and \
               self.Other == another.Other

    def __hash__(self):
        return hash(self.Item) * self.RuleNum ^ hash(self.Other)

    def __str__(self):
        return self.Stringified


def buildLookup(items):
    itemToIndex = {}
    index = 0
    for key in sorted(items):
        itemToIndex[key] = index
        index += 1
    return itemToIndex


def buildRules(items, rule_num):
    itemToIndex = buildLookup(items.keys())
    rulesAdded = {}
    rules = []
    keys = sorted(list(items.keys()))

    for key in sorted(items.keys()):
        keyIndex = itemToIndex[key]
        adjacentKeys = items[key]
        for adjacentKey in adjacentKeys:
            if adjacentKey == '':
                continue
            adjacentIndex = itemToIndex[adjacentKey]
            temp = keyIndex
            if adjacentIndex < temp:
                temp, adjacentIndex = adjacentIndex, temp
            ruleKey = keys[temp] + "->" + keys[adjacentIndex]
            rule = Rule(temp, adjacentIndex, ruleKey, rule_num)
            if rule in rulesAdded:
                rulesAdded[rule] += 1
            else:
                rulesAdded[rule] = 1
                rules.append(rule)

    for k, v in rulesAdded.items():
        if v == 1:
            print("rule %s is not bidirectional" % k)

    return rules

def display(candidate, startTime):
    timeDiff = datetime.datetime.now() - startTime
    print("%s\t%i\t%s" % (''.join(map(str, candidate.Genes)), candidate.Fitness, str(timeDiff)))


def getFitness(candidate, rules):
    rulesThatPass = 0
    for rule in rules:
        if candidate[rule.Item] != candidate[rule.Other]:
            rulesThatPass += 1

    return rulesThatPass