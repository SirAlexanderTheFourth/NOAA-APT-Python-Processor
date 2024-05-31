# NOAA-APT-Python-Processor
A repository aiming to to schedule, tune in and process NOAA POES passes by recieving their APT signal and converting it to images

## NOAA POES SATELLITES
<img src="https://cdn.mos.cms.futurecdn.net/Sx2PsebqPzCPCMnau3K5Bh-1200-80.jpg" width="75%" height="75%">

The **Polar Operational Environmental Satellites (POES)** are a constellation of polar-orbiting weather satellites funded by the National Oceanic and Atmospheric Administration (NOAA). These satellites play a crucial role in improving the accuracy and detail of weather analysis and forecasting. Here are some key points about the POES system:

1. **Orbit and Coverage**:
   - POES satellites orbit the Earth in an almost north-south direction, passing close to both poles.
   - They make nearly polar orbits approximately 520 miles (about 837 kilometers) above the Earth's surface.
   - The Earth's rotation allows each satellite to capture a different view with each orbit.
   - Each POES satellite provides two complete views of weather around the world every day.
   - The advantage of this polar orbit is daily global coverage.

2. **Instrumentation**:
   - The POES instruments include the **Advanced Very High Resolution Radiometer (AVHRR)**, which provides visible, infrared, and microwave data.
   - The **Advanced TIROS Operational Vertical Sounder (ATOVS)** suite complements AVHRR by providing additional data for applications such as cloud and precipitation monitoring, surface property determination, and humidity profiles.
   - The **Microwave Humidity Sounder (MHS)**, provided by EUMETSAT, completes the ATOVS suite.

3. **Applications**:
   - Data from the POES series supports various environmental monitoring applications, including:
     - Weather analysis and forecasting.
     - Climate research and prediction.
     - Global sea surface temperature measurements.
     - Atmospheric soundings of temperature and humidity.
     - Ocean dynamics research.
     - Volcanic eruption monitoring.
     - Forest fire detection.
     - Global vegetation analysis.
     - Search and rescue operations.

4. **Orbit Details**:
   - The orbits are circular, with altitudes between 830 km (morning orbit) and 870 km (afternoon orbit).
   - The satellites are sun-synchronous, meaning they cross the equator at specific local times (7:30 a.m. and 1:40 p.m.).
   - Operating as a pair, these satellites ensure that data for any region of the Earth are no more than six hours old.

In summary, the POES satellites provide critical data for weather monitoring, climate research, and various environmental applications, contributing to our understanding of Earth's atmosphere and surface¹². You can find more information on the latest POES satellite status [here](https://www.ospo.noaa.gov/Operations/POES/status.html).

## THE APT SIGNAL
![image](https://github.com/SirAlexanderTheFourth/NOAA-APT-Python-Processor/assets/113352655/50c63aba-64ff-4d0f-92a6-30fea0ad18c9)


The **Automatic Picture Transmission (APT)** format is a method used to transmit weather satellite images from polar-orbiting satellites to ground stations. Here's a concise overview:

1. **Purpose**:
   - APT is primarily used for transmitting visible and infrared images of Earth's surface, including cloud cover, weather patterns, and other meteorological features.
   - These images help meteorologists monitor and analyze weather conditions globally.

2. **Transmission Process**:
   - APT images are transmitted via radio signals in the VHF (Very High Frequency) band.
   - The satellite scans the Earth's surface and converts the image data into a series of audio tones.
   - Ground stations receive these tones and decode them back into visual images.

3. **Image Characteristics**:
   - APT images are typically black and white (grayscale).
   - They have a resolution of around 4 kilometers per pixel.
   - Each image covers a swath of approximately 2,000 kilometers wide.

4. **Reception and Decoding**:
   - Hobbyists and amateur radio operators can receive APT signals using simple equipment, such as a VHF receiver and a computer.
   - Specialized software decodes the audio tones and reconstructs the image.

## HOW TO INSTALL
first of all you will need to install the dependencies:
```TERMINAL
pip install dependencies.txt
```

### Windows:




### Linux:
you will need to download and install	[pycsdr](https://github.com/jketterl/pycsdr)
