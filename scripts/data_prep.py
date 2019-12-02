import pandas as pd
from geopy.geocoders import Nominatim
from concurrent.futures import ThreadPoolExecutor
from routingpy.routers import OSRM
import datetime


def get_coordinate_data():
    g = Nominatim(user_agent="Euro2020")
    o = OSRM()

    df = pd.read_excel(r'../data/games_filled.xlsx')

    # Venue Info Table
    VENUES = df[['venue', 'city']].copy()
    VENUES = VENUES.drop_duplicates()
    VENUES['fullname'] = VENUES.apply(
        lambda i: i['venue'] + ', ' + i['city'], axis=1)
    coordinates = [g.geocode(i['fullname']) for _, i in VENUES.iterrows()]
    VENUES['info'] = coordinates

    # Distance Calculation
    venue_df = VENUES.drop('fullname', axis=1).copy()
    vcopy = venue_df.assign(key=0)
    vf = vcopy.merge(vcopy, how='outer', on='key').drop('key', axis=1)
    vf = vf[vf['venue_x'] != vf['venue_y']]

    def get_distance(row):
        stadium1 = (row.info_x.longitude, row.info_x.latitude)
        stadium2 = (row.info_y.longitude, row.info_y.latitude)
        # print(stadium1, stadium2)
        dr = o.directions([stadium1, stadium2], profile='car', steps=False)
        km_distance = dr.distance / 1000
        travel_time = datetime.timedelta(seconds=dr.duration)
        return (km_distance, travel_time)

    with ThreadPoolExecutor(max_workers=1) as executor:
        distances = list(executor.map(get_distance, vf.itertuples()))

    travel_info = vf.copy()
    travel_info['travel'] = list(distances)

    travel_info['distance_km'] = travel_info['travel'].apply(lambda i: i[0])
    travel_info['travel_time'] = travel_info['travel'].apply(lambda i: i[1])

    travel_info.to_pickle('../data/travel_info.p')


def generate_all_arcs():
    df = pd.read_excel(r'../data/games_filled.xlsx')

    # Filtered Games
    df['key'] = 0
    df['dt'] = df.apply(
        lambda i: datetime.datetime.combine(i['date'], i['time']), axis=1)
    all_combinations = pd.merge(df, df, on='key')
    filtered = all_combinations[
        all_combinations.venue_x != all_combinations.venue_y]
    filtered = filtered[filtered['dt_y'] >= filtered['dt_x']]
    filtered.to_pickle('../data/arcs.p')


if __name__ == '__main__':
    get_coordinate_data()
    generate_all_arcs()
