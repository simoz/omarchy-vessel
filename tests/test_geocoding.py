"""City search validation and persistence, with no network calls."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
import geocoding
import settings
import vessel


def feature(name="Genova",country="Italy",countrycode="IT",point=None):
    return dict(properties=dict(name=name,country=country,countrycode=countrycode,state="Liguria"),
                geometry=dict(type="Point",coordinates=point or [8.9338624,44.40726]))


class CityTest(unittest.TestCase):
    def test_ambiguous_cities_remain_separate_and_invalid_positions_are_ignored(self):
        result = geocoding.places(dict(features=[feature(),feature(),feature("Genova","Philippines","PH",[124.19,9.65]),
            feature(point=[190,95]),None,dict(properties={})]))
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]["label"],"Genoa (Italy)")
        self.assertEqual(result[1]["label"],"Genova (Philippines)")
        self.assertEqual(result[0]["latitude"],44.40726)

    def test_request_encodes_city_and_never_includes_credentials(self):
        with patch.dict(os.environ,{"AISSTREAM_API_KEY":"secret-test"}), patch.object(geocoding,"urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value=json.dumps(dict(features=[feature()])).encode()
            self.assertEqual(geocoding.search("São Paulo & coast")[0]["label"],"Genoa (Italy)")
            outgoing = request.call_args.args[0]
            self.assertEqual(parse_qs(urlsplit(outgoing.full_url).query)["q"],["São Paulo & coast"])
            self.assertNotIn("secret-test",outgoing.full_url+str(outgoing.headers))
            self.assertEqual(request.call_args.kwargs["timeout"],12)

    def test_empty_results_and_malformed_response(self):
        self.assertEqual(geocoding.places(dict(features=[])),[])
        for invalid in [[],None,{},dict(features={})]:
            with self.assertRaises(ValueError):
                geocoding.places(invalid)
        with patch.object(geocoding,"urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value=b"x"*262145
            with self.assertRaises(ValueError):
                geocoding.search("Genoa")

    def test_selected_city_survives_restart_without_another_lookup(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{"XDG_CONFIG_HOME":directory}):
            settings.save(dict(apiKey="test",autoLocation=False,latitude=44.40726,longitude=8.9338624,cityName="Genoa (Italy)"))
            self.assertEqual(settings.public_settings()["cityName"],"Genoa (Italy)")
            output=io.StringIO()
            with patch("runtime.ensure_runtime"), patch.object(vessel.basemap,"build",return_value={}), patch.object(vessel.Receiver,"run",new_callable=AsyncMock), patch.object(geocoding,"urlopen") as network, redirect_stdout(output):
                self.assertEqual(vessel.main(["--saved-settings"]),0)
                network.assert_not_called()
            # The receiver receives the saved city label, without reverse geocoding.
            with patch("runtime.ensure_runtime"), patch.object(vessel.basemap,"build",return_value={}), patch.object(vessel,"Receiver") as receiver, patch.object(vessel.asyncio,"run"), redirect_stdout(io.StringIO()):
                vessel.main(["--saved-settings"])
                self.assertEqual(receiver.call_args.args[1]["location"],"Genoa (Italy)")

    def test_legacy_coordinates_and_invalid_city_label(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{"XDG_CONFIG_HOME":directory}):
            saved=settings.save(dict(autoLocation=False,latitude=44,longitude=9))
            self.assertEqual(saved["cityName"],"")
            with self.assertRaises(ValueError):
                settings.save(dict(cityName="bad\nlabel"))


if __name__ == "__main__":
    unittest.main()
