#!/usr/bin/env python3
"""Jalankan dengan python case_a.py --help."""

import argparse
from datetime import datetime
import ipaddress
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import numpy as np

from analisis import SKENARIO, analyze
from csi import FS, SUBCARRIERS, save_csv, scan_cs8, selftest


def write_json(path, values):
    path.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def checked_tool(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f"{name} tidak ditemukan. Pasang HackRF Tools sesuai README.")
    return path


def record(args):
    if not (2400 <= args.freq_mhz <= 2500 or 5000 <= args.freq_mhz <= 5900):
        raise ValueError("Masukkan frekuensi tengah primary channel Wi-Fi dalam MHz.")
    if not (0 <= args.lna <= 40 and args.lna % 8 == 0 and 0 <= args.vga <= 62 and args.vga % 2 == 0):
        raise ValueError("LNA harus kelipatan 8 dalam 0–40; VGA kelipatan 2 dalam 0–62.")
    if not (0 < args.durasi <= 120):
        raise ValueError("Gunakan durasi di atas 0 sampai 120 detik.")
    for field in (args.sesi, args.subjek):
        if not field or not all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in field):
            raise ValueError("ID sesi dan subjek memakai huruf, angka, atau tanda hubung.")
    tool = checked_tool("hackrf_transfer")
    path = args.raw / f"A_{args.sesi}_{args.subjek}_{args.skenario}.cs8"
    path.parent.mkdir(parents=True, exist_ok=True)
    log = path.with_suffix(".json")
    incomplete = path.with_suffix(".cs8.part")
    if any(p.exists() for p in (path, log, incomplete)):
        raise ValueError(f"Nama rekaman sudah terpakai: {path}. Pilih ID lain atau folder baru.")
    samples = round(FS * args.durasi)
    if shutil.disk_usage(path.parent).free < samples * 2 + 50_000_000:
        raise ValueError(f"Ruang disk kurang. Rekaman perlu {samples * 2 / 1e9:.2f} GB.")
    command = [tool, "-r", str(incomplete), "-f", str(round(args.freq_mhz * 1e6)),
               "-s", str(FS), "-b", str(FS), "-l", str(args.lna), "-g", str(args.vga),
               "-a", "0", "-n", str(samples)]
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"Rekam {args.skenario} selama {args.durasi:g} s mulai {started}. Ukuran ~{samples*2/1e9:.2f} GB.",
          flush=True)
    try:
        subprocess.run(command, check=True)
        # HackRF dapat menghasilkan padding satu blok. Gunakan jumlah sampel yang diminta.
        if incomplete.stat().st_size < samples * 2:
            raise ValueError("Rekaman terpotong. Periksa USB dan kecepatan penyimpanan.")
        with incomplete.open("r+b") as handle:
            handle.truncate(samples * 2)
        incomplete.rename(path)
    except (OSError, ValueError, subprocess.CalledProcessError, KeyboardInterrupt):
        if incomplete.exists():
            print(f"Rekaman belum selesai tersimpan sebagai {incomplete}.", file=sys.stderr)
        raise
    write_json(log, {
        "asal": "hackrf", "rekaman": path.name, "sesi": args.sesi, "subjek": args.subjek,
        "skenario": args.skenario, "mulai": started, "durasi_s": samples / FS,
        "freq_mhz": args.freq_mhz, "lna": args.lna, "vga": args.vga, "amp": False,
        "lokasi": args.lokasi, "sumber": args.sumber, "catatan": args.catatan,
    })
    print(f"Tersimpan {path} dan {log}")


def extract(args):
    if not (0.6 <= args.rho < 1 and 0 < args.min_burst_us <= 1000 and 0 < args.ambang_db <= 60
            and args.cfo_tol_hz > 0):
        raise ValueError("Cek nilai rho, ambang daya, durasi burst, dan toleransi CFO.")
    files = sorted(args.input.glob("*.cs8")) if args.input.is_dir() else [args.input]
    if not files:
        raise ValueError(f"Tidak ada file CS8 di {args.input}.")
    args.csi.mkdir(parents=True, exist_ok=True)
    for path in files:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        print(f"Mengekstrak {path.name} ...", flush=True)
        frames, quality = scan_cs8(path, args.ambang_db, args.min_burst_us, args.rho)
        duration = quality["durasi_s"]
        cfo = np.array([row[2] for row in frames])
        if len(cfo):
            frequencies, counts = np.unique(np.rint(cfo / 1000).astype(int), return_counts=True)
            peaks = sorted(zip(counts, frequencies), reverse=True)[:8]
            print("Kelompok CFO (kHz: paket): " + ", ".join(f"{f:+d}: {n}" for n, f in peaks))
        rows = frames
        if args.cfo_hz is not None:
            rows = [r for r in frames if abs(r[2] - args.cfo_hz) <= args.cfo_tol_hz]
        gap = max(np.diff([0, *(row[0] for row in rows), duration]))
        print(f"CSI terpilih: {len(rows)}/{len(frames)} L-LTF valid, {len(rows)/duration:.2f} paket/s, "
              f"celah maksimum {gap:.3f} s, clipping {quality['clipping_pct']:.3f}%.")
        if not rows:
            raise ValueError(f"{path.name}: tidak ada paket terpilih. Periksa kanal, OFDM, gain, dan CFO.")
        dest = args.csi / f"{path.stem}.csv"
        save_csv(dest, rows, meta["skenario"])
        write_json(dest.with_suffix(".json"), {
            **meta, **quality, "ltf_valid": len(frames), "rho_min": args.rho,
            "ambang_db": args.ambang_db, "min_burst_us": args.min_burst_us,
            "cfo_hz": args.cfo_hz, "cfo_tol_hz": args.cfo_tol_hz,
        })
        print(f"Tersimpan {dest}")


def demo(args):
    with tempfile.TemporaryDirectory(prefix="case-a-") as folder:
        frames = selftest(Path(folder) / "sintetis.cs8")
    print(f"Selftest CS8: {len(frames)} preamble lolos, CFO dan amplitudo CSI sesuai.")
    if args.selftest:
        return
    rng = np.random.default_rng(51)
    csi_dir = args.out / "csi"
    k = SUBCARRIERS
    for session in range(1, 4):
        for scenario in SKENARIO:
            t = (np.arange(900) + rng.uniform(0.05, 0.95, 900)) / 30
            static = (0.86 + 0.21 * np.cos(k / 9) +
                      0.10 * (scenario == "diam") * np.sin(k / 6) +
                      rng.normal(0, 0.01, len(k)))
            movement = {"kosong": 0, "diam": 0.01, "jalan_los": 0.22, "jalan_dinding": 0.13}[scenario]
            amp = (static + movement * np.sin(2 * np.pi * t[:, None] * 2.4 + k / 7) +
                   rng.normal(0, 0.018, (len(t), len(k))))
            rssi = -35 + rng.normal(0, 0.25, len(t)) + 0.09 * np.sin(2 * np.pi * t * 2.4)
            path = csi_dir / f"A_s{session}_sim_{scenario}.csv"
            save_csv(path, zip(t, rssi, np.full(len(t), -8100), np.full(len(t), 0.95), amp), scenario)
            write_json(path.with_suffix(".json"), {
                "asal": "simulasi", "sesi": f"s{session}", "subjek": "sim", "skenario": scenario,
                "durasi_s": 30,
            })
    analyze(csi_dir, args.out / "hasil", exploration=True)


def traffic(args):
    ip = ipaddress.IPv4Address(args.ip)
    if ip.is_unspecified or ip.is_multicast or ip.is_link_local or not (ip.is_private or ip.is_loopback):
        raise ValueError("Pakai IPv4 lokal perangkat kelompok.")
    if not (1024 <= args.port <= 65535 and 0 < args.durasi <= 600 and 1 <= args.pps <= 100):
        raise ValueError("Port 1024–65535, durasi maksimal 600 detik, dan laju 1–100 paket/s.")
    deadline = time.monotonic() + args.durasi
    count = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        if args.mode == "terima":
            sock.bind((str(ip), args.port))
            sock.settimeout(0.5)
            print(f"Mendengarkan UDP di {ip}:{args.port}", flush=True)
            while time.monotonic() < deadline:
                try:
                    sock.recvfrom(1500)
                    count += 1
                except socket.timeout:
                    pass
        else:
            print(f"Mengirim UDP uji ke {ip}:{args.port} pada {args.pps} paket/s.", flush=True)
            payload = b"CSILAB" * 200
            while time.monotonic() < deadline:
                sock.sendto(payload, (str(ip), args.port))
                count += 1
                time.sleep(1 / args.pps)
    print(f"Datagram {args.mode}: {count}")


def main():
    cli = argparse.ArgumentParser(description="Praktikum Wi-Fi CSI Case A dengan HackRF One.")
    commands = cli.add_subparsers(required=True)
    doctor = commands.add_parser("doctor", help="cek apakah HackRF terbaca")
    doctor.set_defaults(run=lambda _: subprocess.run([checked_tool("hackrf_info")], check=True))
    capture = commands.add_parser("rekam", help="rekam satu skenario sebagai CS8 dan JSON")
    capture.add_argument("--sesi", required=True)
    capture.add_argument("--subjek", required=True)
    capture.add_argument("--skenario", choices=SKENARIO, required=True)
    capture.add_argument("--freq-mhz", type=float, required=True)
    capture.add_argument("--lokasi", required=True)
    capture.add_argument("--sumber", required=True)
    capture.add_argument("--catatan", default="")
    capture.add_argument("--durasi", type=float, default=30)
    capture.add_argument("--lna", type=int, default=32)
    capture.add_argument("--vga", type=int, default=26)
    capture.add_argument("--raw", type=Path, default=Path("data/raw"))
    capture.set_defaults(run=record)
    extractor = commands.add_parser("ekstrak", help="ubah satu CS8 atau satu folder CS8 menjadi CSV CSI")
    extractor.add_argument("input", type=Path)
    extractor.add_argument("--csi", type=Path, default=Path("data/csi"))
    extractor.add_argument("--ambang-db", type=float, default=10)
    extractor.add_argument("--min-burst-us", type=float, default=40)
    extractor.add_argument("--rho", type=float, default=0.6)
    extractor.add_argument("--cfo-hz", type=float)
    extractor.add_argument("--cfo-tol-hz", type=float, default=4000)
    extractor.set_defaults(run=extract)
    report = commands.add_parser("analisis", help="buat grafik dan evaluasi pada sesi terpisah")
    report.add_argument("--csi", type=Path, default=Path("data/csi"))
    report.add_argument("--out", type=Path, default=Path("hasil"))
    report.add_argument("--eksplorasi", action="store_true")
    report.set_defaults(run=lambda a: analyze(a.csi, a.out, a.eksplorasi))
    sample = commands.add_parser("demo", help="jalankan selftest dan analisis data simulasi")
    sample.add_argument("--out", type=Path, default=Path("demo"))
    sample.add_argument("--selftest", action="store_true", help="uji decoder CS8 saja")
    sample.set_defaults(run=demo)
    flow = commands.add_parser("trafik", help="buat trafik UDP di jaringan Wi-Fi kelompok")
    flow.add_argument("mode", choices=("kirim", "terima"))
    flow.add_argument("--ip", required=True)
    flow.add_argument("--durasi", type=float, default=120)
    flow.add_argument("--pps", type=int, default=35)
    flow.add_argument("--port", type=int, default=5005)
    flow.set_defaults(run=traffic)
    args = cli.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        cli.exit(1, f"Gagal: {exc}\n")
    except KeyboardInterrupt:
        cli.exit(130, "\nProses dihentikan.\n")


if __name__ == "__main__":
    main()
