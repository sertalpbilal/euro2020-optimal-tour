# European Football Tournament: Optimal Trips

This repository includes source codes of our blog post about an optimal trip all over the Europe.

- [Summary Blog](https://blogs.sas.com/content/hiddeninsights/2019/12/03/1-tournament-12-countries-a-logistical-maze)
- [Full Gallery](https://blogs.sas.com/content/hiddeninsights/2019/12/03/fastest-cheapest-greenest-how-will-football-fans-choose-which-matches-to-attend/)

Resulting maps can be previewed:
- [Shortest Trip](https://raw.githack.com/sertalpbilal/euro2020-optimal-tour/master/notebook/map1_shortest_tour.html)
- [Cheapest Trip](https://raw.githack.com/sertalpbilal/euro2020-optimal-tour/master/notebook/map2_cheapest_tour.html)
- [Least Emission - Diesel](https://raw.githack.com/sertalpbilal/euro2020-optimal-tour/master/notebook/map3_least_emission_diesel.html)
- [Least Emission - Electric](https://raw.githack.com/sertalpbilal/euro2020-optimal-tour/master/notebook/map4_least_emission_electric.html)

You can find Python codes for data preparation and optimization under `scripts`, problem data under `data` and a Jupyter notebook showing how we populated animated maps under `notebook`.

## Data

The original data we used is kindly provided by [Rome2Rio.com](http://rome2rio.com). In this repository, we have used a sample data, which is randomly generated. If you would like to populate original results, please contact with Rome2Rio.

`all_modes.csv` files include origin, destination, route description, duration of the travel, low and high price for each option, and total distance in kilometers for each mode of transportation.

`arcs.p` file includes arcs we have used in the optimization model. Each arc represent a connection from a game to another one.

`games_filled.xlsx` is the schedule for the tournament.

`travel_info.p` file includes coordinates of each venue and driving distance and duration between them. This data is collected through OpenStreetMap and OSRM. Note that, we have used Rome2Rio driving durations instead of these values.

## CO2e Emission

We have collected emission data from UK Government GHG Conversion Factors for Company Reporting:

- https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/806025/Conversion-Factors-2019-Condensed-set-for-most-users.xls
- https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2019

Following CO2e emissions (gram per kilometer per passenger) is used in the model

- Flight: 180.78
- Ferry: 112.86
- Car: 170.61 (Medium size, average, diesel)
- Car: 5.76 (Medium size, average, battery-electric)
- Bus/Coach: 27.79
- Train: 5.97

## Optimization

Optimization model is formulated using our open-source optimization modeling package [sasoptpy](ttps://github.com/sassoftware/sasoptpy). Problems are solved on SAS Viya 3.5.

Learn more about sasoptpy here: https://sassoftware.github.io/sasoptpy/index.html

Learn more about SAS Viya here: https://www.sas.com/en_us/software/viya.html

## Packages

For Python codes, we have used following packages:
- geopy
- routingpy
- pandas
- swat
- sasoptpy

