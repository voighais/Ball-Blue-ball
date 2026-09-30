Ball at Sea

A tiny arcade game where you steer a ball across the sea and dodge whatever falls from above. Built with Python + pywebview — the entire game runs in an HTML5 canvas inside a native window.

Gameplay

Move the mouse left and right to steer. Obstacles fall from the top of the screen — rocks, icebergs, logs, and drifting sea mines. Touch one and the run ends. Score grows with time, and so does the speed.

Features

Four obstacle types with different sizes, speeds, and hitboxes

Three difficulty levels: Easy, Normal, Hard

In-game shop: unlock a pirate hat, an ice trail, and a rainbow trail

Persistent progress — points, best score, run count, purchases, and equipped items are saved between sessions

Simple flat visuals, no glow or heavy effects

Requirements

Python 3.8+

pywebview

Installation

pip install pywebview


Run

python main.py


On Linux you may also need a webkit backend, for example:

sudo apt install python3-gi gir1.2-webkit2-4.1
