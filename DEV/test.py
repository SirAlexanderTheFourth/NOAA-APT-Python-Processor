import subprocess

#subprocess.run([r"C:\Program Files (x86)\WXtoImg\wxtoimg.exe", "-n", f"-eHVCT", "-o", r"C:\Users\alexa\Desktop\NOAA\NOAA_19\NOAA_19_02-05-24_18-38-08.wav", r"C:\Users\alexa\Desktop\NOAA\NOAA_19\NOAA_19_02-05-24_18-38-08_HVCT.png"])
subprocess.run([r"C:\Program Files (x86)\WXtoImg\wxtoimg.exe", 
                "-n", 
                "-eHVCT", 
                #"-f2400000",  # Replace with the actual sample rate
                "-o",
                "-tNOAA",  # Replace with the actual satellite name 
                r"C:\Users\alexa\Desktop\NOAA\NOAA_19\NOAA_19_02-05-24_20-17-03.wav", 
                r"C:\Users\alexa\Desktop\NOAA\NOAA_19\NOAA_19_02-05-24_20-17-03_HVCT.png"])

"""
    # Resample to 11025 Hz
from scipy.io.wavfile import write
from scipy.signal import resample_poly
import numpy as np

data = np.fromfile(r"C:\Users\alexa\Desktop\NOAA\NOAA_19\DATA_RAW\NOAA_19_02-05-24_20-17-03.bin", dtype=np.int16)
print("normalizing data...")
data_r= data / np.max(np.abs(data))
print("Resampling data...")
resampled_data = resample_poly(data_r, up=11025, down=2400000)
write(r"C:\Users\alexa\Desktop\NOAA\NOAA_19\NOAA_19_02-05-24_20-17-03.wav", 11025, resampled_data)
print("file saved succesfully")
"""