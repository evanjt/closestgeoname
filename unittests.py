#!/usr/bin/python3

import unittest
import closestgeoname
import urllib
import os
import requests

class TestSchema(unittest.TestCase):
    # Test the schema of the country info file by asserting the first line considered is at Andorra
    def test_first_country(self):
        urllib.request.urlretrieve("http://download.geonames.org/export/dump/countryInfo.txt", "countryInfo.txt")

        with open("countryInfo.txt") as country_file:
            country_info = country_file.readlines()
        os.remove("countryInfo.txt")

        # First country in file should be Andorra(AD) on on line 51
        country_file_L51 = country_info[51].split("\t")
        self.assertEqual(country_file_L51[0], "AD")

    # Test the download links are available by checking their HTTP header status is 200
    def test_download_links(self):
        for download_link in closestgeoname.DBNAMES_LINKS:
            link_request = requests.head(download_link[0])
            self.assertEqual(link_request.status_code, 200, "Download link missing")

if __name__ == '__main__':
    unittest.main()
