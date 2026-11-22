"""Ekstraksi CSI legacy Wi-Fi 20 MHz dari sampel HackRF CS8."""

import csv
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing


FS = 20_000_000
SUBCARRIERS = np.r_[np.arange(-26, 0), np.arange(1, 27)]
LTF_SIGNS = np.array([
    1, 1, -1, -1, 1, 1, -1, 1, -1, 1, 1, 1, 1, 1, -1, -1,
    1, 1, -1, 1, -1, 1, 1, 1, 1, 1,
    1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, -1, -1,
    1, 1, -1, -1, 1, -1, 1, -1, 1, 1, 1, 1,
])
LTF_FREQ = np.zeros(64, complex)
LTF_FREQ[SUBCARRIERS % 64] = LTF_SIGNS
LTF = np.fft.ifft(LTF_FREQ)
AMP = [f"amp_k{k}" for k in SUBCARRIERS]
PHASE = [f"fasa_k{k}" for k in SUBCARRIERS]
HEADER = ["t_s", "rssi_dbfs", "cfo_hz", "rho", *AMP, *PHASE, "label"]


def decode_preamble(segment, onset):
    """Pakai pengulangan 16 sampel untuk CFO kasar dan dua LTF untuk CFO sisa."""
    stf = segment[onset + 20:onset + 140]
    if len(stf) != 120:
        return None
    left, right = stf[:-16], stf[16:]
    repeat = np.vdot(left, right)
    if abs(repeat) < 0.40 * np.linalg.norm(left) * np.linalg.norm(right):
        return None
    coarse = np.angle(repeat) / 16
    corrected = segment * np.exp(-1j * coarse * np.arange(len(segment)))
    # L-STF 160 sampel + guard L-LTF 32 sampel. Beri ruang untuk
    # kesalahan estimasi awal burst dari jendela daya 1 mikrodetik.
    lo = max(0, onset + 192 - 48)
    hi = min(len(segment) - 128, onset + 192 + 48)
    if hi < lo:
        return None
    search = corrected[lo:hi + 128]
    energy = np.sqrt(np.convolve(np.abs(search) ** 2, np.ones(64), "valid"))
    correlation = np.abs(np.correlate(search, LTF, "valid"))
    correlation /= np.linalg.norm(LTF) * energy + 1e-12
    pairs = np.minimum(correlation[:-64], correlation[64:])
    peak = int(np.argmax(pairs))
    rho = float(pairs[peak])
    ltf = corrected[lo + peak:lo + peak + 128]
    fine = np.angle(np.vdot(ltf[:64], ltf[64:])) / 64
    ltf *= np.exp(-1j * fine * np.arange(128))
    observed = np.fft.fft(ltf.reshape(2, 64), axis=1).mean(axis=0)
    channel = observed[SUBCARRIERS % 64] / LTF_SIGNS
    rssi = 10 * np.log10(np.mean(np.abs(ltf) ** 2) + 1e-12)
    return float(rssi), float((coarse + fine) * FS / (2 * np.pi)), rho, channel


def scan_cs8(path, threshold_db, min_burst_us, min_rho, block=1_000_000):
    """Baca blok kecil dengan overlap supaya preamble di batas blok tetap utuh."""
    size = path.stat().st_size
    if size < 2 or size % 2:
        raise ValueError(f"{path}: CS8 harus berisi pasangan I/Q int8.")
    raw = np.memmap(path, dtype=np.int8, mode="r").reshape(-1, 2)
    span = len(raw)
    margin, bin_size = 4096, 20
    frames = []
    clips = 0
    bursts = 0
    minimum_bins = int(np.ceil(min_burst_us))
    for start in range(0, span, block):
        end = min(start + block, span)
        base = max(0, start - margin)
        samples = raw[base:min(end + margin, span)]
        center = raw[start:end]
        clips += np.count_nonzero((center == -128) | (center == 127))
        iq = samples[:, 0].astype(np.complex64)
        iq.imag = samples[:, 1]
        iq /= 128
        iq -= iq.mean()
        samples_for_power = iq[:len(iq) // bin_size * bin_size]
        power = (np.abs(samples_for_power.reshape(-1, bin_size)) ** 2).mean(axis=1)
        if not len(power):
            continue
        floor = max(float(np.quantile(power, 0.25)), 1 / 128**2)
        active = binary_closing(power > floor * 10**(threshold_db / 10), structure=np.ones(3))
        edges = np.flatnonzero(np.diff(np.r_[False, active, False]))
        for first, stop in zip(edges[::2], edges[1::2]):
            absolute = base + first * bin_size
            if not start <= absolute < end or stop - first < minimum_bins:
                continue
            bursts += 1
            offset = first * bin_size
            begin = max(0, offset - 48)
            decoded = decode_preamble(iq[begin:offset + 400], offset - begin)
            if decoded is not None and decoded[2] > min_rho:
                rssi, cfo, rho, channel = decoded
                frames.append((absolute / FS, rssi, cfo, rho, channel))
    return frames, {"durasi_s": span / FS, "burst": bursts, "clipping_pct": 100 * clips / size}


def save_csv(path, rows, label):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            for t, power, cfo, rho, channel in rows:
                values = [t, power, cfo, rho, *np.abs(channel), *np.angle(channel)]
                writer.writerow([*(f"{v:.8g}" for v in values), label])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def selftest(path):
    rng = np.random.default_rng(4)
    short_bins = np.zeros(64, complex)
    short_bins[np.r_[np.arange(-24, 0, 4), np.arange(4, 25, 4)] % 64] = 1 + 1j
    short = np.tile(np.fft.ifft(short_bins)[:16], 10)
    cfo = 210_000  # Melebihi rentang fine CFO tanpa koreksi kasar.
    channel_ir = np.array([1, 0, 0, 0.18 + 0.09j])
    burst = np.convolve(np.r_[short, LTF[-32:], LTF, LTF, np.tile(LTF, 8)], channel_ir)
    burst *= 2 * np.exp(2j * np.pi * cfo * np.arange(len(burst)) / FS)
    iq = 0.002 * (rng.normal(size=800_000) + 1j * rng.normal(size=800_000))
    for start in (49_980, 120_004, 599_798):
        iq[start:start + len(burst)] += burst
    raw = np.rint(128 * np.column_stack((iq.real, iq.imag))).clip(-128, 127).astype(np.int8)
    raw.tofile(path)
    frames, stats = scan_cs8(path, 10, 40, 0.6, block=50_000)
    if len(frames) != 3 or max(abs(row[2] - cfo) for row in frames) > 1_500:
        raise ValueError(f"Selftest preamble gagal: {len(frames)} frame, statistik {stats}.")
    expected = 2 * np.abs(np.fft.fft(channel_ir, 64)[SUBCARRIERS % 64])
    if any(np.max(np.abs(np.abs(row[4]) - expected)) > 0.08 for row in frames):
        raise ValueError("Selftest amplitudo CSI gagal.")
    return frames
