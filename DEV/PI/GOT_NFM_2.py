import os
import sys
import time
import queue
import threading
import subprocess
import numpy as np
from rtlsdr import RtlSdr
from scipy.io.wavfile import write
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta, timezone
import wave

def azimuth_to_compass(azimuth):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    index = round((azimuth.degrees % 360) / 45)
    return directions[index]

def doppler_shift(frequency, velocity):
    speed_of_light = 299792458  # m/s
    dop_freq = frequency * (1 + velocity / speed_of_light)
    return dop_freq

def set_frequency(sdr, frequency):
    sdr.center_freq = frequency

def demodulate_nfm(complex_samples, sample_rate):
    """
    Demodulate Narrowband FM (NFM) from a vector of complex samples.
    
    Parameters:
    complex_samples (numpy array): Vector of complex samples from the SDR.
    sample_rate (int): Sample rate of the input signal.
    
    Returns:
    demodulated_signal (numpy array): Demodulated audio signal.
    """
    # Calculate the instantaneous phase
    instantaneous_phase = np.angle(complex_samples)

    # Unwrap the phase to prevent discontinuities
    unwrapped_phase = np.unwrap(instantaneous_phase)

    # Differentiate the unwrapped phase to get frequency deviation
    frequency_deviation = np.diff(unwrapped_phase)

    # Append a zero to maintain the same length
    frequency_deviation = np.append(frequency_deviation, 0)

    # Normalize the frequency deviation
    frequency_deviation = frequency_deviation / (2.0 * np.pi)

    return frequency_deviation

def process_data(rate, duration, data_queue, bin_file_path, center_freq, bandwidth):
    print("[Thread] > Processing data and saving to binary file")
    with open(bin_file_path, 'wb') as f:
        start_time = time.time()
        while True:
            time_elapsed = time.time() - start_time
            if time_elapsed > duration and data_queue.empty():
                break
            elif time_elapsed > duration:
                print("[Thread] > Pass ended, processing remaining data...")

            samples = data_queue.get()
            demodulated_chunk = demodulate_nfm(samples, rate)
            f.write(demodulated_chunk.astype(np.float32).tobytes())
            data_queue.task_done()
    print("[Thread] > Processing complete")

def save_as_wav(bin_file_path, sample_rate, filename):
    """
    Convert a binary file to a WAV file.
    
    Parameters:
    bin_file_path (str): The path to the binary file.
    sample_rate (int): The sample rate of the audio signal.
    filename (str): The filename for the output WAV file.
    """
    # Read the binary file
    with open(bin_file_path, 'rb') as f:
        raw_data = np.frombuffer(f.read(), dtype=np.float32)
    
    # Normalize the signal to the range [-32767, 32767]
    signal = np.int16(raw_data / np.max(np.abs(raw_data)) * 32767)
    
    # Write the signal to a WAV file
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit samples
        wf.setframerate(sample_rate)
        wf.writeframes(signal.tobytes())

def receive_and_process_pass(satellite_name, frequency, tle1, tle2):
    sdr = RtlSdr()
    sdr.sample_rate = 1.024e6  # Adjusted sample rate for POES APT
    sdr.freq_correction = 60
    sdr.gain = 'auto'

    observer = Topos(44.384477, 7.542671, elevation_m=500)
    ts = load.timescale()
    satellite = EarthSatellite(tle1, tle2, satellite_name)

    t0 = ts.utc(datetime.now(timezone.utc) - timedelta(minutes=5))
    t, events = satellite.find_events(observer, t0, t0 + timedelta(minutes=100), altitude_degrees=5)
    passes = [ti.utc_datetime() for ti, event in zip(t, events) if event in [0, 2]]

    if len(passes) < 2:
        print(f"Error, no pass detected for {satellite_name}")
        return

    cur_pass = passes[0]
    folder_path = os.path.join("./NOAA", satellite_name.replace(" ", "_"))
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.wav")
    raw_folder_path = os.path.join(folder_path, "DATA_RAW")
    os.makedirs(raw_folder_path, exist_ok=True)
    bin_file_path = os.path.join(raw_folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.bin")
    duration = (passes[1] - passes[0]).total_seconds()

    data_queue = queue.Queue()
    start_time = time.time()
    process_thread = threading.Thread(target=process_data, args=(sdr.sample_rate, duration, data_queue, bin_file_path, float(frequency) * 1e6, 34e3))
    process_thread.start()

    while True:
        time_elapsed = time.time() - start_time
        if time_elapsed > duration:
            print("\nPass complete, processing data...")
            break
        time_remaining = duration - time_elapsed
        progress_percent = int((time_elapsed / duration) * 100)

        t = ts.now()
        alt, az, distance = (satellite - observer).at(t).altaz()
        geocentric = satellite.at(t)
        observer_geocentric = observer.at(t)
        relative_position = geocentric.position.km - observer_geocentric.position.km
        relative_velocity = geocentric.velocity.km_per_s - observer_geocentric.velocity.km_per_s
        unit_vector = relative_position / np.linalg.norm(relative_position)
        relative_velocity_along_line_of_sight = np.dot(relative_velocity, unit_vector)
        adjusted_frequency = doppler_shift(float(frequency) * 1e6, relative_velocity_along_line_of_sight)
        set_frequency(sdr, adjusted_frequency)
        samples = sdr.read_samples(int(sdr.sample_rate / 10))
        data_queue.put(samples)
        signal_strength = np.mean(np.abs(samples))

        sys.stdout.write(f"\rPass Progress: {progress_percent}%, Time Remaining: {int((time_remaining // 60) % 60)}:{int(time_remaining % 60)} - Signal Strength: {signal_strength:.2f}, current frequency: {adjusted_frequency} - Current elevation: {int(alt.degrees)}°, current azimuth: {int(az.degrees)}° {azimuth_to_compass(az)}               ")
        sys.stdout.flush()

    process_thread.join()

    save_as_wav(bin_file_path, 48000, file_path)  # Assume final audio sample rate is 48000

    sdr.close()

    print("Processing images...")
    if 'NOAA' in satellite_name:
        image_types = ['NO', 'MCIR', 'MSA', 'HVCT', 'HVCT-precip', 'sea', 'therm']
        for image_type in image_types:
            print(f">Processing {image_type} image")
            output_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}_{image_type}.png")
            subprocess.run(["wxtoimg", "-n", f"-e{image_type}", "-o", "-tNOAA", file_path, output_path])
    else:
        pass

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