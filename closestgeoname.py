#!/usr/bin/python3

# closestgeoname <http://github.com/evanjt/closestgeoname>
# A simple tool used to generate a local DB for reverse geocoding
# License: MIT
# Contact: Evan Thomas <evan@evanjt.com>

import pandas as pd
import sqlite3
import os
import argparse
import urllib.request
import time
import sys
from zipfile import ZipFile
import constants


def import_dump(city_filename, admin_filename, country_filename,
                city_colnames, state_colnames, encoding='utf-8',
                delimiter='\t'):
    MULTIPLIER = 1.4  # Estimated final DB size versus original input
    filesize = os.stat(city_filename).st_size/1048576  # In MB
    print("Initial filesize\t{} MB\nExpected database size\t{} MB\n".format(
                            round(filesize, 2), round(filesize*MULTIPLIER, 2)))

    df = pd.read_csv(city_filename, delimiter=delimiter, encoding=encoding,
                     header=None, names=city_colnames, low_memory=False)

    # Filter only the necessary columns
    cities = df[['Geonameid', 'Name', 'Latitude', 'Longitude',
                 'Admin1Code', 'CountryCode']]

    # Admin 1 table (commonly the state names)
    states = pd.read_csv(admin_filename, encoding='utf-8', delimiter='\t',
                         header=None, names=state_colnames)

    # Split the Country/Admin code by the separating decimal
    splitdf = states['AdCode'].str.split(".", expand=True)
    states['CountryID'] = splitdf[0]
    states['AdminCode'] = splitdf[1]
    states = states[['State', 'CountryID', 'AdminCode']]

    # This file is a bit messier, skip first 51 rows, only use columns 0 & 4
    countries = pd.read_csv(country_filename, encoding='utf-8',
                            delimiter='\t', header=None, skiprows=51)
    countries = countries[[0, 4]]
    countries.columns = ['ISO', 'Country']
    states = pd.merge(states, countries, left_on='CountryID', right_on='ISO',
                      how='left')

    return cities, states, countries


def fetch_data(options, choiceid, zipname, admincodes, countryinfo):
    urllib.request.urlretrieve(options[choiceid][0], zipname, reporthook)
    urllib.request.urlretrieve(constants.COUNTRYINFO,
                               "countryInfo.txt", reporthook)
    urllib.request.urlretrieve(constants.ADMINCODES,
                               "admin1CodesASCII.txt", reporthook)


def query_db_size(db_path):
    print("Database size {} MB\n".format(
        round(os.stat(db_path).st_size/1048576, 2)))


def generate_db(db_path, cities, states, countries):
    with sqlite3.connect(db_path) as conn:
        # Use pandas SQL export to generate SQLite DB
        print("Populating database", end='... ')
        cities.to_sql('cities', conn, if_exists='replace', index=False)
        states.to_sql('states', conn, if_exists='replace', index=False)
        countries.to_sql('countries', conn, if_exists='replace', index=False)
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


def query_closest_city(db_path, latitude, longitude, epsg=4326,
                       query_buffer_distance=0.1):
    ''' Start the buffer size for searching nearest points at a low number
    for speed, but keep iterating (doubling distance in size) until
    somewhere is found. Hence, this is faster for huge datasets as
    less points are considered in the spatial query, but slower for small
    datasets as more iterations will need to occur if no pointexists
    '''

    row = None
    while row is None:
        # Prevent an infinite loop
        if query_buffer_distance > 12756 * 1000:  # Longest distance on earth
            print("Search distance more than length of earth")
            return None

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
                select a.Name, b.State, b.Country from (
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
                ) a,
                states b
                where a.CountryCode == b.ISO
                and a.Admin1Code == b.AdminCode;
                """, query_tuple
            )
            row = cur.fetchone()

        query_buffer_distance *= 2

    return row


# Reporthook function to show file download progress. Code from
# https://blog.shichao.io/2012/10/04/progress_speed_indicator_for_urlretrieve_in_python.html
def reporthook(count, block_size, total_size):
    global start_time
    if count == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * duration))
    percent = int(count * block_size * 100 / total_size)
    sys.stdout.write("\r...%d%%, %d MB, %d KB/s, %d seconds passed" %
                     (percent, progress_size / (1024 * 1024), speed, duration))
    sys.stdout.flush()


# Fetches the dataset from the geonames repository and generates the db
def download_dataset(city_colnames, state_colnames, db_path,
                     options, choice=None):
    # If not defined in function, let user choose which file to download
    if (choice is None) or (choice < 0) or (choice > 4):
        for id, option in enumerate(options):
            print("[{}] {}:\t{}".format(id, option[0].split('/')[-1],
                                        option[1]))
        try:
            choice = int(input("Choose which file to download: "))
            if choice < 0 or choice >= len(options):
                exit("Error: Choose between {} and {}".format(0,
                                                              len(options)-1))
        except ValueError:
            exit('Error: Not an integer')

    zipname = "rawdata.zip"
    admincodes = "admin1CodesASCII.txt"
    countryinfo = "countryInfo.txt"
    fetch_data(options, choice, zipname, admincodes, countryinfo)
    extracted_txt = extract_zip(zipname)

    print()
    # Create database
    cities, states, countries = import_dump(extracted_txt, admincodes,
                                            countryinfo, city_colnames,
                                            state_colnames)
    generate_db(db_path, cities, states, countries)

    # Remove downloaded files
    os.remove(zipname)
    os.remove(extracted_txt)
    os.remove(countryinfo)
    os.remove(admincodes)
    print("Success")


def extract_zip(filename):
    with ZipFile('rawdata.zip', 'r') as zipObj:
        files = zipObj.namelist()
        # Iterate over the file names
        for fileName in files:
            # Check filename endswith csv
            if fileName.endswith('.txt'):
                # Extract a single file from zip
                zipObj.extract(fileName)
                filename = fileName
    return filename


def check_db_existance(dbfilename, columns_city, columns_state,
                       options, choice=None):
    if os.path.exists(dbfilename):
        return True
    else:
        print("GeoNames database", dbfilename,
              "does not exist. Choose an option")
        try:
            download_dataset(columns_city, columns_state, dbfilename,
                             options, choice=None)
        except ValueError:
            return False
        return True


def main():
    if check_db_existance(constants.DBFILENAME,
                          constants.CITY_COLNAMES,
                          constants.STATE_COLNAMES,
                          constants.DBNAMES_LINKS):
        parser = argparse.ArgumentParser()
        parser.add_argument("--database", type=str,
                            help="Set file for database (default: {})".format(
                                constants.DBFILENAME),
                            default=constants.DBFILENAME)
        parser.add_argument("longitude", type=float,
                            help="X coordinate (Longitude)")
        parser.add_argument("latitude", type=float,
                            help="Y coordinate (Latitude)")
        args = parser.parse_args()

        result = query_closest_city(args.database, args.latitude,
                                    args.longitude,
                                    constants.PROJECTION_EPSG,
                                    constants.MIN_QUERY_DIST)
        print("{}, {}, {}".format(result[0], result[1], result[2]))


if __name__ == "__main__":
    main()
