# Piano-Hand-Electrical

Electrical Division of Piano Hand in the Autonomous Robotics Club

## Setup

## SRC information:
The code is adapted from Spring 2024 and has outdated flex sensors information. We have adapted it for our current architecture with servos, stepper and encoder. We are working on making the PWM information dynamic. 
### Clubbed Code
Coordinates between all motors using helper functions. 
Parses the CSV file for input date
   Input (csv file) for actuator movement: 
   Note duration, Stepper Motor: hand (left or right), position of hand, Note and Finger, Sharp (true or false)

### Microcontroller
   We are using the ESP32 microcontroller. We have two pins assigned for the direction and the position with 6 servo motors (the thumb gets two) and 6 additional smaller servo motors to be mounted on top of the fingers. 
