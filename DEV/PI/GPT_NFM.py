import os
import sys
import time
import queue
import threading
import subprocess
from rtlsdr import RtlSdr
import numpy as np
from scipy.io.wavfile import write
from scipy.signal import butter, lfilter, decimate
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta, timezone

def azimuth_to_compass(azimuth):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    index = round((azimuth.degrees % 360) / 45)
    return directions[index]

# Function to calculate Doppler shift
def doppler_shift(frequency, velocity):
    speed_of_light = 299792458  # m/s
    dop_freq = frequency * (1 + velocity / speed_of_light)
    return dop_freq

# Function to tune RTL-SDR to a frequency
def set_frequency(sdr, frequency):
    sdr.set_center_freq(frequency)

def nfm_demodulate(samples, sample_rate, bandwidth, last_phase=0):
    phase = np.angle(samples)
    phase[0] += last_phase  # Adjust the first phase by adding the last phase from the previous chunk
    unwrapped_phase = np.unwrap(phase)
    phase_diff = np.diff(unwrapped_phase)
    demodulated_signal = np.concatenate(([0], phase_diff))  # Maintain the same length

    nyquist_rate = sample_rate / 2
    cutoff_freq = bandwidth / 2  # 34kHz bandwidth, so cutoff is 17kHz
    normalized_cutoff = cutoff_freq / nyquist_rate
    b, a = butter(4, normalized_cutoff, btype='low')

    filtered_signal = lfilter(b, a, demodulated_signal)

    decimation_factor = sample_rate // (2 * int(bandwidth))  # Ensure the final rate is above the Nyquist rate for 34kHz
    decimated_signal = decimate(filtered_signal, int(decimation_factor))  # Convert decimation_factor to int

    last_phase = unwrapped_phase[-1]  # Return the last phase value for the next chunk

    return decimated_signal, last_phase, decimation_factor


def process_data(rate, duration, data_queue, b_file_path, frequency, factor_queue):
    print("[Thread] >processing data and saving to binary file")
    last_phase = 0  # Initialize last phase
    total_decimation_factor = 1  # To accumulate decimation factors
    with open(b_file_path, 'wb') as f:
        start_time = time.time()
        while True:
            time_elapsed = time.time() - start_time
            if time_elapsed > duration and data_queue.empty():
                break
            elif time_elapsed > duration:
                print("[Thread] >pass ended, processing remaining data...")
            samples = data_queue.get()
            data_demodulated, last_phase, decimation_factor = nfm_demodulate(samples, rate, 34e3, last_phase)  # Pass and retrieve last phase
            total_decimation_factor *= decimation_factor  # Accumulate total decimation factor
            data_int = np.int16(data_demodulated * (2**15 - 1))
            if np.max(data_int) > 32767 or np.min(data_int) < -32768:
                print("Warning: Clipping detected")
            f.write(data_int.tobytes())
            data_queue.task_done()
    factor_queue.put(total_decimation_factor)  # Put the total decimation factor in the queue
    print("[Thread] >processing complete")

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

    # Define satellite
    satellite = EarthSatellite(tle1, tle2, satellite_name)

    # Find ongoing pass
    t0 = ts.utc(datetime.now(timezone.utc) - timedelta(minutes=5))  # current time
    t, events = satellite.find_events(observer, t0, t0 + timedelta(minutes=90), altitude_degrees=5)  # look for events in the next 40 minutes
    passes = [ti.utc_datetime() for ti, event in zip(t, events) if event in [0, 2]]  # consider only rising and setting events

    # Check if there is a pass happening right now
    if len(passes) < 2:
        print(f"Error, no pass detected for {satellite_name}")
        return

    cur_pass = passes[0]

    folder_path = os.path.join(r"C:\Users\alexa\Desktop\NOAA", satellite_name.replace(" ", "_"))
    os.makedirs(folder_path, exist_ok=True)  # Create folder if not exists
    file_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.wav")
    raw_folder_path = folder_path + r"\DATA_RAW"
    os.makedirs(raw_folder_path, exist_ok=True)
    bin_file_path = os.path.join(raw_folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.bin")
    duration = (passes[1] - passes[0]).total_seconds()

    data_queue = queue.Queue()
    factor_queue = queue.Queue()
    start_time = time.time()
    process_thread = threading.Thread(target=process_data, args=(sdr.sample_rate, duration, data_queue, bin_file_path, float(frequency) * 1e6, factor_queue))
    process_thread.start()

    while True:
        time_elapsed = time.time() - start_time
        if time_elapsed > duration:
            print("\npass complete, processing data...")
            break
        time_remaining = duration - time_elapsed
        progress_percent = int((time_elapsed / duration) * 100)

        t = ts.now()
        alt, az, distance = (satellite - observer).at(t).altaz()
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
        data_queue.put(samples)
        signal_strength = np.mean(np.abs(samples))

        # Print status update
        sys.stdout.write(f"\rPass Progress: {progress_percent}%, Time Remaining: {int((time_remaining// 60) % 60)}:{int(time_remaining%60)} - Signal Strength: {signal_strength:.2f}, current frequency: {adjusted_frequency} - Current elevation: {int(alt.degrees)}°, current azimuth: {int(az.degrees)}° {azimuth_to_compass(az)}               ")
        sys.stdout.flush()

    process_thread.join()

    # Get the total decimation factor from the queue
    total_decimation_factor = factor_queue.get()
    # Calculate the new sample rate after decimation
    final_sample_rate = sdr.sample_rate / total_decimation_factor
    print(final_sample_rate)
    # Convert the binary file to a WAV file
    print("Converting binary file to WAV format")
    data = np.fromfile(bin_file_path, dtype=np.int16)
    write(file_path, int(sdr.sample_rate), data)
    print(f"[WARNING]: check file duration, should be {duration} or {int((duration// 60) % 60)}:{int(duration %60)}!!")
    # Delete the binary file
    #os.remove(bin_file_path)

    # Close RTL-SDR connection
    sdr.close()
    print("processing images...")
    # Process the WAV file using WXtoImg for each image type
    if 'NOAA' in satellite_name:
        image_types = ['NO', 'MCIR', 'MSA', 'HVCT', 'HVCT-precip', 'sea', 'therm']
        for image_type in image_types:
            print(f">Processing {image_type} image")
            output_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}_{image_type}.png")
            subprocess.run([r"C:\Program Files (x86)\WXtoImg\wxtoimg.exe", "-n", f"-e{image_type}", "-o", "-tNOAA", file_path, output_path])
    else:
        pass
        # meteor satellite

# Main function
if __name__ == "__main__":
    #parametri ricevuti dallo scheduler
    """satellite_name = sys.argv[1].replace("_"," ")
    frequency = sys.argv[2]
    tle1 = sys.argv[3].replace("_"," ")
    tle2 = sys.argv[4].replace("_"," ")
    #print(sys.argv)"""

    #parametri inseriti manualmente per testare
    #consiglio prima di farlo di eseguire lo scheduler e poi sostituire i dati orbitali indicati con quelli in TLE.txt
    #per testare manualmente modificare il lasso di tempo alle righe 69-70 cambiando i parametri dei timedelta
    """satellite_name = 'NOAA 15'
    frequency = '137.6200'
    tle1='1 25338U 98030A   24159.48767669  .00000464  00000+0  21009-3 0  9993'
    tle2='2 25338  98.5687 186.8171 0010157   0.4342 359.6846 14.26596617356052'"""
    """satellite_name = 'NOAA 18'
    frequency = '137.9125'
    tle1='1 28654U 05018A   24149.45500860  .00000283  00000+0  17468-3 0  9998'
    tle2='2 28654  98.8743 226.5833 0015322 118.1096 242.1627 14.13217129980477'"""
    """satellite_name = 'NOAA 19'
    frequency = '137.1000'
    tle1='1 33591U 09005A   24149.47441550  .00000238  00000+0  15179-3 0  9993'
    tle2='2 33591  99.0481 205.0639 0013485 352.3873   7.7092 14.13013951788849'"""
    print(f"Processing pass for {satellite_name} at {frequency}MHz")
    receive_and_process_pass(satellite_name, frequency, tle1, tle2)
