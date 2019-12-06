import pandas as pd
import datetime

import sasoptpy as so
from swat import CAS
from collections import namedtuple

import os

supplier = 'R2R'


def prep_data(car_type='diesel'):

    # Data in this repository is randomly populated, original data is provided by Rome2Rio.com
    travel_data = pd.read_csv('../data/all_methods_random.csv')

    def get_emission(row):
        if car_type == 'diesel':
            row['emission'] = 180.78 * row['flight'] +\
                              170.61 / 2 * row['car'] +\
                              27.79 * row['bus'] +\
                              112.86 * row['ferry'] +\
                              5.97 * row['train']
        else:
            row['emission'] = 180.78 * row['flight'] + \
                              5.76 / 2 * row['car'] + \
                              27.79 * row['bus'] + \
                              112.86 * row['ferry'] + \
                              5.97 * row['train']
        return row

    travel_data = travel_data.apply(lambda i: get_emission(i), axis=1).dropna(subset=['emission'])
    # Drop rows with missing data
    travel_data = travel_data[travel_data.price_low != ''].copy()
    travel_data = travel_data[travel_data.method != ''].copy()

    def get_avg_price(r):
        low = int(r.price_low.strip('$').replace(',', ''))
        high = int(r.price_high.strip('$').replace(',', ''))
        return (low+high)/2
    travel_data['cost'] = travel_data.apply(lambda i: get_avg_price(i), axis=1)

    travel_data.set_index(['city_x', 'city_y', 'method'], inplace=True)
    travel_info = travel_data

    arcs = pd.read_pickle('../data/arcs.p')
    arcs = arcs.set_index(['city_x', 'city_y', 'date_x', 'date_y'])

    def evaluate_arc_feasibility(arc):
        if arc.dt_x + datetime.timedelta(hours=2) <= arc.dt_y:
            arc['feasible'] = True
        else:
            arc['feasible'] = False
        return arc

    arcs = arcs.apply(evaluate_arc_feasibility, axis=1)
    arcs = arcs[arcs['feasible']].copy()

    games = pd.read_excel('../data/games_filled.xlsx')
    games['dt'] = games.apply(lambda i: datetime.datetime.combine(i['date'], i['time']), axis=1)
    games['ts'] = games['dt'].apply(lambda i: float(i.timestamp()))
    games = games.set_index('id')

    return games, arcs, travel_info


def solve_problem(objective, options=None):
    if options is None:
        options = dict()

    car_type = options.get('car_type', 'diesel')
    day_limit = options.get('day_limit', None)
    emission_limit = options.get('emission_limit', None)
    cost_limit = options.get('cost_limit', None)

    print('Connecting to CAS')
    hostname = os.getenv('CASHOST')
    port = os.getenv('CASPORT')
    cas = CAS(hostname, port)
    m = so.Model(name='european_trip_2020', session=cas)

    print('Parsing data')
    game_data, arcs_data, travel_data = prep_data(car_type)
    source = 0
    sink = 999

    GAMES = list(range(1, 52))
    RAW_ARCS = [(i.id_x, i.id_y) for i in arcs_data.itertuples()]
    ARCS = [(source, g) for g in GAMES] + [(g, sink) for g in GAMES] + RAW_ARCS
    CITIES = list(game_data['city'].unique())
    CONNECTION = [(city1, city2, method)
                  for city1 in CITIES for city2 in CITIES
                  if city1 != city2
                  for method in travel_data.loc[(city1, city2)].index]

    game_city = game_data['city'].to_dict()
    method_dict = travel_data.reset_index().groupby(['city_x', 'city_y']).apply(
        lambda i: i.method.to_list()).to_dict()

    use_arc = m.add_variables(ARCS, name='use_arc', vartype=so.BIN)
    use_method = m.add_variables(CONNECTION, name='use_method', vartype=so.BIN)

    total_emission = so.quick_sum(travel_data.loc[i].emission * use_method[i]
                                  for i in CONNECTION)
    total_trip_time = \
        so.quick_sum(
            use_arc[g, sink] * game_data.loc[g]['ts'] for g in GAMES) - \
        so.quick_sum(
            use_arc[source, g] * game_data.loc[g]['ts'] for g in GAMES)
    total_duration = so.quick_sum(
        travel_data.loc[i].duration.total_seconds() * use_method[i]
        for i in CONNECTION)
    total_km = so.quick_sum(
        travel_data.loc[i].car * use_method[i] for i in CONNECTION)

    total_expense = so.quick_sum(
        travel_data.loc[i].cost * use_method[i] for i in CONNECTION)

    if objective == 'least_emission':
        m.set_objective(total_emission, name='total_emission', sense=so.MIN)
    elif objective == 'shortest_tour':
        # Total trip time
        m.set_objective(total_trip_time, name='total_trip_time', sense=so.MIN)
    elif objective == 'total_duration':
        m.set_objective(total_duration, name='total_duration', sense=so.MIN)
    elif objective == 'total_km':
        m.set_objective(total_km, name='total_km', sense=so.MIN)
    elif objective == 'least_expensive':
        m.set_objective(total_expense, name='total_expense', sense=so.MIN)

    # Balance constraints
    m.add_constraints(
        (so.quick_sum(use_arc[g1, g] for (g1, g2) in ARCS if g2 == g) -
         so.quick_sum(use_arc[g, g2] for (g1, g2) in ARCS if g1 == g) ==
         (-1 if g == source else (1 if g == sink else 0))
         for g in GAMES + [source, sink]), name='balance'
    )

    # Visit each city once
    m.add_constraints(
        (so.quick_sum(use_arc[g1, g2] for (g1, g2) in ARCS
                      if g1 != source and game_data.loc[g1]['city'] == CITIES[i])
         == 1 for i in range(12)), name='visit')

    # Must use a travel method
    m.add_constraints(
        (so.quick_sum(
             use_method[game_data.loc[i].city, game_data.loc[j].city, method]
             for method in travel_data.loc[(game_data.loc[i].city, game_data.loc[j].city)].index.to_list()
         ) == 1 * use_arc[i, j] for (i, j) in RAW_ARCS
         if game_data.loc[i].city != game_data.loc[j].city), name='travel_method'
    )

    # Catch game before it starts
    m.add_constraints((
        so.quick_sum(
            use_method[game_city[i], game_city[j], k] * travel_data.loc[game_city[i], game_city[j], k].duration.total_seconds() for k in method_dict[game_city[i], game_city[j]]
        ) + datetime.timedelta(hours=4).total_seconds() * use_arc[i, j]
        <= (game_data.loc[j, 'dt'] - game_data.loc[i, 'dt']).total_seconds()
        for (i, j) in RAW_ARCS), name='catch_game'
    )

    # Day limit
    if day_limit:
        second_limit = datetime.timedelta(days=day_limit).total_seconds()
        m.add_constraint(total_trip_time <= second_limit, name='time_limit')

    if emission_limit:
        m.add_constraint(total_emission <= emission_limit, name='emission_limit')

    if cost_limit:
        m.add_constraint(total_expense <= cost_limit, name='cost_limit')

    print('Submitting')
    m.solve()

    steps = []
    schedule = []
    for (g1, g2) in ARCS:
        if use_arc[g1, g2].get_value() > 0.5 and g1 != source and g2 != sink:
            if g1 not in schedule:
                schedule.append(g1)
            if g2 not in schedule:
                schedule.append(g2)
            steps.append((g1, g2))

    methods = travel_data[travel_data.apply(
        lambda i: use_method[i.name].get_value() > 0.5, axis=1)].copy()
    methods = methods.reset_index('method')

    # Sort the schedule and print information
    schedule = sorted(schedule, key=lambda i: game_data.loc[i, 'ts'])
    if objective == 'least_emission':
        objective += car_type
    result = print_final_schedule(
        objective, schedule, methods, game_data, arcs_data, options)
    return result


def print_final_schedule(name, schedule, methods, game_data, arcs_data, options):
    daylimit = 'd' + str(options.get('day_limit', ''))
    costlimit = 'c' + str(options.get('cost_limit', ''))
    emissionlimit = 'e' + str(options.get('emission_limit', ''))

    Entry = namedtuple('Entry', [
        'type', 'name', 'location', 'destination',
        'start_date', 'start_time', 'end_date', 'end_time', 'price', 'emission'])
    full_schedule = []
    for i, _ in enumerate(schedule):
        step = i + 1
        game_id = schedule[i]
        g = game_data.loc[game_id]
        game_end = g['dt'] + datetime.timedelta(hours=1, minutes=45)
        gtype = g['type']
        gcode = g['code']

        if pd.isna(g.team1):
            gamename = ''
        else:
            gamename = f'{g.team1} vs {g.team2} '

        full_schedule.append(Entry(
            type='Game', name=f'{gamename}[ID:{game_id:02d} - {gtype}-{gcode}]',
            location=g.city, destination='', start_date=g.date.date(),
            start_time=g.time, end_date=game_end.date(),
            end_time=game_end.time(), price=0, emission=0
        ))

        if i == len(schedule)-1:
            continue

        next_game = game_data.loc[schedule[i + 1]]
        arc = arcs_data.loc[(g.city, next_game.city, g.date, next_game.date)]

        m = methods.loc[g.city, next_game.city]
        if isinstance(m, pd.DataFrame):
            m = m.iloc[0]
        def get_type(r):
            if 'fly' in r.lower():
                return 'Flight'
            elif 'train' in r.lower():
                return 'Train'
            elif 'bus' in r.lower():
                return 'Bus'
            else:
                return 'Drive'

        start_of_next_game = next_game['dt']
        gap = (start_of_next_game - game_end) - m.duration
        departure = (game_end + gap / 2).replace(microsecond=0)
        arrival = (departure + m.duration).replace(microsecond=0)
        full_schedule.append(Entry(
            type=get_type(m.method), name=f'{m.method} ({m.duration})',
            location=g.city,
            destination=next_game.city,
            start_date=departure.date(), start_time=departure.time(),
            end_date=arrival.date(), end_time=arrival.time(), price=m.cost,
            emission=m.emission
        ))

    df = pd.DataFrame.from_records(full_schedule, columns=Entry._fields)
    print(name)
    print(df.to_string())

    def combine_dt(row):
        start = datetime.datetime.combine(row['start_date'], row['start_time'])
        finish = datetime.datetime.combine(row['end_date'], row['end_time'])
        row['start_dt'] = start
        row['finish_dt'] = finish
        return row
    df = df.apply(lambda i: combine_dt(i), axis=1)
    limits = '_'.join([daylimit, costlimit, emissionlimit])
    df.to_csv(f'../results/{supplier}_all_method_{name}_{limits}.csv')
    return df

if __name__ == '__main__':
    solve_problem('shortest_tour')
    solve_problem('least_expensive')
    solve_problem('least_emission')
    solve_problem('least_emission', {'car_type': 'electric'})
