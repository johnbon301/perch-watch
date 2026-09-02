# perch-watch

A species-aware bird deterrent system for a Raspberry Pi. A static webcam feeds two YOLO models into a pan/tilt turret with a water sprayer. Protected species (bald eagle, red-tailed hawk) are automatically excluded from firing, and sightings of any of the trained species are logged with a photo for later review.

## How it works

1. The camera (fixed in place, not mounted on the turret) captures a frame.
2. `birdOnlyModel` detects birds in the frame and the largest bounding box is treated as the target for that frame.
3. That region is cropped out and ran through `speciesOnlyModel`, which tries to match it against the 11 trained species.
4. If a species is positively identified, it's logged and has a cooldown so one lingering bird doesn't flood the log.
5. The target's pixel position is converted into a pan/tilt angle using the camera's measured field of view, and is smoothed to cut down on servo jitter.
6. Unless the identified species is protected, the water pump fires, which also has a cooldown.
7. All of the above is skipped outside a configurable active-hours window (default 5am-10pm), but the loop still reads camera frames overnight, just doesn't run detection. Again has a 20 minute cooldown when the camera is reading frames

## Hardware

Full parts list and wiring diagram plus a photo of the parts in place: [`hardware/parts-list.md`](hardware/parts-list.md), [`hardware/wiring.md`](hardware/wiring.md), [`hardware/Parts.jpeg`](hardware/Parts.jpeg).

- **Compute**: Raspberry Pi 5 (4GB) with active cooler, 64GB microSD, USB webcam (1080p) — statically mounted near the turret, not attached to it (see the field-of-view calibration note below for why that matters)
- **Aiming**: 2x MG996R servos (pan/tilt) via a PCA9685 driver through Adafruit `ServoKit` (pan range 0-180°, tilt range 80-180°)
- **Water system**: 12V diaphragm pump (1.2 GPM), adjustable nozzle, silicone tubing, a DIY vented reservoir
- **Power/switching**: three separate power rails (Pi, servo, pump) tied to one common ground — pump is fused and switched through a MOSFET trigger module on GPIO 17, servo rail steps 12V down to 6V through a buck converter before reaching the PCA9685

## Software setup

```bash
python3 -m venv turret-env
source turret-env/bin/activate
pip install -r requirements.txt
```
(Assumes standard Raspberry Pi OS, which ships with [piwheels.org](https://www.piwheels.org) configured as an extra pip index by default — that's what resolves the ARM CPU builds of `torch`/`torchvision` in this file. On a non-Pi-OS system you'd need to point pip at it yourself, or drop those two pins and let pip resolve its own build.)

### Models

Model weights aren't tracked in git. Training is done via [`training/model_training.ipynb`](training/model_training.ipynb), so retrain and export to NCNN format, then place the resulting folders at:

- `models/birdOnly/bird_detection(best_weight)v2_ncnn_model/` — general bird detector
- `models/speciesOnly/birdDetectionUmatilla_ncnn_model/` — 11-species classifier (red-winged blackbird, greater white-fronted goose, snow goose, canada goose, cackling goose, bufflehead, red-tailed hawk, bald eagle, dark-eyed junco, black-crowned night heron, american robin)

`yolo11n_ncnn_model/` (stock YOLO11n, used for generic detection/testing) can be regenerated any time with:
```bash
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt').export(format='ncnn')"
```

## Calibrating the camera's field of view

`movement.py`'s pan/tilt math depends on the camera's actual horizontal/vertical field of view (`HFOV`/`VFOV`) at whatever capture resolution you're using. So this has to be measured per camera, it can't be assumed from a spec sheet (cheap webcam listings are frequently inaccurate about this). See the comment and formula at `movement.py:94-95` for how it's calculated.

This only needs to be redone if the camera, lens, or capture resolution changes.

## Configuration

All of these live as constants near the top of `main()` in `movement.py`:

| Constant | Meaning |
|---|---|
| `HFOV` / `VFOV` | Camera's measured field of view, in degrees (see calibration above) |
| `SMOOTHING_FACTOR` | 0-1, how much each new pan/tilt target blends with the previous one. Closer to 1 = more responsive but jitterier; closer to 0 = smoother but laggier |
| `DEADBAND_DEGREES` | Ignore corrections smaller than this, to stop the servo from chasing detection noise |
| `ACTIVE_START_HOUR` / `ACTIVE_END_HOUR` | Hours during which detection runs at all |
| `SHOOT_COOLDOWN` | Minimum seconds between pump activations |
| `LOG_COOLDOWN` | Minimum seconds between sighting log entries, so one lingering bird doesn't spam the CSV |
| `PROTECTED_SPECIES` | Set of species names that are logged but never fired on |

## Running it

Manual (interactive):
```bash
python movement.py
```

As a persistent, unattended service. Auto-restarts on crash, auto-starts on boot:
```bash
sudo systemctl enable --now perch-watch   # start it now + on every future boot
sudo systemctl status perch-watch          # check it's running
journalctl -u perch-watch -f               # follow live logs
sudo systemctl disable --now perch-watch   # stop it, and stop auto-starting
```
The unit file lives at `/etc/systemd/system/perch-watch.service`.

## Species logging

Every positively-identified sighting (throttled by `LOG_COOLDOWN`) gets recorded to:
- `sightings/sightings.csv` — id, species, confidence, timestamp
- `sightings/images/{id}.png` — the cropped photo matching that row

Sighting IDs pick up where they left off across restarts (computed from existing CSV rows at startup), so old photos are never overwritten. Detections that don't match any of the trained species aren't logged since the trained species list is a small set, most everyday detections are expected to fall into this "unidentified" case, and that's by design, not a failure.

## Protected species

`PROTECTED_SPECIES` currently covers the bald eagle and red-tailed hawk, which both carry federal protections beyond the general Migratory Bird Treaty Act that covers nearly all native North American birds. Worth knowing that this only blocks firing when the species model successfully identifies one of these. An unidentified detection is treated as allowed to fire, matching this project's actual bird population (the trained species are rare here, so this is meant to be a safety net for a raresighting rather than the default outcome).

## Remote monitoring

The Pi is reachable over Tailscale and works whether checking in from inside or outside the home network, without exposing SSH to the public internet:
```bash
ssh USER_NAME@PI_NAME   # or the Tailscale IP directly if MagicDNS isn't set up
```

## Repo structure

- `movement.py` — main detection/tracking/logging loop
- `turretMovement.py` — `Turret` class wrapping the servos and water trigger
- `requirements.txt` — pinned Python dependencies for `pip install -r`
- `models/` — model weights (not tracked in git)
- `training/` — `model_training.ipynb`, used to train/retrain the bird and species models
- `hardware/` — parts list and wiring diagram for the physical build
- `sightings/` — generated at runtime: sighting log + photos
