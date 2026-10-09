"""Compose PEN News' own music: a loopable news bed and an 8-second intro sting.

Everything is synthesised from scratch with numpy (additive pads, sine bass, plucked arpeggio,
noise ticks), so the channel owns the audio outright. Output: bucket/media/music/bed.m4a and sting.m4a.
"""
import subprocess
import wave

import numpy as np

from .config import FFMPEG, MUSIC_DIR

SR = 44100
BPM = 96
BEAT = 60 / BPM
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def tone(freq, dur, harmonics=8, tilt=1.6, detune=.003):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for d in (-detune, 0, detune):
        for n in range(1, harmonics + 1):
            out += np.sin(2 * np.pi * freq * (1 + d) * n * t + rng.uniform(0, 6.28)) / n ** tilt
    return out / 3


def env(n, a, r, sustain=1.0):
    e = np.full(n, sustain)
    ai, ri = int(a * SR), int(r * SR)
    e[:ai] = np.linspace(0, sustain, ai) if ai else e[:ai]
    if ri:
        e[-ri:] *= np.linspace(1, 0, ri)
    return e


def pluck(freq, dur):
    t = np.arange(int(dur * SR)) / SR
    x = (2 * np.abs(2 * ((freq * t) % 1) - 1) - 1) * .6 + .4 * np.sin(2 * np.pi * freq * 2 * t)
    return x * np.exp(-t * 9)


def tick(dur=.05):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    x = np.diff(x, prepend=0)          # crude high-pass: keeps the bright "tick"
    return x * np.exp(-np.arange(n) / SR * 90) * .25


def place(buf, clip, at):
    i = int(at * SR)
    j = min(len(buf), i + len(clip))
    if i < len(buf):
        buf[i:j] += clip[: j - i]


# D minor: Dm  Bb  F  C  (two bars each)
CHORDS = [[50, 57, 62, 65, 69], [46, 53, 58, 62, 65], [41, 53, 57, 60, 65], [48, 55, 60, 64, 67]]
ROOTS = [38, 34, 41, 36]


def bed(loops=4):
    bar = 4 * BEAT
    total = loops * len(CHORDS) * 2 * bar
    out = np.zeros(int(total * SR) + SR * 4)
    t = 0.0
    for _ in range(loops):
        for ci, chord in enumerate(CHORDS):
            span = 2 * bar
            pad = sum(tone(hz(m), span + 1.5, tilt=1.9) for m in chord)
            place(out, pad * env(len(pad), .8, 1.5) * .05, t)
            for k in range(16):                       # bass on eighth notes
                b = tone(hz(ROOTS[ci]), BEAT / 2, harmonics=3, tilt=2.5)
                place(out, b * env(len(b), .005, .12) * (.22 if k % 2 == 0 else .14), t + k * BEAT / 2)
            arp = [chord[1], chord[2], chord[3], chord[4], chord[3], chord[2]]
            for k in range(32):                       # sixteenth-note arpeggio, an octave up
                p = pluck(hz(arp[k % len(arp)] + 12), .35)
                place(out, p * .05, t + k * BEAT / 4)
            for k in range(8):                        # offbeat ticks like a newsroom clock
                place(out, tick(), t + k * BEAT + BEAT / 2)
            t += span
    # wrap the release tail onto the start so the loop is seamless
    n = int(total * SR)
    tail = out[n:]
    out = out[:n]
    out[: len(tail)] += tail
    return out


def sting():
    dur = 8.0
    out = np.zeros(int(dur * SR))
    tt = np.arange(len(out)) / SR
    # rising noise swell into the hit at 2.0 s
    riser = rng.standard_normal(int(2.0 * SR)) * np.linspace(0, 1, int(2.0 * SR)) ** 3 * .12
    riser = np.convolve(riser, np.ones(30) / 30, mode="same")
    place(out, riser, 0)
    # impact: falling sub thump plus a bright chord
    n = int(2.5 * SR); t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (90 * np.exp(-t * 3) + 38) * t) * np.exp(-t * 2.2) * .7
    place(out, thump, 2.0)
    chord = sum(tone(hz(m), 6.0, tilt=1.7) for m in [50, 57, 62, 64, 69, 74])
    place(out, chord * env(len(chord), .02, 3.5) * np.exp(-np.arange(len(chord)) / SR * .35) * .08, 2.0)
    for k in range(10):                               # light arpeggio sparkle after the hit
        p = pluck(hz([74, 77, 81, 86][k % 4]), .5)
        place(out, p * .06 * (1 - k / 12), 2.2 + k * BEAT / 4)
    # soft closing pulse
    end = tone(hz(38), 1.6, harmonics=3, tilt=2.4)
    place(out, end * env(len(end), .01, 1.2) * .25, 6.2)
    out *= np.minimum(1, (dur - tt) / .6)            # fade the last 0.6 s
    return out


def write(x, name):
    x = x / (np.max(np.abs(x)) + 1e-9) * .89
    stereo = np.stack([x, np.roll(x, 37)], axis=1)     # tiny delay for width
    pcm = (stereo * 32767).astype("<i2")
    wav = MUSIC_DIR / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    m4a = MUSIC_DIR / f"{name}.m4a"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "192k", str(m4a)], check=True)
    wav.unlink()
    return m4a


if __name__ == "__main__":
    print(write(bed(), "bed"))
    print(write(sting(), "sting"))
