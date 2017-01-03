#!/usr/bin/env python3

import sys
#sys.setrecursionlimit(50)
import yaml
import datetime
import itertools

class Period:
    def __init__(self, id_, name, begin, end):
        self._id = id_
        self._name = name
        self._begin = begin
        self._end = end
        self._conflictions = []

    def __str__(self):
        begin = datetime.datetime.fromtimestamp(
            self._begin, tz=datetime.timezone.utc).time().strftime('%T')
        end = datetime.datetime.fromtimestamp(
            self._end, tz=datetime.timezone.utc).time().strftime('%T')
        return '<Period: #%d, name=%s, time=%s-%s, confliction=%s>' % (
            self._id, self._name, begin, end, self._conflictions)


class Title:
    def __init__(self, id_, name):
        self._id = id_
        self._name = name
        self._staffs = set()

    def __str__(self):
        return '<Title: #%d, name=%s, staff=%s>' % (
            self._id, self._name, self._staffs)


class Staff:
    def __init__(self, id_, name, title):
        self._id = id_
        self._name = name
        self._titles = title

    def __str__(self):
        return '<Staff: #%d, name=%s, title=%s>' % (
            self._id, self._name, self._titles)

class DLX:
    def preprocess(self, constraints):
        def basic():
            self._begin = constraints['date-range'][0]
            self._end = constraints['date-range'][1]
            self._days = (self._end - self._begin).days + 1
            assert self._days % 7 == 0
            self._min_rest_time = constraints['min-rest-time'] * 60 * 60
            self._vacation = constraints['vacation']
            assert 0 <= self._vacation <= 7
            self._max_rest_gap = constraints['max-rest-gap']

        def period():
            self._periods = {}
            for p in constraints['period']:
                period = Period(p['id'], p['name'], p['begin'], p['end'])
                self._periods[period._id] = period
            for pid, p in self._periods.items():
                for cpid, cp in self._periods.items():
                    if 86400 + cp._begin - p._end < self._min_rest_time:
                        p._conflictions.append(cpid)

        def title():
            self._titles = {}
            for t in constraints['title']:
                title = Title(t['id'], t['name'])
                self._titles[title._id] = title

        def staff():
            self._staffs = {}
            for s in constraints['staff']:
                title = self._titles[s['title-id']]
                staff = Staff(s['id'], s['name'], title)
                self._staffs[staff._id] = staff
                title._staffs.add(staff._id)

        def staff_number():
            self._staff_numbers = {}
            for sn in constraints['staff-number']:
                assert sn['date-range'][0] >= self._begin
                assert sn['date-range'][1] <= self._end
                begin = (sn['date-range'][0] - self._begin).days
                end = (sn['date-range'][1] - self._begin).days + 1
                days = range(begin, end)
                periods = sn['period-id']
                if not isinstance(periods, list):
                    periods = [periods]
                titles = sn['title-id']
                if not isinstance(titles, list):
                    titles = [titles]
                for day in days:
                    for period in periods:
                        for title in titles:
                            key = (day, period, title)
                            self._staff_numbers[key] = sn['number-range']

        def prefer_period():
            self._prefer_periods = {}
            if 'prefer-period' not in constraints: return
            for pp in constraints['prefer-period']:
                assert self._begin \
                        <= pp['date-range'][0] \
                        <= pp['date-range'][1] \
                        <= self._end
                begin = (pp['date-range'][0] - self._begin).days
                end = (pp['date-range'][1] - self._begin).days + 1
                days = range(begin, end)
                staff = pp['staff-id']
                periods = pp['period-id']
                if not isinstance(periods, list):
                    periods = [periods]
                for day in days:
                    self._prefer_periods[(day, staff)] = periods

        def prefer_vacation():
            self._prefer_vacations = {}
            if 'prefer-vacation' not in constraints: return
            for pv in constraints['prefer-vacation']:
                staff = pv['staff-id']
                days = set()
                for day in pv['days']:
                    assert self._begin <= day <= self._end
                    offset = (day - self._begin).days
                    days.add(offset)
                self._prefer_vacations[staff] = days

        def partner():
            self._partners = {}
            if 'partner' not in constraints: return
            for p in constraints['partner']:
                assert p['date-range'][0] >= self._begin
                assert p['date-range'][1] <= self._end
                begin = (p['date-range'][0] - self._begin).days
                end = (p['date-range'][1] - self._begin).days + 1
                days = range(begin, end)
                staffs = p['staff-id']
                assert len(staffs) > 1

        def confliction():
            self._conflictions = {}

        basic()
        period()
        title()
        staff()
        staff_number()
        prefer_period()
        prefer_vacation()
        partner()
        confliction()

        #for p in self._periods.values():
        #    print(p)
        #for t in self._titles.values():
        #    print(t)
        #for s in self._staffs.values():
        #    print(s)
        #for sn in self._staff_numbers.items():
        #    print(sn)
        #for pp in self._prefer_periods.items():
        #    print(pp)
        #for pv in self._prefer_vacations.items():
        #    print(pv)

    class Node:
        def __init__(self):
            self._left = self
            self._right = self
            self._up = self
            self._down = self

        def appendToRow(self, row):
            self._row = row
            self._left = row._left
            self._right = row
            row._left._right = self
            row._left = self

        def appendToColumn(self, col):
            self._col = col
            self._up = col._up
            self._down = col
            col._up._down = self
            col._up = self
            col._count += 1

        def unlinkInRow(self):
            self._left._right = self._right
            self._right._left = self._left

        def unlinkInColumn(self):
            self._up._down = self._down
            self._down._up = self._up
            self._col._count -= 1

        def relinkInRow(self):
            self._left._right = self
            self._right._left = self

        def relinkInColumn(self):
            self._up._down = self
            self._down._up = self
            self._col._count += 1

        def iterInRow(self):
            node = self._right
            while node != self:
                yield node
                node = node._right

        def iterInColumn(self):
            node = self._down
            while node != self:
                yield node
                node = node._down

    def createRoot(self):
        self._root = DLX.Node()
        self._root._row = self._root
        self._root._col = self._root
        self._root._count = 0
        return self._root

    def createRow(self, symbol):
        row = DLX.Node()
        row._row = row
        row.appendToColumn(self._root)
        row._symbol = symbol
        return row

    def createColumn(self):
        col = DLX.Node()
        col._col = col
        col._count = 0
        col.appendToRow(self._root)
        return col

    def addNode(self, row, col):
        node = DLX.Node()
        node.appendToRow(row)
        node.appendToColumn(col)
        return node

    def createArrangementColumns(self):
        self._arrangement_cols = {}
        for day in range(self._days):
            for staff in self._staffs:
                self._arrangement_cols[(day, staff)] = self.createColumn()

    def createVacationColumns(self):
        self._vacation_cols = {}
        if self._vacation <= 0: return
        for week in range(self._days // 7):
            for staff in self._staffs:
                self._vacation_cols[(week, staff)] = self.createColumn()

    def createPeriodColumns(self):
        self._period_cols = {}
        for day in range(self._days):
            for period in self._periods:
                for title in self._titles:
                    key = (day, period, title)
                    if key not in self._staff_numbers: continue
                    number = self._staff_numbers[key][0]
                    if number <= 0: continue
                    self._period_cols[key] = self.createColumn()

    def createPreferColumns(self):
        self._prefer_cols = {}
        for day, staff in self._prefer_periods:
            self._prefer_cols[(day, staff)] = self.createColumn()

    def createVacationRows(self):
        self._vacation_rows = {}
        if self._vacation <= 0: return
        for week in range(self._days // 7):
            for staff in self._staffs:
                prefers = set(filter(lambda day: week * 7 <= day < (week + 1) * 7,
                                     self._prefer_vacations.get(staff, [])))
                for weekdays in itertools.combinations(range(7), self._vacation):
                    days = set(map(lambda day: week * 7 + day, weekdays))
                    if not prefers.issubset(days): continue
                    key = (week, staff, tuple(sorted(days)))
                    symbol = ('vacation', *key)
                    row = self.createRow(symbol)
                    self._vacation_rows[key] = row
                    for day in days:
                        col = self._arrangement_cols[(day, staff)]
                        self.addNode(row, col)
                        if (day, staff) in self._prefer_periods:
                            col = self._prefer_cols[(day, staff)]
                            self.addNode(row, col)
                    col = self._vacation_cols[(week, staff)]
                    self.addNode(row, col)

    def createArrangementRows(self):
        self._arrangement_rows = {}
        if self._vacation >= 7: return
        for day in range(self._days):
            for period in self._periods:
                for title in self._titles:
                    key = (day, period, title)
                    if key not in self._staff_numbers: continue
                    number_range = self._staff_numbers[key]
                    available_staffs = self._titles[title]._staffs
                    for number in range(number_range[0], number_range[1] + 1):
                        for staffs in map(set,
                                          itertools.combinations(available_staffs,
                                                                 number)):
                            key = (day, period, title, tuple(sorted(staffs)))
                            symbol = ('arrangement', *key)
                            row = self.createRow(symbol)
                            self._arrangement_rows[key] = row
                            for staff in staffs:
                                col = self._arrangement_cols[(day, staff)]
                                self.addNode(row, col)
                                if ((day, staff) in self._prefer_periods and
                                    period in self._prefer_periods[(day, staff)]):
                                    col = self._prefer_cols[(day, staff)]
                                    self.addNode(row, col)
                            col = self._period_cols[(day, period, title)]
                            self.addNode(row, col)


    def __init__(self, constraints):
        self.preprocess(constraints)
        self.createRoot()
        self.createArrangementColumns()
        self.createVacationColumns()
        self.createPeriodColumns()
        self.createPreferColumns()
        print('columns: %d' % sum([len(self._arrangement_cols),
                                   len(self._vacation_cols),
                                   len(self._period_cols),
                                   len(self._prefer_cols)]))
        self.createVacationRows()
        self.createArrangementRows()
        print('rows: %d' % sum([len(self._vacation_rows),
                                len(self._arrangement_rows)]))
        print([node._count for node in self._root.iterInRow()])
        self._solution = []

    def solve(self):
        def cover(col):
            col.unlinkInRow()
            for row in col.iterInColumn():
                for node in row.iterInRow():
                    node.unlinkInColumn()

        def resume(col):
            for row in reversed(list(col.iterInColumn())):
                for node in reversed(list(row.iterInRow())):
                    node.relinkInColumn()
            col.relinkInRow()

        #print([col._count for col in self._root.iterInRow()])
        if self._root._right == self._root: return True
        selected = min(self._root.iterInRow(), key=lambda col: col._count)
        #print('%s: %d' % (selected, selected._count))
        cover(selected)
        for row in selected.iterInColumn():
            self._solution.append(row._row._symbol)
            for node in row.iterInRow():
                if node._row == node: continue
                cover(node._col)
            if self.solve(): return True
            for node in reversed(list(row.iterInRow())):
                if node._row == node: continue
                resume(node._col)
            self._solution.pop()
        resume(selected)
        return False

    def outputSolution(self, filename):
        table = []
        header = [''] + list(map(str, [self._begin + datetime.timedelta(days=day)
                                       for day in range(self._days)]))
        table.append(header)
        staff_row = {}
        for sid, staff in self._staffs.items():
            row = [staff._name] + [''] * self._days
            table.append(row)
            staff_row[staff._id] = len(table) - 1
        for symbol in self._solution:
            if symbol[0] == 'arrangement':
                _, day, pid, _, staffs = symbol
                period = self._periods[pid]._name
                for staff in staffs:
                    row = staff_row[staff]
                    table[row][day + 1] = period
            if symbol[0] == 'vacation':
                _, _, staff, days = symbol
                row = staff_row[staff]
                for day in days:
                    table[row][day + 1] = '公休'
        open(filename, 'w').writelines(','.join(row) + '\n' for row in table)


if __name__ == '__main__':
    filename = 'schedule.yaml'
    constraints = yaml.load(open(filename))
    #print(constraints)
    solver = DLX(constraints)
    if not solver.solve():
        print('no solution')
        sys.exit(0)
    solver.outputSolution('solution.csv')
