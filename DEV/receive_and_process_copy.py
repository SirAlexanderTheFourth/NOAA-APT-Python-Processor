import os
import sys
import time
import subprocess
from rtlsdr import RtlSdr
import numpy as np
from scipy.io.wavfile import write
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt

# Function to calculate Doppler shift
def doppler_shift(frequency, velocity):
    speed_of_light = 299792458  # m/s
    dop_freq=frequency * (1 + velocity / speed_of_light)
    #print(dop_freq)
    return dop_freq

# Function to tune RTL-SDR to a frequency
def set_frequency(sdr, frequency):
    sdr.set_center_freq(frequency)

def am_demodulate(rate, data):  # Set chunk_size to a suitable value depending on your available memory
    chunk_size=int(rate)
    demodulated = np.zeros(len(data))
    total_chunks = len(data) // chunk_size
    for i in range(0, len(data), chunk_size):
        sys.stdout.write(f"\r>Demodulating chunk {i // chunk_size + 1} of {total_chunks}...")
        sys.stdout.flush()
        chunk = data[i:i+chunk_size]
        demodulated_chunk=np.abs(chunk)
        demodulated[i:i+chunk_size-1] = demodulated_chunk
    return demodulated

# Function to receive and process signals during a pass
def receive_and_process_pass(satellite_name, frequency, tle1, tle2):
    # Connect to RTL-SDR
    sdr = RtlSdr()

    # Set RTL-SDR parameters
    sdr.sample_rate = 2.4e6
    sdr.freq_correction = 60
    sdr.gain = 'auto'

    # Define observer location
    observer = Topos(44.384477, 7.542671, elevation_m=500)

    # Load timescale
    ts = load.timescale()
    #print(ts)
    # Define satellite
    satellite = EarthSatellite(tle1, tle2, satellite_name)
    print(satellite)

    # Find ongoing pass
    t0 = ts.utc(datetime.now(timezone.utc) - timedelta(minutes=60))  # current time
    t, events = satellite.find_events(observer, t0, t0 + timedelta(minutes=30), altitude_degrees=5)  # look for events in the next 40 minutes
    #print(f"T:{t}, eventi:{events}")
    passes = [ti.utc_datetime() for ti, event in zip(t, events) if event in [1, 2]]  # consider only rising and setting events

    # Check if there is a pass happening right now
    #print(len(passes))
    if len(passes) < 2:
        print(f"Error, no pass detected for {satellite_name}\n[debug data: {t0.utc_datetime()}---{(t0 + timedelta(minutes=40)).utc_datetime()}---{passes}]")
        return

    cur_pass = passes[0]

    # Adjust frequency for Doppler shift during the pass
    folder_path = os.path.join(r"C:\NOAA", satellite_name.replace(" ", "_"))
    os.makedirs(folder_path, exist_ok=True)  # Create folder if not exists
    file_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.wav")
    
    duration = (passes[1] - passes[0]).total_seconds()

    data = []
    start_time = time.time()
    while True:
        time_elapsed = time.time() - start_time
        if time_elapsed > duration:
            print("\npass complete, processing data...")
            break
        #print(f"\n{time_elapsed}, {duration//60%60}")
        time_remaining = duration - time_elapsed
        progress_percent = int((time_elapsed / duration) * 100)

        t = ts.now()
        geocentric = satellite.at(t)
        # Get the observer's geocentric position and velocity
        observer_geocentric = observer.at(t)
        # Calculate the relative position and velocity of the satellite with respect to the observer
        relative_position = geocentric.position.km - observer_geocentric.position.km
        relative_velocity = geocentric.velocity.km_per_s - observer_geocentric.velocity.km_per_s
        # Calculate the unit vector pointing from the observer to the satellite
        unit_vector = relative_position / np.linalg.norm(relative_position)
        # Calculate the component of the satellite's velocity along the line of sight
        relative_velocity_along_line_of_sight = np.dot(relative_velocity, unit_vector)
        # Use this relative velocity for the Doppler shift calculation
        adjusted_frequency = doppler_shift(float(frequency) * 1e6, relative_velocity_along_line_of_sight)
        set_frequency(sdr, adjusted_frequency)
        samples = sdr.read_samples(int(sdr.sample_rate))
        data.append(samples)

        signal_strength = np.mean(np.abs(samples))
        
        # Print status update
        sys.stdout.write(f"\rPass Progress: {progress_percent}%, Time Remaining: {int((time_remaining// 60) % 60)}:{int(time_remaining%60)} - Signal Strength: {signal_strength:.2f}, current frequency: {adjusted_frequency} - Number of samples: {len(samples)}, Sample rate: {sdr.sample_rate}")
        sys.stdout.flush()
    

    # Save received audio as WAV file
    print(">Concatenating data...")
    data = np.concatenate(data)
    print(">Demodulating data...")
    data_demodulated = am_demodulate(sdr.sample_rate, data)  # Demodulate the data
    print("\n>Converting to 16-bit integers...")
    data_int = np.int16(data_demodulated / np.max(np.abs(data_demodulated)) * (2**15 - 1))  # Convert the real numbers to 16-bit integers
    if np.max(data_int) > 32767 or np.min(data_int) < -32768:
        print("Warning: Clipping detected")
    print(f"writing to file to {file_path} ...")
    write(file_path, int(sdr.sample_rate), data_int)

    # Close RTL-SDR connection
    sdr.close()
    print("processing images...")
    # Process the WAV file using WXtoImg for each image type
    if 'NOAA' in satellite_name :
        image_types = ['NO', 'MCIR', 'MSA', 'HVCT', 'HVCT-precip', 'sea', 'therm']
        for image_type in image_types:
            print(f">Processing {image_type} image")
            subprocess.run([r"C:\Program Files (x86)\WXtoImg\wxtoimg.exe", "-n", f"-e{image_type}", "-o", folder_path, file_path])
    else:
        pass
        #meteor satellite

# Main function
if __name__ == "__main__":
    """# Parse command-line arguments
    satellite_name = sys.argv[1].replace("_"," ")
    frequency = sys.argv[2]
    tle1 = sys.argv[3].replace("_"," ")
    tle2 = sys.argv[4].replace("_"," ")
    #print(sys.argv)"""
    """satellite_name = 'NOAA 15'
    frequency = '137.6200'
    tle1='1 25338U 98030A   24115.51118005  .00000653  00000+0  28852-3 0  9996'
    tle2='2 25338  98.5736 143.7484 0011476 119.3572 240.8756 14.26547466349787'"""
    """satellite_name = 'NOAA 18'
    frequency = '137.9125'
    tle1='1 28654U 05018A   24115.39971650  .00000597  00000+0  34229-3 0  9995'
    tle2='2 28654  98.8750 192.8099 0013836 211.6711 148.3630 14.13179526975669'"""
    satellite_name = 'NOAA 19'
    frequency = '137.1000'
    tle1='1 33591U 09005A   24115.48526765  .00000565  00000+0  32702-3 0  9993'
    tle2='2 33591  99.0518 170.7061 0014862  85.0633 275.2235 14.12979578784045'
    print(f"Processing pass for {satellite_name} at {frequency}MHz") #\n[orbital data: {tle1}, {tle2}]
    receive_and_process_pass(satellite_name, frequency, tle1, tle2)