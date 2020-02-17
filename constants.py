#!/usr/bin/python3

# Schema of geonames databases from
# as of 07/01/2020

import os

ADMINCODES = "http://download.geonames.org/export/dump/admin1CodesASCII.txt"
CITY_COLNAMES = ['Geonameid',
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
COUNTRYINFO = "http://download.geonames.org/export/dump/countryInfo.txt"
DBFILENAME = os.path.join(os.getcwd(), 'geonames.sqlite')
DBNAMES_LINKS = [
    ("http://download.geonames.org/export/dump/allCountries.zip",
     "all countries combined in one file (HUGE! > 1.2 GB)"),
    ("http://download.geonames.org/export/dump/cities500.zip",
     "all cities with a population > 500 or seats of adm div \
     down to PPLA4 (ca 185.000)"),
    ("http://download.geonames.org/export/dump/cities1000.zip",
     "all cities with a population > 1000 or seats of adm div \
     down to PPLA3 (ca 130.000)"),
    ("http://download.geonames.org/export/dump/cities5000.zip",
     "all cities with a population > 5000 or PPLA (ca 50.000)"),
    ("http://download.geonames.org/export/dump/cities15000.zip",
     "all cities with a population > 15000 or capitals (ca 25.000)")
    ]
MIN_QUERY_DIST = 0.1  # Metres
PROJECTION_EPSG = 4326
STATE_COLNAMES = ["AdCode", "State", "StateClean", "ID"]
