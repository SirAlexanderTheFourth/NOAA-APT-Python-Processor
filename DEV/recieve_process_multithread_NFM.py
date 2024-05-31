import os
import sys
import time
import queue
import threading
import subprocess
from rtlsdr import RtlSdr
import numpy as np
from scipy.io.wavfile import write
from scipy.signal import butter, lfilter
from skyfield.api import Topos, load, EarthSatellite
from datetime import datetime, timedelta, timezone


def azimuth_to_compass(azimuth):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    index = round((azimuth.degrees % 360) / 45)
    return directions[index]

# Function to calculate Doppler shift
def doppler_shift(frequency, velocity):
    speed_of_light = 299792458  # m/s
    dop_freq=frequency * (1 + velocity / speed_of_light)
    #print(dop_freq)
    return dop_freq

# Function to tune RTL-SDR to a frequency
def set_frequency(sdr, frequency):
    sdr.set_center_freq(frequency)
"""def fm_demod(data, df=1.0, fc):
    ''' Perform FM demodulation of complex carrier.

    Args:
        x (array):  FM modulated complex carrier.
        df (float): Normalized frequency deviation [Hz/V].
        fc (float): Normalized carrier frequency.

    Returns:
        Array of real modulating signal.
    '''

    # Remove carrier.
    n = np.arange(len(data))
    rx = data*np.exp(-1j*2*np.pi*fc*n)

    # Extract phase of carrier.
    phi = np.arctan2(np.imag(rx), np.real(rx))

    # Calculate frequency from phase.
    y = np.diff(np.unwrap(phi)/(2*np.pi*df))

    return y"""


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def fm_demodulate(data, last_phase):
    # Compute the phase of the data
    phase = np.angle(data)
    # Adjust the first phase value by adding the last phase from the previous chunk
    phase[0] += last_phase
    # Unwrap the phase to remove discontinuities
    unwrapped_phase = np.unwrap(phase)
    # Compute the derivative of the phase
    derivative = np.diff(unwrapped_phase)
    # Compute the last phase value for the next chunk
    last_phase = unwrapped_phase[-1]
    return derivative, last_phase

def process_data(rate, duration, data_queue, b_file_path, frequency):
    print("[Thread] >processing data and saving to binary file")
    last_phase = 0  # Variable to store the last phase value
    with open(b_file_path, 'wb') as f:
        start_time = time.time()
        while True:
            time_elapsed = time.time() - start_time
            if time_elapsed > duration and data_queue.empty():
                break
            elif time_elapsed > duration:
                print("[Thread] >pass ended, processing remaining data...")
            # Get a chunk of data from the queue and process it
            samples = data_queue.get()
            # Demodulate the data and update the last phase value
            filtered_data=butter_bandpass_filter(samples, frequency, 34e3, rate)
            data_demodulated, last_phase = fm_demodulate(filtered_data, last_phase)
            #resampled_data = resample_poly(data_demodulated, up=11025, down=rate) #resample data to 11025Hz to save memory and conform to WxtoImg values
            #data_int = np.int16(resampled_data / np.max(np.abs(resampled_data)) * (2**15 - 1))  # Convert the real numbers to 16-bit integers
            # Convert to int16
            #data_rounded = np.around(data_demodulated)
            #data_int = data_rounded.astype(np.int16)
            data_int = np.int16(data_demodulated * (2**15 - 1))
            if np.max(data_int) > 32767 or np.min(data_int) < -32768:
                print("Warning: Clipping detected")
            # Write the processed data to the binary file immediately
            f.write(data_int.tobytes())
            # Mark the task as done after processing
            data_queue.task_done()
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
    #print(ts)
    # Define satellite
    satellite = EarthSatellite(tle1, tle2, satellite_name)
    #print(satellite)

    # Find ongoing pass
    t0 = ts.utc(datetime.now(timezone.utc) - timedelta(minutes=5))  # current time
    t, events = satellite.find_events(observer, t0, t0 + timedelta(minutes=50), altitude_degrees=5)  # look for events in the next 40 minutes
    #print(f"T:{t}, eventi:{events}")
    passes = [ti.utc_datetime() for ti, event in zip(t, events) if event in [0, 2]]  # consider only rising and setting events

    # Check if there is a pass happening right now
    #print(len(passes))
    if len(passes) < 2:
        print(f"Error, no pass detected for {satellite_name}")
        return

    cur_pass = passes[0]


    folder_path = os.path.join(r"C:\Users\alexa\Desktop\NOAA", satellite_name.replace(" ", "_"))
    os.makedirs(folder_path, exist_ok=True)  # Create folder if not exists
    file_path = os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.wav")
    raw_folder_path=folder_path + r"\DATA_RAW"
    os.makedirs(raw_folder_path, exist_ok=True)
    bin_file_path=os.path.join(raw_folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}.bin")
    duration = (passes[1] - passes[0]).total_seconds()

    data_queue = queue.Queue()
    start_time = time.time()
    process_thread = threading.Thread(target=process_data, args=(sdr.sample_rate, duration, data_queue, bin_file_path, float(frequency) * 1e6))
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
    if 'NOAA' in satellite_name :
        image_types = ['NO', 'MCIR', 'MSA', 'HVCT', 'HVCT-precip', 'sea', 'therm']
        for image_type in image_types:
            print(f">Processing {image_type} image")
            output_path=os.path.join(folder_path, f"{satellite_name.replace(' ', '_')}_{cur_pass.strftime('%d-%m-%y_%H-%M-%S')}_{image_type}.png")
            subprocess.run([r"C:\Program Files (x86)\WXtoImg\wxtoimg.exe", "-n", f"-e{image_type}", "-o", "-tNOAA", file_path, output_path])
    else:
        pass
        #meteor satellite

# Main function
if __name__ == "__main__":
    # Parse command-line arguments
    """satellite_name = sys.argv[1].replace("_"," ")
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
    tle1='1 28654U 05018A   24123.18790732  .00000331  00000+0  20054-3 0  9998'
    tle2='2 28654  98.8746 200.5340 0014240 189.3128 170.7782 14.13187184976761'"""
    satellite_name = 'NOAA 19'
    frequency = '137.1000'
    tle1='1 33591U 09005A   24141.82693966  .00000484  00000+0  28357-3 0  9999'
    tle2='2 33591  99.0486 197.3345 0013878  14.0975 346.0581 14.13007727787768'
    print(f"Processing pass for {satellite_name} at {frequency}MHz") #\n[orbital data: {tle1}, {tle2}]
    receive_and_process_pass(satellite_name, frequency, tle1, tle2)


