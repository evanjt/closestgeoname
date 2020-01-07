#!/usr/bin/python3

# This script will import a cities database from GeoNames and generate a local
# SQLite/Spatialite database for querying placenames nearest to a lat/long point.
# The column schema follows that which is given on
# http://download.geonames.org/export/dump/ as of 07/01/2020. As this is the same for
# all datasets, whichever chosen should function the same way, depending on the needs
# of your database

import pandas as pd
import sqlite3
import os
import argparse
from shapely.geometry import Point

# Schema of geonames databases from
# as of 07/01/2020
COLNAMES = ['Geonameid',
            'Name',
            'Asciiname',
            'Alternatenames',
            'Latitude',
            'Longitude',
            'FeatureClass',
            'FeatureCode',
            'CountryCode',
            'Cc2',
            'Admin1Code',
            'Admin2Code',
            'Admin3Code',
            'Admin4Code',
            'Population',
            'Elevation',
            'Dem',
            'Timezone',
            'ModificationDate']

def import_dump(filename, colnames, encoding='utf-8', delimiter='\t'):
    MULTIPLIER = 1.4 # DB size versus original text file
    filesize = os.stat(filename).st_size/1048576 # In MB
    print("Initial filesize\t{} MB\nExpected database size\t{} MB\n".format(
                            round(filesize,2), round(filesize*MULTIPLIER,2)))

    df = pd.read_csv(filename, delimiter=delimiter, encoding=encoding,
                     header=None, names=colnames, low_memory=False)

    # Filter only the necessary columns
    return df[['Geonameid', 'Name', 'Latitude', 'Longitude', 'CountryCode']]

def query_db_size(db_path):
    print("Database size {} MB\n".format(round(os.stat(db_path).st_size/1048576, 2)))

def generate_db(db_path, dataframe):
    with sqlite3.connect(db_path) as conn:
        # Use pandas SQL export to generate SQLite DB
        print("Populating database", end='... ')
        dataframe.to_sql('cities', conn, if_exists='replace', index=False)
        print("Done")
        query_db_size(db_path)

        # Initialise spatialite
        conn.enable_load_extension(True)
        conn.load_extension("mod_spatialite")
        conn.execute("SELECT InitSpatialMetaData(1);")

        # Build geometry columns
        print("Building geometry columns", end='... ')
        conn.execute(
            """
            SELECT AddGeometryColumn('cities', 'geom', 4326, 'POINT', 2);
            """
        )
        print("Done")
        query_db_size(db_path)

        # Form geometry column 'geom' from latitude and logitude columns
        print("Generating spatial columns from lat/long columns", end='... ')
        conn.execute(
            """
            UPDATE cities
            SET geom = MakePoint(Longitude, Latitude, 4326);
            """
        )
        print("Done")
        query_db_size(db_path)

        # Generate the spatial index for super-fast queries
        print("Building spatial index", end='... ')
        conn.execute(
            """
            SELECT createspatialindex('cities', 'geom');
            """
        )
        print("Done")
        query_db_size(db_path)

def query_closest_city(db_path, latitude, longitude, epsg=4326, query_buffer_distance=0.5):
    # Form tuple to represent values missing in SQL query
    query_tuple = (longitude,
                   latitude,
                   epsg,
                   longitude,
                   latitude,
                   epsg,
                   query_buffer_distance)
    with sqlite3.connect(db_path) as conn:
        conn.enable_load_extension(True)
        conn.load_extension("mod_spatialite")
        cur = conn.cursor()

        # Query database with spatial index
        cur.execute(
            """
            select Name, CountryCode from (
                select *, distance(geom, makepoint(?, ?, ?)) dist
                from cities
                where rowid in (
                    select rowid
                    from spatialindex
                    where f_table_name = 'cities'
                    and f_geometry_column = 'geom'
                    and search_frame = buffer(makepoint(?, ?, ?), ?)
                )
                order by dist
                limit 1
            );
            """, query_tuple
        )
        row = cur.fetchone()
    return row

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=str, help="Set the file for database (default: geonames.sqlite)", default="geonames.sqlite")
    parser.add_argument("longitude", type=float, help="X coordinate (Longitude)")
    parser.add_argument("latitude", type=float, help="Y coordinate (Latitude)")
    args = parser.parse_args()
    print(args)
    print(args.database)

    result = query_closest_city(args.database, args.latitude, args.longitude)
    print("{}, {}".format(result[0], result[1]))

if __name__ == "__main__":
    main()
