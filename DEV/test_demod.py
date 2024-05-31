import numpy as np
from scipy.io.wavfile import write
from rtlsdr import RtlSdr

# Function to perform AM demodulation
def am_demodulate(samples):
    # Compute the envelope of the signal
    envelope = np.abs(samples)
    return envelope

# Set up RTL-SDR
sdr = RtlSdr()

# Configure RTL-SDR parameters
sdr.sample_rate = 2.4e6  # Sample rate (Hz)
sdr.center_freq = 137e6  # Center frequency (Hz) for NOAA APT signals
sdr.freq_correction = 60  # Frequency correction (ppm)
sdr.gain = 'auto'        # Automatic gain control

# Number of samples to capture
num_samples = 8192

try:
    # Capture samples from RTL-SDR
    samples = sdr.read_samples(num_samples)

    # Demodulate the captured samples using AM demodulation
    demodulated_audio = am_demodulate(samples)

    # Scale the demodulated audio to 16-bit integer range (-32768 to 32767)
    demodulated_audio_scaled = np.int16(demodulated_audio * 32767)

    # Save the demodulated audio as a WAV file
    write('output.wav', int(sdr.sample_rate), demodulated_audio_scaled)

    print("Demodulated audio saved as 'output.wav'")

except Exception as e:
    print(f"Error: {e}")

finally:
    # Close RTL-SDR connection
    sdr.close()


# Function to perform AM demodulation
def am_demodulate(samples):
    # Compute the envelope of the signal
    envelope = np.abs(samples)
    return envelope

# Set up RTL-SDR
sdr = RtlSdr()

# Configure RTL-SDR parameters
sdr.sample_rate = 2.4e6  # Sample rate (Hz)
sdr.center_freq = 137e6  # Center frequency (Hz) for NOAA APT signals
sdr.freq_correction = 60  # Frequency correction (ppm)
sdr.gain = 'auto'        # Automatic gain control

# Duration of the transmission in seconds
transmission_duration = 15 * 60

# Sample rate
sample_rate = int(sdr.sample_rate)

# Total number of samples to capture
total_samples = int(sample_rate * transmission_duration)

try:
    # Initialize an empty array to store the demodulated audio
    demodulated_audio = np.array([])

    # Capture samples in chunks until enough samples are collected
    samples_collected = 0
    while samples_collected < total_samples:
        # Calculate the number of samples to capture in this iteration
        samples_to_capture = min(sample_rate, total_samples - samples_collected)

        # Capture samples from RTL-SDR
        samples = sdr.read_samples(samples_to_capture)

        # Demodulate the captured samples using AM demodulation
        demodulated_audio_chunk = am_demodulate(samples)

        # Append the demodulated audio chunk to the array
        demodulated_audio = np.concatenate((demodulated_audio, demodulated_audio_chunk))

        # Update the total number of samples collected
        samples_collected += samples_to_capture

    # Scale the demodulated audio to 16-bit integer range (-32768 to 32767)
    demodulated_audio_scaled = np.int16(demodulated_audio * 32767)

    # Save the demodulated audio as a WAV file
    write('output.wav', sample_rate, demodulated_audio_scaled)

    print("Demodulated audio saved as 'output.wav'")

except Exception as e:
    print(f"Error: {e}")

finally:
    # Close RTL-SDR connection
    sdr.close()
