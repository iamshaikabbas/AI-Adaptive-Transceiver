"""
record_audio.py
================
Records a short clip from the default microphone and saves it to the fixed
path config.AUDIO_FILE, which environment_classifier.py reads next.

Called by the MATLAB script as:  python record_audio.py
(no arguments -- MATLAB's Module 1 invokes it bare), but you can also run it
manually with --duration / --output for testing.

Requires: sounddevice, soundfile  (pip install sounddevice soundfile)
These need a working PortAudio install on the machine actually recording --
they are NOT needed just to run the rest of the pipeline (training,
prediction, dashboard) offline.
"""

import argparse
import sys

from config import AUDIO_FILE


def record(duration_sec: float, samplerate: int, out_path: str) -> None:
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError:
        print("ERROR: sounddevice/soundfile not installed. Run:\n"
              "  pip install sounddevice soundfile", file=sys.stderr)
        sys.exit(1)

    print(f"Recording {duration_sec:.1f}s of audio at {samplerate} Hz ...")
    audio = sd.rec(int(duration_sec * samplerate), samplerate=samplerate,
                    channels=1, dtype='float32')
    sd.wait()
    sf.write(out_path, audio, samplerate)
    print(f"Saved recording -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Record mic audio for environment detection.")
    ap.add_argument("--duration", type=float, default=4.0, help="Seconds to record")
    ap.add_argument("--samplerate", type=int, default=16000, help="Sample rate (Hz)")
    ap.add_argument("--output", type=str, default=AUDIO_FILE, help="Output WAV path")
    args = ap.parse_args()
    record(args.duration, args.samplerate, args.output)
