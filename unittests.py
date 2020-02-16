#!/usr/bin/python3

import unittest
import closestgeoname
import urllib
import os
import requests

FILE_ZIPNAME = "rawdata.zip"
FILE_ADMINCODES = "admin1CodesASCII.txt"
FILE_COUNTRYINFO = "countryInfo.txt"

class TestSchema(unittest.TestCase):
    # Test the schema of the country info file by asserting the first line considered is at Andorra
    def test_first_country(self):
        urllib.request.urlretrieve("http://download.geonames.org/export/dump/countryInfo.txt", FILE_COUNTRYINFO)

        with open(FILE_COUNTRYINFO) as country_file:
            country_info = country_file.readlines()
        os.remove(FILE_COUNTRYINFO)

        # First country in file should be Andorra(AD) on on line 51
        country_file_L51 = country_info[51].split("\t")
        self.assertEqual(country_file_L51[0], "AD")

    # Test the download links are available by checking their HTTP header status is 200
    def test_download_links(self):
        for download_link in closestgeoname.DBNAMES_LINKS:
            link_request = requests.head(download_link[0])
            self.assertEqual(link_request.status_code, 200, "Download link missing")

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.zipname = "rawdata.zip"
        self.admincodes = "admin1CodesASCII.txt"
        self.countryinfo = "countryInfo.txt"
        self.db_path = "geonames_tester.sqlite"
        self.min_query_dist = 0.1 # Metres

        # Download files
        closestgeoname.fetch_data(closestgeoname.DBNAMES_LINKS,
                                  4,
                                  self.zipname,
                                  self.admincodes,
                                  self.countryinfo)
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    self.zipname)))
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    self.admincodes)))
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    self.countryinfo)))

        # Unzip file
        self.unzipped_filename = closestgeoname.extract_zip(self.zipname)
        self.assertTrue(os.path.exists(self.unzipped_filename))

        cities, states, countries = closestgeoname.import_dump(self.unzipped_filename,
                                                               self.admincodes,
                                                               self.countryinfo,
                                                               closestgeoname.CITY_COLNAMES,
                                                               closestgeoname.STATE_COLNAMES)
        self.assertTrue(os.path.exists(self.unzipped_filename))
        closestgeoname.generate_db(self.db_path, cities, states, countries)
        self.assertTrue(os.path.exists(self.db_path))

    def tearDown(self):
        os.remove(self.zipname)
        os.remove(self.admincodes)
        os.remove(self.countryinfo)
        os.remove(self.unzipped_filename)
        os.remove(self.db_path)


    def test_some_cities(self):
        locations = [(-37.8136, 144.9631, "Melbourne", "Victoria", "Australia"),
                     (-33.4489, -70.6693, "Santiago", "Santiago Metropolitan", "Chile"),
                     (51.5074, -0.1278, "London", "England", "United Kingdom"),
                     (35.6762, 139.6503, "Tokyo", "Tokyo", "Japan"),
                     (47.3769, 8.5417, "Zürich", "Zurich", "Switzerland"),
                     (-31.9505, 115.8605, "Perth", "Western Australia", "Australia"),
                     (40.7128, -74.0060, "New York City", "New York", "United States")]
        for location in locations:
            city, state, country = closestgeoname.query_closest_city(self.db_path,
                                                location[0],
                                                location[1],
                                                query_buffer_distance=self.min_query_dist)
            self.assertEqual(city, location[2])
            self.assertEqual(state, location[3])
            self.assertEqual(country, location[4])

if __name__ == '__main__':
    unittest.main()
