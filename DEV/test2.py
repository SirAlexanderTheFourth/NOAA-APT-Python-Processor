import os
import sys
import time
import subprocess
from rtlsdr import RtlSdr
import numpy as np
from scipy.io.wavfile import write
from beyond.dates import Date
from beyond.frames import create_station
from beyond.orbits import Orbit
from beyond.utils import doppler_shift
import matplotlib.pyplot as plt

# Function to tune RTL-SDR to a frequency
def set_frequency(sdr, frequency):
    sdr.set_center_freq(frequency)

# Function to receive and process signals during a pass
def receive_and_process_pass(satellite_name, frequency, tle1, tle2):
    # Connect to RTL-SDR
    sdr = RtlSdr()

    # Set RTL-SDR parameters
    sdr.sample_rate = 2.4e6
    sdr.freq_correction = 60
    sdr.gain = 'auto'

    # Define observer location
    station = create_station("Observer", (44.384477, 7.542671, 500))

    # Define satellite
    orb = Orbit.from_tle(tle1, tle2, satellite_name)

    # Find ongoing pass
    now = Date.now()
    end = now + 5 * 60  # Search for next 5 minutes
    passes = [(start.utc, end.utc) for start, end in orb.visibility(station, now, end)]

    # Check if there is a pass happening right now
    if not passes:
        print(f"Error, no pass detected for {satellite_name}")
        return

    cur_pass_start, cur_pass_end = passes[0]

    # Adjust frequency for Doppler shift during the pass
    folder_path = os.path.join(r"C:\NOAA", satellite_name.replace(" ", "_"))
    os.makedirs(folder_path, exist_ok=True)  # Create folder if not exists
    file_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass_start.strftime('%d-%m-%y_%H-%M-%S')}.wav")
    
    duration = (cur_pass_end - cur_pass_start).total_seconds()

    data = []
    start_time = time.time()
    while True:
        time_elapsed = time.time() - start_time
        if time_elapsed > duration:
            print("\npass complete, processing data...")
            break
        time_remaining = duration - time_elapsed
        progress_percent = int((time_elapsed / duration) * 100)

        t = Date.now()
        dop = doppler_shift(orb, station, t)
        adjusted_frequency = float(frequency) * 1e6 + dop
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
    data_demodulated = fm_demodulate(sdr, data)  # Demodulate the data
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
    # Parse command-line arguments
    satellite_name = sys.argv[1].replace("_"," ")
    frequency = sys.argv[2]
    tle1 = sys.argv[3].replace("_"," ")
    tle2 = sys.argv[4].replace("_"," ")
    print(f"Processing pass for {satellite_name} at {frequency}MHz") #\n[orbital data: {tle1}, {tle2}]
    receive_and_process_pass(satellite_name, frequency, tle1, tle2)
