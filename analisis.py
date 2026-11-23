"""Fitur per detik, grafik, dan evaluasi antar sesi untuk Case A."""

import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import butter, sosfiltfilt

from csi import AMP, SUBCARRIERS


SKENARIO = ("kosong", "diam", "jalan_los", "jalan_dinding")
GRID_HZ = 20
LOW_PASS = butter(2, 8, fs=GRID_HZ, output="sos")


def read_data(path):
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    values = np.array([
        [float(row[k]) for k in ("t_s", "rssi_dbfs", *AMP)] for row in rows
    ])
    if len(values) < 2 or not np.isfinite(values).all() or np.any(np.diff(values[:, 0]) <= 0):
        raise ValueError(f"{path}: CSI kurang dari dua paket, tidak valid, atau waktunya tidak urut.")
    if any(row["label"] != metadata["skenario"] for row in rows):
        raise ValueError(f"{path}: label CSV berbeda dengan log sesi.")
    return metadata, values


def thin(values, rate):
    """Ambil paling banyak satu paket aktual per slot, tanpa membuat paket baru."""
    if rate is None:
        return values
    _, indices = np.unique(np.floor(values[:, 0] * rate), return_index=True)
    return values[indices]


def windows(meta, values, rate):
    values = thin(values, rate)
    t = values[:, 0]
    features = []
    if not len(t):
        return features
    for start in range(int(meta["durasi_s"])):
        grid = start + (np.arange(GRID_HZ) + 0.5) / GRID_HZ
        first, last = np.searchsorted(t, (grid[0], grid[-1]), side="left")
        lo, hi = max(0, first - 1), min(len(t), last + 1)
        # Jangan isi lubang panjang atau memperpanjang sinyal di luar data.
        frames = (t >= start) & (t < start + 1)
        max_gap = max(0.25, 1.5 / rate) if rate else 0.25
        if frames.sum() < 3 or t[lo] > grid[0] or t[hi - 1] < grid[-1]:
            continue
        if np.max(np.diff(t[lo:hi])) > max_gap:
            continue
        uniform = np.column_stack([
            np.interp(grid, t[lo:hi], col[lo:hi]) for col in values.T[1:]
        ])
        smooth = sosfiltfilt(LOW_PASS, median_filter(uniform, size=(3, 1)), axis=0)
        features.append({
            "sesi": meta["sesi"], "skenario": meta["skenario"], "t_s": start,
            "csi": float(np.var(smooth[:, 1:], axis=0).mean()),
            "rssi": float(np.var(smooth[:, 0])),
            "profil": np.mean(smooth[:, 1:], axis=0), "daya": float(np.mean(smooth[:, 0])),
        })
    return features


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, bool), np.asarray(predicted, bool)
    tp = int(np.sum(actual & predicted))
    tn = int(np.sum(~actual & ~predicted))
    fp = int(np.sum(~actual & predicted))
    fn = int(np.sum(actual & ~predicted))
    if not (tp + fn and tn + fp):
        raise ValueError("Kedua kelas harus punya jendela valid pada setiap sesi.")
    return {
        "akurasi": (tp + tn) / len(actual), "fpr": fp / (fp + tn), "fnr": fn / (fn + tp),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


def fit_threshold(score, label):
    scores = np.unique(score)
    candidates = np.r_[-np.inf, (scores[:-1] + scores[1:]) / 2, np.inf]
    # Sertakan prediksi semua negatif/positif dengan ambang yang tetap berhingga.
    candidates[0] = np.nextafter(scores[0], -np.inf)
    candidates[-1] = np.nextafter(scores[-1], np.inf)
    positives, negatives = np.sort(score[label]), np.sort(score[~label])
    fnr = np.searchsorted(positives, candidates, side="right") / len(positives)
    fpr = 1 - np.searchsorted(negatives, candidates, side="right") / len(negatives)
    return float(candidates[np.argmin(fnr + fpr)])


def evaluate(features, session_ids, task, feature):
    classes = (
        ("kosong", "jalan_los", "jalan_dinding") if task == "gerak" else ("kosong", "diam")
    )
    subset = [row for row in features if row["skenario"] in classes]
    actual, predicted, folds = [], [], []
    for session in session_ids:
        train = [row for row in subset if row["sesi"] != session]
        test = [row for row in subset if row["sesi"] == session]
        truth = lambda rows: np.array([row["skenario"] != "kosong" for row in rows], dtype=bool)
        train_labels, test_labels = truth(train), truth(test)
        if not (train_labels.any() and (~train_labels).any() and test_labels.any() and (~test_labels).any()):
            raise ValueError(f"Sesi {session}: jendela kosong atau {task} tidak cukup untuk evaluasi.")
        if task == "gerak":
            scores = lambda rows: np.array([row[feature] for row in rows])
        else:
            key = "profil" if feature == "csi" else "daya"
            baseline = np.mean([row[key] for row in train if row["skenario"] == "kosong"], axis=0)
            scores = lambda rows: np.array([np.mean(np.abs(row[key] - baseline)) for row in rows])
        cutoff = fit_threshold(scores(train), train_labels)
        guess = scores(test) > cutoff
        folds.append({"sesi_uji": session, "ambang": cutoff, **metrics(test_labels, guess)})
        actual.extend(test_labels)
        predicted.extend(guess)
    return {"gabungan": metrics(actual, predicted), "per_sesi": folds}


def export_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_heatmap(out, dataset):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    if dataset[0][0]["asal"] == "simulasi":
        fig.suptitle("Data simulasi")
    low, high = np.quantile(np.concatenate([values[:, 2:].ravel() for _, values in dataset]), [0.02, 0.98])
    for name, ax in zip(SKENARIO, axes.flat):
        meta, values = next(pair for pair in dataset if pair[0]["skenario"] == name)
        t = values[:, 0]
        limits = np.r_[t[0], (t[1:] + t[:-1]) / 2, t[-1]]
        amplitude = np.insert(values[:, 2:], 26, np.nan, axis=1)
        # Lubang panjang ditampilkan kosong agar tidak tampak seperti data kontinu.
        long_gap = np.flatnonzero(np.diff(t) > 0.25)
        for k in long_gap[::-1]:
            amplitude = np.insert(amplitude, k + 1, np.nan, axis=0)
            limits = np.r_[limits[:k + 1], t[k], t[k + 1], limits[k + 2:]]
        heat = ax.pcolormesh(limits, np.arange(-26.5, 27), amplitude.T,
                             shading="flat", vmin=low, vmax=high)
        ax.set(title=f"{name} · {meta['sesi']}", xlabel="Waktu (s)", ylabel="Subcarrier")
    fig.colorbar(heat, ax=axes, label="Amplitudo CSI |H[k]|")
    fig.savefig(out / "heatmap.png", dpi=160)
    plt.close(fig)


def plot_features(out, features, source):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    if source == "simulasi":
        fig.suptitle("Data simulasi")
    for ax, key, title in zip(axes, ("csi", "rssi"), ("Variansi CSI", "Variansi RSSI (dB²)")):
        groups = [[row[key] for row in features if row["skenario"] == name] for name in SKENARIO]
        ax.boxplot(groups, tick_labels=SKENARIO)
        ax.set_ylabel(title)
        ax.tick_params(axis="x", labelrotation=18)
    fig.savefig(out / "fitur.png", dpi=160)
    plt.close(fig)


def analyze(folder, out, exploration):
    dataset = [read_data(path) for path in sorted(folder.glob("*.csv"))]
    if not dataset:
        raise ValueError(f"Belum ada CSV CSI di {folder}. Jalankan ekstrak terlebih dahulu.")
    session_ids = sorted({meta["sesi"] for meta, _ in dataset})
    combinations = [(m["sesi"], m["skenario"]) for m, _ in dataset]
    expected = {(session, label) for session in session_ids for label in SKENARIO}
    if len(session_ids) < 3 or set(combinations) != expected or len(combinations) != len(expected):
        raise ValueError("Perlu minimal 3 sesi, masing-masing berisi tepat satu rekaman tiap skenario.")
    kinds = {meta["asal"] for meta, _ in dataset}
    mixed_synthetic = kinds == {"hackrf", "sintetis"}
    if (len(kinds) != 1 and not mixed_synthetic) or any(meta["durasi_s"] < 30 for meta, _ in dataset):
        raise ValueError("Gunakan satu jenis data dan durasi minimal 30 detik per skenario.")
    keys = ("freq_mhz", "lna", "vga", "amp", "sumber",
            "rho_min", "ambang_db", "min_burst_us", "cfo_hz", "cfo_tol_hz")
    settings = {tuple(meta.get(k) for k in keys) for meta, _ in dataset}
    if len(settings) > 1:
        raise ValueError("Gunakan setelan radio, sumber, dan filter ekstraksi yang sama untuk semua sesi.")
    features = []
    logs = []
    for meta, values in dataset:
        rows = windows(meta, values, None)
        if not rows:
            raise ValueError(f"{meta['sesi']}/{meta['skenario']}: tidak ada jendela CSI valid.")
        features.extend(rows)
        rate = len(values) / meta["durasi_s"]
        logs.append({
            **meta, "paket_valid": len(values), "paket_per_s": rate,
            "celah_maks_s": float(np.max(np.diff(np.r_[0, values[:, 0], meta["durasi_s"]]))),
            "jendela_valid": len(rows), "jendela_total": int(meta["durasi_s"]),
        })
    output = {
        "asal": "+".join(sorted(kinds)),
        "gerak": {key: evaluate(features, session_ids, "gerak", key) for key in ("csi", "rssi")},
        "hadir_diam": {key: evaluate(features, session_ids, "diam", key) for key in ("csi", "rssi")},
    }
    if mixed_synthetic:
        output["rekaman_sintetis"] = sorted(
            f"{meta['sesi']}/{meta['skenario']}" for meta, _ in dataset if meta["asal"] == "sintetis")
        print("Catatan: rekaman sintetis ikut dianalisis: " + ", ".join(output["rekaman_sintetis"]))
    if exploration:
        output["downsampling"] = []
        for rate in (20, 10, 5):
            thinned = [row for meta, values in dataset for row in windows(meta, values, rate)]
            fps = sum(len(thin(values, rate)) for _, values in dataset) / sum(m["durasi_s"] for m, _ in dataset)
            report = {"batas_paket_per_s": rate, "aktual_paket_per_s": fps, "jendela_valid": len(thinned)}
            try:
                report["gerak"] = {key: evaluate(thinned, session_ids, "gerak", key) for key in ("csi", "rssi")}
            except ValueError as exc:
                report["status"] = str(exc)
            output["downsampling"].append(report)
    out.mkdir(parents=True, exist_ok=True)
    export_csv(out / "log_sesi.csv", logs)
    export_csv(out / "fitur.csv", [{k: v for k, v in row.items() if k != "profil"} for row in features])
    (out / "metrik.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    plot_heatmap(out, dataset)
    plot_features(out, features, output["asal"])
    for task in ("gerak", "hadir_diam"):
        for method, results in output[task].items():
            stats = results["gabungan"]
            print(f"{task}/{method}: akurasi={stats['akurasi']:.1%}, FPR={stats['fpr']:.1%}, FNR={stats['fnr']:.1%}")
    for row in logs:
        if row["paket_per_s"] < 20:
            print(f"{row['sesi']}/{row['skenario']}: {row['paket_per_s']:.1f} paket/s, di bawah target 20.")
    print(f"Hasil disimpan di {out}")
