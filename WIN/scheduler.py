import os
import sys
import time
import schedule
import requests
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta
from pytz import timezone


# Function to calculate satellite passes
def calculate_passes(satellite, observer, start_time, end_time, ts):
    t, events = satellite.find_events(observer, ts.from_datetime(start_time), ts.from_datetime(end_time), altitude_degrees=5)
    #print(f"{t} - {events}")

    passes = []
    alts=[]
    for i in range(len(events) - 1):
        if events[i] == 1:  # Satellite culminated and started to descend again
            culmination_time = t[i]
            alt, az, distance = (satellite - observer).at(culmination_time).altaz()
            if alt.degrees >= 30:  # Check if the satellite reached an elevation of 30° or more
                passes.append((t[i-1].astimezone(timezone('Europe/Rome')), t[i+1].astimezone(timezone('Europe/Rome'))))
                alts.append(alt)

    #print(passes)
    return passes ,alts

# Function to update TLE data
def update_tle_data():
    tle_data = {}
    tle_file = open("TLE.txt")
    s = tle_file.readlines()
    tle_file.close()
    if (datetime.now() - datetime.strptime(s[0].replace('\n',''), "%Y-%m-%d %H:%M:%S.%f")) > timedelta(days=2):
        print("tle out of date, updating...")
        url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle"
        response = requests.get(url)
        lines = response.text.split("\n")
        tle_file=open("TLE.txt", "w")
        tle_file.write(str(datetime.now()) + "\n")
        tle_file.write(response.text.replace("\n", ""))
        tle_file.close()
        l=0  
    else:
        lines=s
        l=1
    for i in range(l, len(lines) - 2, 3):
        if lines[i].strip():
            tle_data[lines[i].strip()] = (lines[i+1].strip(), lines[i+2].strip())
    #print(tle_data)
    return tle_data

# Clears the console
def clearConsole():
    command = "clear"
    if os.name in ("nt", "dos"):
        command = "cls"
    os.system(command)

# Function to print countdown to the next pass
def print_countdown(next_pass, next_sat):
    while datetime.now(timezone('Europe/Rome')) < next_pass:
        time_left = next_pass - datetime.now(timezone('Europe/Rome'))
        str_left = '{}:{}:{}'.format(time_left.seconds // 3600, (time_left.seconds // 60) % 60, time_left.seconds % 60)
        sys.stdout.write(f"\rNext pass in: {str_left} for {next_sat}    ")
        sys.stdout.flush()
        time.sleep(1)

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
    #print(start_time, end_time)

    # Load timescale
    ts = load.timescale()

    next_passes = []
    for satellite_name, frequency in satellites.items():
        tle1, tle2 = tle_data[satellite_name]
        satellite = EarthSatellite(tle1, tle2, satellite_name, ts)
        passes, alts = calculate_passes(satellite, observer, start_time, end_time, ts)


        #print(f"passaggi: {passes}")
        next_passes.extend([(pass_time[0], satellite_name) for pass_time in passes])
        for pass_time, alt in zip(passes, alts):
            begin=pass_time[0]
            end=pass_time[1]
            duration=(end-begin).total_seconds()
            print(f"Satellite: {satellite_name} - {begin.strftime('%d/%m %H:%M:%S')} - Duration: {int((duration// 60) % 60)} mins - Max elevation: {int(alt.degrees)}°")
            schedule.every().day.at(begin.strftime('%H:%M:%S')).do(os.system, f"python recieve_process_multithread_NFM.py {satellite_name.replace(" ","_")} {frequency} {tle1.replace(" ","_")} {tle2.replace(" ","_")}")

    # Start the countdown to the next pass
    next_passes.sort()
    if next_passes:
        next_pass, next_satellite = next_passes[0]
        print_countdown(next_pass, next_satellite)

# Start the scheduler
schedule_passes()

while True:
    schedule.run_pending()
    time.sleep(1)
