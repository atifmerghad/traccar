#!/usr/bin/env python3

"""
This script simulates a fleet of vehicles on a road trip in Morocco.
It uses the Traccar API to send position updates to a Traccar server.
"""
import datetime
import http.client as httplib
import json
import math
import random
import threading
import time
import urllib
from dataclasses import dataclass
from typing import List, Tuple
from urllib.request import urlopen

# Traccar endpoint (osmand protocol).
SERVER = "35.192.21.69:5055"

# Fleet simulation configuration.
FLEET_SIZE = 15
UPDATE_INTERVAL = 2  # seconds
SIMULATION_STEPS = 240  # ~8 minutes per car
LONG_TRIP_STEPS = 420  # ~14 minutes for selected cars
LONG_TRIP_CAR_NUMBERS = {1, 7, 11, 14}
FINAL_STOP_UPDATES = 3
ALWAYS_STOPPED_CAR_NUMBERS = {3, 2}
AVERAGE_SPEED_KMH = 75
FUEL_TANK_CAPACITY = 64.0
FUEL_CONSUMPTION_RATE = 8.5  # litres / 100km
INITIAL_FUEL_LEVELS = [0.4, 0.6, 1.0]  # 40%, 60%, 100%

# Major Moroccan cities to spread cars geographically.
MOROCCO_CITIES = {
    "Tangier": (35.7595, -5.8340),
    "Tetouan": (35.5889, -5.3626),
    "Rabat": (34.0209, -6.8416),
    "Casablanca": (33.5731, -7.5898),
    "Marrakech": (31.6295, -7.9811),
    "Fes": (34.0331, -5.0003),
    "Meknes": (33.8935, -5.5473),
    "Agadir": (30.4278, -9.5981),
    "Oujda": (34.6814, -1.9086),
    "Nador": (35.1744, -2.9287),
    "Kenitra": (34.2610, -6.5802),
    "Safi": (32.2994, -9.2372),
    "El Jadida": (33.2316, -8.5007),
    "Beni Mellal": (32.3373, -6.3498),
    "Errachidia": (31.9314, -4.4245),
    "Laayoune": (27.1536, -13.2033),
    "Dakhla": (23.6848, -15.9570),
}

# 15 unique routes so each car runs in a different area.
MOROCCO_ROUTES: List[Tuple[str, str]] = [
    ("Tangier", "Tetouan"),
    ("Rabat", "Casablanca"),
    ("Casablanca", "El Jadida"),
    ("Marrakech", "Safi"),
    ("Fes", "Meknes"),
    ("Kenitra", "Rabat"),
    ("Agadir", "Marrakech"),
    ("Oujda", "Nador"),
    ("Beni Mellal", "Marrakech"),
    ("Errachidia", "Fes"),
    ("Safi", "Agadir"),
    ("Tetouan", "Tangier"),
    ("Casablanca", "Beni Mellal"),
    ("Laayoune", "Dakhla"),
    ("Meknes", "Kenitra"),
]


@dataclass
class VehiclePlan:
    device_id: str
    name: str
    start_city: str
    end_city: str
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    trip_steps: int
    initial_fuel: float
    always_stopped: bool


class RealRoadRouteGenerator:
    """Generate route points on roads with OSRM, fallback to straight line."""

    def __init__(self, start_point: Tuple[float, float], end_point: Tuple[float, float]):
        self.start_lat, self.start_lon = start_point
        self.end_lat, self.end_lon = end_point

    def get_route_from_osrm(self) -> List[Tuple[float, float]]:
        url = (
            "http://router.project-osrm.org/route/v1/driving/"
            f"{self.start_lon},{self.start_lat};{self.end_lon},{self.end_lat}"
            "?overview=full&geometries=geojson"
        )
        try:
            response = urlopen(url, timeout=30)
            data = json.loads(response.read().decode())
            if data.get("code") != "Ok":
                return self._generate_fallback_route()
            coordinates = data["routes"][0]["geometry"]["coordinates"]
            return [(lat, lon) for lon, lat in coordinates]
        except Exception:
            return self._generate_fallback_route()

    def _generate_fallback_route(self) -> List[Tuple[float, float]]:
        points = []
        steps = 120
        for i in range(steps + 1):
            p = i / steps
            lat = self.start_lat + (self.end_lat - self.start_lat) * p
            lon = self.start_lon + (self.end_lon - self.start_lon) * p
            points.append((lat, lon))
        return points

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat_diff = (lat2 - lat1) * 111320
        lon_diff = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
        return math.sqrt(lat_diff**2 + lon_diff**2)

    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        diff_lon = math.radians(lon2 - lon1)
        x = math.sin(diff_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - (
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(diff_lon)
        )
        bearing = math.atan2(x, y)
        return (math.degrees(bearing) + 360) % 360

    def interpolate_points(
        self, route_points: List[Tuple[float, float]], target_count: int
    ) -> List[Tuple[float, float]]:
        if target_count <= 1:
            return route_points[:1]
        if len(route_points) < 2:
            return route_points * target_count
        if len(route_points) >= target_count:
            step = (len(route_points) - 1) / (target_count - 1)
            return [route_points[int(i * step)] for i in range(target_count)]

        interpolated: List[Tuple[float, float]] = []
        for i in range(target_count):
            p = i / (target_count - 1)
            source_index = p * (len(route_points) - 1)
            left = int(source_index)
            right = min(left + 1, len(route_points) - 1)
            local = source_index - left
            lat = route_points[left][0] + (route_points[right][0] - route_points[left][0]) * local
            lon = route_points[left][1] + (route_points[right][1] - route_points[left][1]) * local
            interpolated.append((lat, lon))
        return interpolated

    def generate_points(self, steps: int) -> List[Tuple[float, float, float, bool, float]]:
        """
        Returns list of (lat, lon, speed, ignition, bearing).
        Includes mixed states for Traccar: moving, slow traffic, idle, parked.
        """
        route_points = self.get_route_from_osrm()
        path = self.interpolate_points(route_points, steps)

        if not path:
            return []

        states = []
        # Keep in-trip stop as idle only (ignition on) to avoid parked status mid-trip.
        parked_range: set[int] = set()
        idle_points = min(max(20, steps // 12), max(1, steps - 30))
        idle_start = min(max(25, (steps * 3) // 4), max(0, steps - idle_points))
        idle_end = min(steps, idle_start + idle_points)
        idle_range = set(range(idle_start, idle_end))

        for i, (lat, lon) in enumerate(path):
            if i in parked_range:
                speed = 0.0
                ignition = False
            elif i in idle_range:
                speed = 0.0
                ignition = True
            else:
                ignition = True
                if random.random() < 0.13:
                    speed = random.uniform(8, 25)  # traffic
                else:
                    speed = random.uniform(45, 115)  # normal movement

            if i < len(path) - 1:
                next_lat, next_lon = path[i + 1]
                bearing = self.calculate_bearing(lat, lon, next_lat, next_lon)
            else:
                bearing = states[-1][4] if states else 0.0

            states.append((lat, lon, round(speed, 1), ignition, round(bearing, 1)))
        return states


class TraccarSimulator:
    def __init__(self, plan: VehiclePlan, server: str):
        self.plan = plan
        self.server = server
        self.conn = httplib.HTTPConnection(server, timeout=20)
        self.points_sent = 0
        self.errors = 0
        self.current_fuel = plan.initial_fuel

    def send_position(
        self,
        timestamp: int,
        lat: float,
        lon: float,
        speed: float,
        bearing: float,
        ignition: bool,
        motion: bool,
        event: str = "",
    ) -> bool:
        params = (
            ("id", self.plan.device_id),
            ("timestamp", int(timestamp)),
            ("lat", round(lat, 6)),
            ("lon", round(lon, 6)),
            ("valid", "true"),
            ("speed", speed),
            ("bearing", bearing),
            ("altitude", random.randint(0, 20)),
            ("accuracy", round(random.uniform(4, 12), 1)),
            ("fuel", round(self.current_fuel, 2)),
            ("fuelLevel", round((self.current_fuel / FUEL_TANK_CAPACITY) * 100, 1)),
            ("ignition", str(ignition).lower()),
            ("motion", str(motion).lower()),
            ("event", event),
        )
        try:
            self.conn.request("GET", "/?" + urllib.parse.urlencode(params))
            response = self.conn.getresponse()
            response.read()
            if response.status == 200:
                self.points_sent += 1
                return True
            self.errors += 1
            return False
        except Exception:
            self.errors += 1
            self.conn = httplib.HTTPConnection(self.server, timeout=20)
            return False

    def run(self):
        generator = RealRoadRouteGenerator(self.plan.start_point, self.plan.end_point)
        points = generator.generate_points(self.plan.trip_steps)
        if not points:
            print(f"❌ {self.plan.name}: no points generated")
            return

        if self.plan.always_stopped:
            lat, lon, _, _, bearing = points[0]
            points = [(lat, lon, 0.0, True, bearing) for _ in range(self.plan.trip_steps)]

        print(
            f"🚗 {self.plan.name} [{self.plan.device_id}] "
            f"{self.plan.start_city} → {self.plan.end_city} ({len(points)} updates)"
        )

        start_time = datetime.datetime.now()
        last_ignition = None
        last_motion = None
        for i, (lat, lon, speed, ignition, bearing) in enumerate(points):
            motion = speed > 0.1
            if i > 0 and speed > 0:
                prev_lat, prev_lon, _, _, _ = points[i - 1]
                segment_km = generator.calculate_distance(prev_lat, prev_lon, lat, lon) / 1000
                fuel_used = segment_km * (FUEL_CONSUMPTION_RATE / 100)
                self.current_fuel = max(0, self.current_fuel - fuel_used)

            event = ""
            if last_ignition is None or ignition != last_ignition:
                event = "ignitionOn" if ignition else "ignitionOff"
            elif last_motion is None or motion != last_motion:
                event = "motionchange"

            timestamp = int((start_time + datetime.timedelta(seconds=i * UPDATE_INTERVAL)).timestamp())
            self.send_position(timestamp, lat, lon, speed, bearing, ignition, motion, event)
            last_ignition = ignition
            last_motion = motion
            time.sleep(UPDATE_INTERVAL)

        # Always finish with explicit parked points so Traccar ends in stopped state.
        end_lat, end_lon, _, _, end_bearing = points[-1]
        for j in range(FINAL_STOP_UPDATES):
            stop_timestamp = int(
                (
                    start_time
                    + datetime.timedelta(seconds=(len(points) + j) * UPDATE_INTERVAL)
                ).timestamp()
            )
            stop_event = ""
            if last_ignition is None or last_ignition:
                stop_event = "ignitionOff"
            elif last_motion is None or last_motion:
                stop_event = "motionchange"

            self.send_position(
                stop_timestamp,
                end_lat,
                end_lon,
                0.0,
                end_bearing,
                False,
                False,
                stop_event,
            )
            last_ignition = False
            last_motion = False
            time.sleep(UPDATE_INTERVAL)

        print(
            f"✅ {self.plan.name} finished | sent={self.points_sent}/{len(points) + FINAL_STOP_UPDATES} "
            f"errors={self.errors} fuel={self.current_fuel:.1f}L"
        )
        self.conn.close()


def build_fleet(size: int) -> List[VehiclePlan]:
    fleet = []
    for i in range(size):
        car_number = i + 1
        start_city, end_city = MOROCCO_ROUTES[i % len(MOROCCO_ROUTES)]
        device_id = f"MA-CAR-{car_number:03d}"
        trip_steps = LONG_TRIP_STEPS if car_number in LONG_TRIP_CAR_NUMBERS else SIMULATION_STEPS
        initial_fuel_ratio = INITIAL_FUEL_LEVELS[i % len(INITIAL_FUEL_LEVELS)]
        initial_fuel = FUEL_TANK_CAPACITY * initial_fuel_ratio
        fleet.append(
            VehiclePlan(
                device_id=device_id,
                name=f"Morocco Car {car_number:02d}",
                start_city=start_city,
                end_city=end_city,
                start_point=MOROCCO_CITIES[start_city],
                end_point=MOROCCO_CITIES[end_city],
                trip_steps=trip_steps,
                initial_fuel=initial_fuel,
                always_stopped=car_number in ALWAYS_STOPPED_CAR_NUMBERS,
            )
        )
    return fleet


def main():
    print("\n" + "=" * 72)
    print("MOROCCO FLEET GPS SIMULATOR FOR TRACCAR")
    print("=" * 72)
    print(f"Server: {SERVER}")
    print(f"Cars: {FLEET_SIZE} (start in parallel)")
    print(f"Update interval: {UPDATE_INTERVAL}s")
    print(f"Normal trip duration: {SIMULATION_STEPS * UPDATE_INTERVAL / 60:.1f} minutes")
    print(f"Long trip duration: {LONG_TRIP_STEPS * UPDATE_INTERVAL / 60:.1f} minutes")

    fleet = build_fleet(FLEET_SIZE)

    print("\nIdentifiers to add in Traccar (Unique ID field):")
    for vehicle in fleet:
        duration = vehicle.trip_steps * UPDATE_INTERVAL / 60
        print(f"- {vehicle.device_id} ({vehicle.name}) | fuel start={vehicle.initial_fuel:.1f}L | {duration:.1f} min")

    print(f"\nLong trip cars: {', '.join(f'MA-CAR-{n:03d}' for n in sorted(LONG_TRIP_CAR_NUMBERS))}")

    print("\nStatus coverage in this simulation:")
    print("- Moving: 45-115 km/h")
    print("- Slow traffic: 8-25 km/h")
    print("- Idle stop: speed=0, ignition=true")
    print("- Parked stop: speed=0, ignition=false")
    print(f"- Always stopped test cars: {', '.join(f'MA-CAR-{n:03d}' for n in sorted(ALWAYS_STOPPED_CAR_NUMBERS))}")

    input("\nPress ENTER to start all cars (Ctrl+C to cancel)...")

    threads = []
    simulators = []
    for vehicle in fleet:
        simulator = TraccarSimulator(vehicle, SERVER)
        simulators.append(simulator)
        thread = threading.Thread(target=simulator.run, daemon=True)
        threads.append(thread)
        thread.start()

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n⚠️ Simulation interrupted by user.")

    total_sent = sum(sim.points_sent for sim in simulators)
    total_errors = sum(sim.errors for sim in simulators)
    print("\n" + "=" * 72)
    print("Fleet simulation completed")
    print(f"Total points sent: {total_sent}")
    print(f"Total errors: {total_errors}")
    print(f"Traccar UI: http://{SERVER.split(':')[0]}:8082")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
