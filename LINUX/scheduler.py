import os
import sys
import time
import requests
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta
from pytz import timezone
from crontab import CronTab

# Function to calculate satellite passes
def calculate_passes(satellite, observer, start_time, end_time, ts):
    t, events = satellite.find_events(observer, ts.from_datetime(start_time), ts.from_datetime(end_time), altitude_degrees=5)
    passes = []
    alts = []
    for i in range(len(events) - 1):
        if events[i] == 1:  # Satellite culminated and started to descend again
            culmination_time = t[i]
            alt, az, distance = (satellite - observer).at(culmination_time).altaz()
            if alt.degrees >= 30:  # Check if the satellite reached an elevation of 30° or more
                passes.append((t[i-1].astimezone(timezone('Europe/Rome')), t[i+1].astimezone(timezone('Europe/Rome'))))
                alts.append(alt)
    return passes, alts

# Function to update TLE data
def update_tle_data():
    tle_data = {}
    with open("TLE.txt") as tle_file:
        s = tle_file.readlines()
    if (datetime.now() - datetime.strptime(s[0].replace('\n', ''), "%Y-%m-%d %H:%M:%S.%f")) > timedelta(days=2):
        print("TLE out of date, updating...")
        url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle"
        response = requests.get(url)
        lines = response.text.split("\n")
        with open("TLE.txt", "w") as tle_file:
            tle_file.write(str(datetime.now()) + "\n")
            tle_file.write(response.text.replace("\n", ""))
        l = 0
    else:
        lines = s
        l = 1
    for i in range(l, len(lines) - 2, 3):
        if lines[i].strip():
            tle_data[lines[i].strip()] = (lines[i+1].strip(), lines[i+2].strip())
    return tle_data

# Function to schedule passes and setup executions
def schedule_passes():
    # Define observer location
    observer = Topos(44.384477, 7.542671, elevation_m=500)

    # Define satellite objects
    satellites = {
        'NOAA 15': '137.6200',
        'NOAA 18': '137.9125',
        'NOAA 19': '137.1000'
    }

    # Update TLE data
    tle_data = update_tle_data()

    # Define start and end times for calculation
    start_time = datetime.now(timezone('Europe/Rome'))
    end_time = start_time + timedelta(days=1)  # Calculate passes for next 24 hours

    # Load timescale
    ts = load.timescale()

    next_passes = []
    cron = CronTab(user=True)

    for satellite_name, frequency in satellites.items():
        tle1, tle2 = tle_data[satellite_name]
        satellite = EarthSatellite(tle1, tle2, satellite_name, ts)
        passes, alts = calculate_passes(satellite, observer, start_time, end_time, ts)

        next_passes.extend([(pass_time[0], satellite_name) for pass_time in passes])
        for pass_time, alt in zip(passes, alts):
            begin = pass_time[0]
            end = pass_time[1]
            duration = (end - begin).total_seconds()
            print(f"Satellite: {satellite_name} - {begin.strftime('%d/%m %H:%M:%S')} - Duration: {int((duration // 60) % 60)} mins - Max elevation: {int(alt.degrees)}°")

            # Create cron job
            job = cron.new(command=f"python3 recieve_process_multithread_AM.py {satellite_name.replace(' ', '_')} {frequency} {tle1.replace(' ', '_')} {tle2.replace(' ', '_')}")
            job.minute.on(begin.minute)
            job.hour.on(begin.hour)
            job.dom.on(begin.day)
            job.month.on(begin.month)
            job.dow.on('*')  # Every day of the week
            cron.write()

    # Start the countdown to the next pass
    next_passes.sort()
    if next_passes:
        next_pass, next_satellite = next_passes[0]
        print_countdown(next_pass, next_satellite)

# Function to print countdown to the next pass
def print_countdown(next_pass, next_sat):
    while datetime.now(timezone('Europe/Rome')) < next_pass:
        time_left = next_pass - datetime.now(timezone('Europe/Rome'))
        str_left = '{}:{}:{}'.format(time_left.seconds // 3600, (time_left.seconds // 60) % 60, time_left.seconds % 60)
        sys.stdout.write(f"\rNext pass in: {str_left} for {next_sat}    ")
        sys.stdout.flush()
        time.sleep(1)

# Clears the console
def clearConsole():
    command = "clear"
    if os.name in ("nt", "dos"):
        command = "cls"
    os.system(command)

# Main function to run the scheduler and set up cron jobs
if __name__ == "__main__":
    schedule_passes()

    # Create cron job for this script to run daily
    cron = CronTab(user=True)
    job = cron.new(command=f"python3 {os.path.abspath(__file__)}")
    job.minute.on(0)
    job.hour.on(0)
    job.dom.on('*')
    job.month.on('*')
    job.dow.on('*')
    cron.write()
