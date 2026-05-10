#!/usr/bin/env python3

import datetime
import http.client as httplib
import json
import math
import random
import time
import urllib
from typing import List, Tuple
from urllib.request import urlopen

# Configuration
DEVICE_ID = "1994-A-78"
SERVER = "35.192.21.69:5055"

# Vehicle Configuration (Not sent to server)
CAR_NAME = "Santa Fe"
FUEL_TANK_CAPACITY = 64  # litres
INITIAL_FUEL_LEVEL = 64  # Start with full tank
FUEL_CONSUMPTION_RATE = 8.5  # litres per 100km (average consumption)

# Real locations - Use coordinates (lat, lon) format
POINT_A = (35.7595, -5.8340)  # Tanger, Morocco
POINT_B = (33.5731, -7.5898)  # Casablanca, Morocco (~280km)

# Simulation parameters
UPDATE_INTERVAL = 2  # Send GPS data every 2 seconds
AVERAGE_SPEED_KMH = 80  # Average highway speed
PARKING_STOPS = 2  # Number of rest stops during trip


class RealRoadRouteGenerator:
    """Generate GPS points following real roads using OpenStreetMap"""

    def __init__(
        self, start_point: Tuple[float, float], end_point: Tuple[float, float]
    ):
        self.start_lat, self.start_lon = start_point
        self.end_lat, self.end_lon = end_point
        self.route_points = []

    def get_route_from_osrm(self) -> List[Tuple[float, float]]:
        """
        Fetch real route from OSRM (OpenStreetMap Routing Machine)
        Returns list of (lat, lon) coordinates following actual roads
        """
        print("🌍 Fetching route from OpenStreetMap...")

        # OSRM public API endpoint
        url = f"http://router.project-osrm.org/route/v1/driving/{self.start_lon},{self.start_lat};{self.end_lon},{self.end_lat}?overview=full&geometries=geojson"

        try:
            response = urlopen(url, timeout=30)
            data = json.loads(response.read().decode())

            if data["code"] != "Ok":
                print("❌ Failed to get route from OSRM")
                return self._generate_fallback_route()

            # Extract route coordinates
            coordinates = data["routes"][0]["geometry"]["coordinates"]
            # Convert from [lon, lat] to (lat, lon)
            route_points = [(lat, lon) for lon, lat in coordinates]

            distance_km = data["routes"][0]["distance"] / 1000
            duration_min = data["routes"][0]["duration"] / 60

            print(f"✅ Route found!")
            print(f"   📏 Distance: {distance_km:.1f} km")
            print(f"   ⏱️  Estimated time: {duration_min:.0f} minutes")
            print(f"   📍 Route points: {len(route_points)}")

            return route_points

        except Exception as e:
            print(f"⚠️  Error fetching route: {e}")
            print("📍 Using fallback straight-line route")
            return self._generate_fallback_route()

    def _generate_fallback_route(self) -> List[Tuple[float, float]]:
        """Generate simple route if OSRM fails"""
        points = []
        steps = 50
        for i in range(steps + 1):
            progress = i / steps
            lat = self.start_lat + (self.end_lat - self.start_lat) * progress
            lon = self.start_lon + (self.end_lon - self.start_lon) * progress
            points.append((lat, lon))
        return points

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance in meters"""
        lat_diff = (lat2 - lat1) * 111320
        lon_diff = (
            (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
        )
        return math.sqrt(lat_diff**2 + lon_diff**2)

    def calculate_bearing(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate bearing between two points"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        diff_lon = math.radians(lon2 - lon1)

        x = math.sin(diff_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(
            lat1_rad
        ) * math.cos(lat2_rad) * math.cos(diff_lon)

        bearing = math.atan2(x, y)
        return (math.degrees(bearing) + 360) % 360

    def interpolate_points(
        self, route_points: List[Tuple[float, float]], target_count: int
    ) -> List[Tuple[float, float]]:
        """
        Interpolate route points to match desired number of GPS updates
        """
        if len(route_points) >= target_count:
            # Downsample by taking every nth point
            step = len(route_points) / target_count
            return [route_points[int(i * step)] for i in range(target_count)]

        # Upsample by interpolating between points
        interpolated = []
        points_per_segment = target_count / (len(route_points) - 1)

        for i in range(len(route_points) - 1):
            lat1, lon1 = route_points[i]
            lat2, lon2 = route_points[i + 1]

            num_intermediate = int(points_per_segment)
            for j in range(num_intermediate):
                progress = j / num_intermediate
                lat = lat1 + (lat2 - lat1) * progress
                lon = lon1 + (lon2 - lon1) * progress
                interpolated.append((lat, lon))

        interpolated.append(route_points[-1])
        return interpolated[:target_count]

    def generate_gps_points_with_timing(
        self,
    ) -> List[Tuple[str, float, float, float, float, float]]:
        """
        Generate GPS points with realistic timing, speeds and fuel consumption
        Returns: List of (timestamp, lat, lon, speed, bearing, fuel)
        """
        # Get real route
        route_points = self.get_route_from_osrm()

        # Calculate total distance
        total_distance = 0
        for i in range(len(route_points) - 1):
            lat1, lon1 = route_points[i]
            lat2, lon2 = route_points[i + 1]
            total_distance += self.calculate_distance(lat1, lon1, lat2, lon2)

        # Calculate trip duration based on distance and average speed
        trip_duration_hours = (total_distance / 1000) / AVERAGE_SPEED_KMH
        trip_duration_minutes = int(trip_duration_hours * 60)

        # Calculate number of GPS points needed
        total_points = (trip_duration_minutes * 60) // UPDATE_INTERVAL

        # Calculate expected fuel consumption
        expected_fuel_used = (total_distance / 1000) * (
            FUEL_CONSUMPTION_RATE / 100
        )

        print(f"\n📊 Trip simulation:")
        print(
            f"   ⏱️  Duration: {trip_duration_minutes} minutes ({trip_duration_hours:.1f} hours)"
        )
        print(f"   📍 GPS updates: {total_points} points")
        print(f"   🛑 Rest stops: {PARKING_STOPS}")
        print(f"   ⛽ Expected fuel consumption: {expected_fuel_used:.1f}L")

        # Interpolate route to match desired point count
        interpolated_route = self.interpolate_points(
            route_points, total_points
        )

        # Generate timed GPS points
        gps_points = []
        current_time = datetime.datetime.now()

        # Parking stop positions (evenly distributed)
        parking_positions = set()
        if PARKING_STOPS > 0:
            interval = total_points // (PARKING_STOPS + 1)
            for i in range(1, PARKING_STOPS + 1):
                parking_positions.add(i * interval)

        is_parked = False
        parking_counter = 0
        current_fuel = INITIAL_FUEL_LEVEL
        distance_traveled = 0

        for i, (lat, lon) in enumerate(interpolated_route):
            # Check if this is a parking stop
            if i in parking_positions and not is_parked:
                is_parked = True
                parking_counter = (
                    random.randint(180, 600) // UPDATE_INTERVAL
                )  # 3-10 min
                print(
                    f"   🅿️  Rest stop at {i}/{total_points} ({parking_counter * UPDATE_INTERVAL}s)"
                )

            if is_parked:
                speed = 0.0
                # Use previous bearing if available
                bearing = gps_points[-1][4] if gps_points else 0.0
                parking_counter -= 1

                if parking_counter <= 0:
                    is_parked = False
            else:
                # Calculate speed with variations
                base_speed = AVERAGE_SPEED_KMH
                speed_variation = random.uniform(-10, 10)
                speed = max(40, min(120, base_speed + speed_variation))

                # Occasional traffic slowdown
                if random.random() < 0.03:
                    speed = random.uniform(20, 40)

                # Calculate bearing
                if i < len(interpolated_route) - 1:
                    next_lat, next_lon = interpolated_route[i + 1]
                    bearing = self.calculate_bearing(
                        lat, lon, next_lat, next_lon
                    )

                    # Calculate distance for this segment
                    segment_distance = (
                        self.calculate_distance(lat, lon, next_lat, next_lon)
                        / 1000
                    )  # Convert to km

                    # Update fuel consumption based on distance
                    fuel_consumed = segment_distance * (
                        FUEL_CONSUMPTION_RATE / 100
                    )
                    current_fuel -= fuel_consumed
                    current_fuel = max(0, current_fuel)  # Don't go below 0
                else:
                    bearing = gps_points[-1][4] if gps_points else 0.0

            gps_points.append(
                (
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    lat,
                    lon,
                    speed,
                    bearing,
                    round(current_fuel, 2),  # Fuel level in litres
                )
            )

            current_time += datetime.timedelta(seconds=UPDATE_INTERVAL)

        return gps_points


class TraccarSimulator:
    def __init__(self, device_id: str, server: str):
        self.device_id = device_id
        self.server = server
        self.conn = httplib.HTTPConnection(server)
        self.points_sent = 0
        self.errors = 0

    def send_position(
        self,
        timestamp: int,
        lat: float,
        lon: float,
        speed: float,
        bearing: float,
        fuel: float,
    ) -> bool:
        """Send GPS position to Traccar server with fuel level"""
        params = (
            ("id", self.device_id),
            ("timestamp", int(timestamp)),
            ("lat", lat),
            ("lon", lon),
            ("speed", speed),
            ("bearing", bearing),
            ("altitude", 0),
            ("accuracy", random.uniform(5, 15)),
            ("fuel", fuel),  # Fuel level in litres
            ("ignition", True),
        )

        try:
            self.conn.request("GET", "/?" + urllib.parse.urlencode(params))
            response = self.conn.getresponse()
            response.read()

            if response.status == 200:
                self.points_sent += 1
                return True
            else:
                self.errors += 1
                return False

        except Exception as e:
            self.errors += 1
            self.conn = httplib.HTTPConnection(self.server)
            return False

    def print_progress(
        self,
        current: int,
        total: int,
        lat: float,
        lon: float,
        speed: float,
        fuel: float,
    ):
        """Print current progress with fuel level"""
        progress = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Fuel indicator
        fuel_percent = (fuel / FUEL_TANK_CAPACITY) * 100
        if fuel_percent > 50:
            fuel_icon = "⛽"
        elif fuel_percent > 20:
            fuel_icon = "🟨"
        else:
            fuel_icon = "⚠️"

        if speed == 0:
            status = "🅿️  PARKED"
        elif speed < 30:
            status = f"🚦 SLOW {speed:.0f} km/h"
        else:
            status = f"🚙 {speed:.0f} km/h"

        print(
            f"\r[{bar}] {progress:.1f}% | {status} | {fuel_icon} {fuel:.1f}L ({fuel_percent:.0f}%)",
            end="",
            flush=True,
        )

    def simulate_real_trip(
        self, points: List[Tuple[str, float, float, float, float, float]]
    ):
        """Simulate real-time GPS tracking with fuel monitoring"""
        print(f"\n{'='*70}")
        print(f"🚗 REAL-TIME GPS TRACKING - {CAR_NAME}")
        print(f"{'='*70}")
        print(f"📱 Device ID: {self.device_id}")
        print(f"🚙 Vehicle: {CAR_NAME} (Tank: {FUEL_TANK_CAPACITY}L)")
        print(f"📍 From: {points[0][1]:.6f}, {points[0][2]:.6f}")
        print(f"📍 To:   {points[-1][1]:.6f}, {points[-1][2]:.6f}")
        print(f"⏱️  Update interval: {UPDATE_INTERVAL} seconds")
        print(f"⛽ Starting fuel: {points[0][5]:.1f}L")
        print(f"\n🚦 Starting trip...\n")

        start_time = time.time()
        stopped_count = 0

        for i, (timestamp_str, lat, lon, speed, bearing, fuel) in enumerate(
            points
        ):
            dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            timestamp = time.mktime(dt.timetuple())

            self.send_position(timestamp, lat, lon, speed, bearing, fuel)

            if speed == 0:
                stopped_count += 1

            self.print_progress(i + 1, len(points), lat, lon, speed, fuel)

            # Real-time simulation
            time.sleep(UPDATE_INTERVAL)

        elapsed = time.time() - start_time
        fuel_used = points[0][5] - points[-1][5]

        print(f"\n\n{'='*70}")
        print(f"✅ TRIP COMPLETED!")
        print(f"{'='*70}")
        print(f"📤 Points sent: {self.points_sent}/{len(points)}")
        print(f"❌ Errors: {self.errors}")
        print(f"🅿️  Stopped updates: {stopped_count}")
        print(f"⛽ Fuel consumed: {fuel_used:.1f}L")
        print(f"⛽ Remaining fuel: {points[-1][5]:.1f}L")
        print(f"⏱️  Real time elapsed: {elapsed/60:.1f} minutes")
        print(f"\n🌐 View tracking: http://{self.server.split(':')[0]}:8082")
        print(f"{'='*70}\n")


def main():
    print("\n" + "=" * 70)
    print(f"🗺️  GPS TRACKER - {CAR_NAME} - Real Road Following")
    print("=" * 70)
    print(f"\n🚙 Vehicle: {CAR_NAME}")
    print(f"⛽ Fuel tank capacity: {FUEL_TANK_CAPACITY}L")
    print(f"📍 Route: {POINT_A} → {POINT_B}")
    print(f"⏱️  Updates every {UPDATE_INTERVAL} seconds")
    print(f"🚗 Average speed: {AVERAGE_SPEED_KMH} km/h")
    print(f"⛽ Fuel consumption: {FUEL_CONSUMPTION_RATE}L/100km")

    # Generate route using real roads
    route_gen = RealRoadRouteGenerator(POINT_A, POINT_B)
    points = route_gen.generate_gps_points_with_timing()

    print(f"\n✅ Route generated with {len(points)} GPS points")
    print(
        f"⏳ This simulation will take approximately {len(points) * UPDATE_INTERVAL / 60:.0f} minutes\n"
    )

    input("Press ENTER to start simulation (or Ctrl+C to cancel)...")

    # Start simulation
    simulator = TraccarSimulator(DEVICE_ID, SERVER)

    try:
        simulator.simulate_real_trip(points)
    except KeyboardInterrupt:
        print("\n\n⚠️  Trip interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        simulator.conn.close()


if __name__ == "__main__":
    main()
