#!/usr/bin/env python3

import datetime
import http.client as httplib
import math
import random
import time
import urllib
from typing import List, Tuple

# Configuration
DEVICE_ID = "123456789012345"
SERVER = "35.192.21.69:5055"

# Real locations (St. Petersburg example - replace with your actual locations)
POINT_A = (59.93211887, 30.33050537)  # Starting point
POINT_B = (59.95000000, 30.36000000)  # Destination (~5km away)

# Simulation parameters
UPDATE_INTERVAL = 2  # Send GPS data every 2 seconds
TRIP_DURATION_MINUTES = 60  # Total trip duration: 1 hour
AVERAGE_SPEED_KMH = 40  # Average driving speed
PARKING_PROBABILITY = 0.15  # 15% chance of parking during trip


class RealisticRouteSimulator:
    """Simulate realistic GPS tracking on roads"""

    def __init__(
        self, start_point: Tuple[float, float], end_point: Tuple[float, float]
    ):
        self.start_lat, self.start_lon = start_point
        self.end_lat, self.end_lon = end_point

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance in meters between two GPS coordinates"""
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

    def add_road_curvature(
        self, points: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Add realistic road curves instead of straight lines"""
        curved_points = []

        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]

            curved_points.append((lat1, lon1))

            # Add intermediate points with slight random deviations (simulating road curves)
            num_intermediate = 3
            for j in range(1, num_intermediate):
                progress = j / num_intermediate

                # Linear interpolation
                mid_lat = lat1 + (lat2 - lat1) * progress
                mid_lon = lon1 + (lon2 - lon1) * progress

                # Add small perpendicular offset to simulate road curves
                bearing = self.calculate_bearing(lat1, lon1, lat2, lon2)
                perp_bearing = (bearing + 90) % 360

                # Small random deviation (max 20 meters to each side)
                deviation = random.uniform(-0.0002, 0.0002)  # ~20m
                mid_lat += deviation * math.cos(math.radians(perp_bearing))
                mid_lon += deviation * math.sin(math.radians(perp_bearing))

                curved_points.append((mid_lat, mid_lon))

        curved_points.append(points[-1])
        return curved_points

    def generate_realistic_trip(
        self,
    ) -> List[Tuple[str, float, float, float, float]]:
        """
        Generate realistic GPS points for 1-hour trip
        Returns: List of (timestamp, lat, lon, speed, bearing)
        """
        points = []
        current_time = datetime.datetime.now()

        # Calculate total distance and create waypoints
        total_distance = self.calculate_distance(
            self.start_lat, self.start_lon, self.end_lat, self.end_lon
        )

        # Create main waypoints (simulating major intersections/turns)
        num_waypoints = random.randint(4, 8)
        waypoints = [(self.start_lat, self.start_lon)]

        for i in range(1, num_waypoints):
            progress = i / num_waypoints
            # Add some randomness to waypoints to simulate actual road routes
            lat = (
                self.start_lat
                + (self.end_lat - self.start_lat) * progress
                + random.uniform(-0.002, 0.002)
            )
            lon = (
                self.start_lon
                + (self.end_lon - self.start_lon) * progress
                + random.uniform(-0.002, 0.002)
            )
            waypoints.append((lat, lon))

        waypoints.append((self.end_lat, self.end_lon))

        # Add road curvature
        route_points = self.add_road_curvature(waypoints)

        # Calculate time per segment
        total_points_needed = (TRIP_DURATION_MINUTES * 60) // UPDATE_INTERVAL
        points_per_segment = len(route_points)

        current_lat, current_lon = route_points[0]

        # Start position (stopped)
        points.append(
            (
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                current_lat,
                current_lon,
                0.0,
                0.0,
            )
        )

        segment_index = 0
        is_parked = False
        parking_duration = 0

        for i in range(1, total_points_needed):
            current_time += datetime.timedelta(seconds=UPDATE_INTERVAL)

            # Random parking event (not at start or end)
            if not is_parked and i > 50 and i < total_points_needed - 100:
                if (
                    random.random() < PARKING_PROBABILITY / 1000
                ):  # Adjusted probability
                    is_parked = True
                    parking_duration = random.randint(
                        30, 180
                    )  # 30 seconds to 3 minutes
                    print(
                        f"🅿️  Parking for {parking_duration} seconds at point {i}"
                    )

            if is_parked:
                # Stay at current position
                speed = 0.0
                bearing = points[-1][4] if points else 0.0
                parking_duration -= UPDATE_INTERVAL

                if parking_duration <= 0:
                    is_parked = False
                    print(f"🚗 Resuming trip")
            else:
                # Calculate progress through route
                progress = i / total_points_needed
                target_segment = int(progress * (len(route_points) - 1))

                if target_segment >= len(route_points) - 1:
                    target_segment = len(route_points) - 2

                # Interpolate between current segment points
                segment_progress = (progress * (len(route_points) - 1)) % 1.0

                lat1, lon1 = route_points[target_segment]
                lat2, lon2 = route_points[target_segment + 1]

                current_lat = lat1 + (lat2 - lat1) * segment_progress
                current_lon = lon1 + (lon2 - lon1) * segment_progress

                # Calculate realistic speed with variations
                base_speed = AVERAGE_SPEED_KMH
                speed_variation = random.uniform(
                    -15, 15
                )  # Speed varies ±15 km/h
                speed = max(
                    10, min(80, base_speed + speed_variation)
                )  # Between 10-80 km/h

                # Add traffic simulation (occasional slowdowns)
                if random.random() < 0.05:  # 5% chance of traffic
                    speed = random.uniform(5, 20)  # Slow down

                # Calculate bearing
                if len(points) > 0:
                    prev_lat, prev_lon = points[-1][1], points[-1][2]
                    bearing = self.calculate_bearing(
                        prev_lat, prev_lon, current_lat, current_lon
                    )
                else:
                    bearing = 0.0

                # Smooth speed transitions
                if len(points) > 0:
                    prev_speed = points[-1][3]
                    max_accel = 5  # Max speed change per update
                    if abs(speed - prev_speed) > max_accel:
                        speed = prev_speed + (
                            max_accel if speed > prev_speed else -max_accel
                        )

            points.append(
                (
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    current_lat,
                    current_lon,
                    speed,
                    bearing,
                )
            )

        # Final position (stopped at destination)
        current_time += datetime.timedelta(seconds=UPDATE_INTERVAL)
        points.append(
            (
                current_time.strftime("%Y-%m-%d %H:%M:%S"),
                self.end_lat,
                self.end_lon,
                0.0,
                bearing,
            )
        )

        return points


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
    ) -> bool:
        """Send GPS position to Traccar server"""
        params = (
            ("id", self.device_id),
            ("timestamp", int(timestamp)),
            ("lat", lat),
            ("lon", lon),
            ("speed", speed),
            ("bearing", bearing),
            ("altitude", 0),
            ("accuracy", random.uniform(5, 15)),  # GPS accuracy variation
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
        self, current: int, total: int, lat: float, lon: float, speed: float
    ):
        """Print current progress"""
        progress = (current / total) * 100
        bar_length = 40
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)

        status = "🛑 STOPPED" if speed == 0 else f"🚙 {speed:.1f} km/h"
        print(
            f"\r[{bar}] {progress:.1f}% | {status} | {lat:.6f}, {lon:.6f}",
            end="",
            flush=True,
        )

    def simulate_real_trip(
        self, points: List[Tuple[str, float, float, float, float]]
    ):
        """Simulate real-time GPS tracking"""
        print(f"\n{'='*70}")
        print(f"🚗 REALISTIC GPS TRACKING SIMULATION")
        print(f"{'='*70}")
        print(f"📱 Device ID: {self.device_id}")
        print(f"📍 From: {points[0][1]:.6f}, {points[0][2]:.6f}")
        print(f"📍 To:   {points[-1][1]:.6f}, {points[-1][2]:.6f}")
        print(f"📊 Total updates: {len(points)}")
        print(f"⏱️  Update interval: {UPDATE_INTERVAL} seconds")
        print(f"🕐 Trip duration: ~{TRIP_DURATION_MINUTES} minutes")
        print(f"\n🚦 Starting trip...\n")

        start_time = time.time()
        stopped_count = 0

        for i, (timestamp_str, lat, lon, speed, bearing) in enumerate(points):
            dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            timestamp = time.mktime(dt.timetuple())

            success = self.send_position(timestamp, lat, lon, speed, bearing)

            if speed == 0:
                stopped_count += 1

            self.print_progress(i + 1, len(points), lat, lon, speed)

            # Real-time simulation: wait for actual interval
            time.sleep(UPDATE_INTERVAL)

        elapsed = time.time() - start_time

        print(f"\n\n{'='*70}")
        print(f"✅ TRIP COMPLETED!")
        print(f"{'='*70}")
        print(f"📤 Points sent: {self.points_sent}/{len(points)}")
        print(f"❌ Errors: {self.errors}")
        print(f"🛑 Stopped updates: {stopped_count}")
        print(f"⏱️  Real time elapsed: {elapsed/60:.1f} minutes")
        print(
            f"\n🌐 View live tracking: http://{self.server.split(':')[0]}:8082"
        )
        print(f"{'='*70}\n")


def main():
    print("\n" + "=" * 70)
    print("🗺️  REALISTIC GPS TRACKER - ROAD FOLLOWING SIMULATION")
    print("=" * 70)
    print(f"\n📍 Route: Point A → Point B")
    print(f"⏱️  Updates every {UPDATE_INTERVAL} seconds")
    print(f"🕐 Duration: {TRIP_DURATION_MINUTES} minutes")
    print(f"🅿️  Random parking: Enabled")
    print(f"\n⏳ Generating realistic route...\n")

    # Generate realistic route
    route_sim = RealisticRouteSimulator(POINT_A, POINT_B)
    points = route_sim.generate_realistic_trip()

    print(f"✓ Generated {len(points)} GPS points with road following\n")

    # Start simulation
    simulator = TraccarSimulator(DEVICE_ID, SERVER)

    try:
        simulator.simulate_real_trip(points)
    except KeyboardInterrupt:
        print("\n\n⚠️  Trip interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
    finally:
        simulator.conn.close()


if __name__ == "__main__":
    main()
