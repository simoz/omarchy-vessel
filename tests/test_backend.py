"""Behaviour checks for AIS normalization, geography, settings and offline startup."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
import basemap
import geometry as g
import settings
import vessel

ROOT = Path(__file__).resolve().parents[1]


def report(kind="PositionReport", mmsi=123456789, **body):
    return dict(MessageType=kind, MetaData=dict(MMSI=mmsi), Message={kind:dict(Valid=True,Latitude=0,Longitude=0.1,Sog=4,Cog=90)|body})


class GeometryTest(unittest.TestCase):
    def test_distance_units_and_bearings(self):
        distance, bearing = g.distance_bearing(0,0,0,1)
        self.assertAlmostEqual(distance,60.04,places=1)
        self.assertEqual(bearing,90)
        self.assertAlmostEqual(g.distance_bearing(0,0,1,0)[1],0)
        self.assertFalse(g.coordinates(True,0))
        self.assertFalse(g.coordinates(float("nan"),0))

    def test_circle_fits_subscription_even_near_dateline_and_poles(self):
        for lat,lon in [(0,0),(44.4,8.9),(70,179.9),(-70,-179.9),(89.9,0),(-89.9,0)]:
            boxes = g.bounding_boxes(lat,lon,200)
            for bearing in range(0,360,5):
                y,x = g.destination(lat,lon,199.99,bearing)
                self.assertTrue(any(a[0] <= y <= b[0] and a[1] <= x <= b[1] for a,b in boxes))


class FleetTest(unittest.TestCase):
    def test_class_a_and_b_and_static_merge(self):
        fleet = vessel.Fleet(0,0,25)
        for index,kind in enumerate(vessel.POSITION_TYPES):
            fleet.ingest(report(kind,123456780+index),1000)
        fleet.ingest(report("StaticDataReport",123456780,ReportA=dict(Valid=True,Name=" TEST@@ "),ReportB=dict(Valid=True,ShipType=36)),1100)
        ships = fleet.snapshot(1100)["ships"]
        self.assertEqual(len(ships),3)
        self.assertEqual(ships[0]["name"],"TEST")
        self.assertEqual(ships[0]["type"],"Sailing")
        self.assertEqual(ships[0]["lastSeen"],1000)

    def test_invalid_positions_and_sentinels(self):
        fleet = vessel.Fleet(0,0,25)
        for lat,lon in [(91,0),(0,181),(None,0),(True,0),(float("nan"),0)]:
            fleet.ingest(report(Latitude=lat,Longitude=lon),1000)
            self.assertEqual(fleet.snapshot(1000)["ships"],[])
        fleet.ingest(report(Sog=102.3,Cog=360),1000)
        ship = fleet.snapshot(1000)["ships"][0]
        self.assertIsNone(ship["speed"])
        self.assertIsNone(ship["course"])

    def test_stale_expiry_and_out_of_order(self):
        fleet = vessel.Fleet(0,0,25)
        item = report()
        item["MetaData"]["time_utc"] = "2024-01-01 00:00:00 +0000 UTC"
        stamp = 1704067200
        fleet.ingest(item,stamp)
        item["MetaData"]["time_utc"] = "2023-12-31T23:59:00Z"
        item["Message"]["PositionReport"]["Longitude"] = 0.2
        fleet.ingest(item,stamp+5)
        self.assertEqual(fleet.snapshot(stamp)["ships"][0]["longitude"],0.1)
        self.assertTrue(fleet.snapshot(stamp+301)["ships"][0]["stale"])
        fleet.ingest(report("ShipStaticData",Name="Still transmitting"),stamp+1799)
        self.assertEqual(fleet.snapshot(stamp+1800)["ships"],[])

    def test_filter_limits_and_malformed_input(self):
        fleet = vessel.Fleet(0,0,25)
        for bad in [None, [], {}, dict(MessageType="PositionReport",MetaData=[],Message={}),report(mmsi=42)]:
            fleet.ingest(bad,1000)
        self.assertEqual(fleet.ships,{})
        for index in range(2100):
            fleet.ingest(report(mmsi=123450000+index),1000+index)
        self.assertLessEqual(len(fleet.ships),2000)
        self.assertLessEqual(len(fleet.snapshot(2100)["ships"]),200)
        fleet = vessel.Fleet(0,0,1)
        fleet.ingest(report(),1000)
        self.assertEqual(fleet.snapshot(1000)["total"],0)

    def test_timestamp_provenance(self):
        self.assertEqual(vessel.message_time({},1000),(1000,"Received"))
        self.assertEqual(vessel.message_time({"time_utc":"2099-01-01T00:00:00Z"},1000),(1000,"Received"))
        self.assertEqual(vessel.message_time({"time_utc":"2024-01-01T00:00:00"},1000),(1000,"Received"))


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME":self.directory.name,"AISSTREAM_API_KEY":""})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_secret_permissions_blank_preservation_and_rotation(self):
        public = settings.save(dict(apiKey="secret",radiusNm="42"))
        self.assertNotIn("secret",json.dumps(public))
        self.assertTrue(public["hasApiKey"])
        self.assertEqual(settings.path().stat().st_mode & 0o777,0o600)
        settings.save(dict(apiKey="",unit="km"))
        self.assertEqual(settings.api_key(),"secret")
        settings.save(dict(apiKey="replacement"))
        self.assertEqual(settings.api_key(),"replacement")

    def test_invalid_settings_do_not_replace_saved_key(self):
        settings.save(dict(apiKey="original"))
        for bad in [dict(radiusNm=0),dict(latitude=91),dict(demo="true"),dict(autoLocation=False),dict(unit="miles"),dict(apiKey="bad\nkey")]:
            with self.assertRaises((ValueError,TypeError)):
                settings.save(bad)
            self.assertEqual(settings.api_key(),"original")

    def test_key_over_stdin_is_never_echoed(self):
        result = subprocess.run([sys.executable,"-B",str(ROOT/"backend/vessel.py"),"--save-settings"],
            input=json.dumps(dict(apiKey="stdin-secret"))+"\n",text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn("stdin-secret",result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])


class BasemapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.genova = basemap.build(*g.GENOVA,25)

    @staticmethod
    def inside(point,ring):
        x,y = point
        inside = False
        for a,b in zip(ring,ring[1:]+ring[:1]):
            if (a[1]>y) != (b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                inside = not inside
        return inside

    @classmethod
    def land(cls,point,data):
        return any(cls.inside(point,rings[0]) and not any(cls.inside(point,r) for r in rings[1:]) for rings in data["polygons"])

    def test_genova_geography_and_demo_stay_offshore(self):
        self.assertTrue(self.genova["available"])
        self.assertTrue(self.land([0,-0.7],self.genova))
        self.assertFalse(self.land([0,0.7],self.genova))
        for tick in [0,314,628,942]:
            fleet = vessel.Fleet(*g.GENOVA,25)
            vessel.populate_demo(fleet,tick,1000)
            for ship in fleet.snapshot(1000)["ships"]:
                angle = math.radians(ship["bearing"])
                self.assertFalse(self.land([math.sin(angle)*ship["distance"]/25,-math.cos(angle)*ship["distance"]/25],self.genova))

    def test_clipping_and_missing_map(self):
        self.assertEqual(basemap.clip_segment([-1,0],[3,2],[0,0,1,1]),[[0,0.5],[1,1]])
        ring = basemap.clip_ring([[-5,-5],[5,-5],[5,5],[-5,5]],[-1,-1,1,1])
        self.assertEqual(abs(basemap.signed_area(ring)),4)
        self.assertFalse(basemap.build(0,0,25,path="/missing/map")["available"])

    def test_dateline_and_poles(self):
        for lat,lon in [(-16.5,179.9),(89.5,0),(-89.5,0)]:
            data = basemap.build(lat,lon,100)
            self.assertTrue(data["available"])
            self.assertNotIn("NaN",json.dumps(data,allow_nan=False))
            if lat < -89:
                self.assertTrue(self.land([0,0],data))
            if lat > 89:
                self.assertFalse(self.land([0,0],data))


class DemoTest(unittest.TestCase):
    def test_demo_uses_standard_library_without_runtime_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, XDG_DATA_HOME=directory,XDG_CONFIG_HOME=directory)
            process = subprocess.Popen([sys.executable,"-B","-S",str(ROOT/"backend/vessel.py"),"--demo","--latitude","0","--longitude","0"],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            try:
                first = json.loads(process.stdout.readline())
                second = json.loads(process.stdout.readline())
                third = json.loads(process.stdout.readline())
                self.assertEqual(first["status"],"LOCATING")
                self.assertEqual(second["latitude"],g.GENOVA[0])
                self.assertEqual(second["location"],"Genoa (Italy) · simulated traffic")
                self.assertEqual(len(second["ships"]),6)
                self.assertIn("basemap",second)
                self.assertNotIn("basemap",third)
                self.assertEqual(list(Path(directory).iterdir()),[])
            finally:
                process.terminate()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
