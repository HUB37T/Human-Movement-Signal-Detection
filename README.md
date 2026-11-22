# Case A — Deteksi Kehadiran dan Gerakan dengan Wi-Fi CSI

HackRF One merekam sampel I/Q dari Wi-Fi kelompok. Skrip mencari preamble OFDM, mengoreksi CFO, dan menghitung CSI pada 52 subcarrier. Dari hasilnya, kalian membandingkan CSI dengan RSSI untuk mendeteksi gerakan dan melihat apakah orang yang duduk diam bisa dibedakan dari ruangan kosong.

## 1. Pasang alat dan jalankan demo

Butuh satu HackRF One dengan antena sesuai pita 2,4 atau 5 GHz, router kelompok, dan komputer dengan Python 3.10 atau lebih baru. Gunakan kabel USB data dan penyimpanan yang bisa menulis sekitar **40 MB/s**.

Di Ubuntu/Debian, jalankan:

```bash
sudo apt install hackrf python3-venv
cd wifi-csi-case-a
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python case_a.py demo
python case_a.py doctor
```

Di macOS, pasang HackRF Tools dengan `brew install hackrf`, lalu jalankan langkah mulai dari `cd`. Di Windows PowerShell, pakai:

```powershell
cd wifi-csi-case-a
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe case_a.py demo
```

Di langkah berikutnya, ganti `python` dengan `.\.venv\Scripts\python.exe` jika lingkungan virtual belum aktif. Untuk merekam di Windows, `hackrf_info` dan `hackrf_transfer` harus bisa dipanggil dari terminal. Demo cukup dengan Python.

Demo menguji ekstraksi dari CS8 sintetis dengan CFO yang diketahui, lalu membuat grafik dan evaluasi untuk 12 rekaman CSI simulasi. Hasilnya ada di `demo/hasil/`. Gunakan data pengukuran sendiri untuk laporan.

## 2. Siapkan ruangan dan sumber Wi-Fi

1. Tempatkan router dan HackRF sekitar **3–5 m** terpisah pada ketinggian sekitar **1 m**. Tandai posisinya. Garis antara kedua antena adalah jalur langsung (*line of sight* atau LOS).
2. Kunci Wi-Fi router di satu kanal berlebar **20 MHz**. Contoh di bawah memakai **kanal 36 (5180 MHz)**. Jika memakai 2,4 GHz, kanal 1, 6, dan 11 masing-masing berada di 2412, 2437, dan 2462 MHz. Pada 2,4 GHz, pastikan trafik menghasilkan frame OFDM dengan L-LTF yang valid. Beacon 802.11b tidak menyediakan L-LTF.
3. Gunakan router kelompok dan ruangan yang diizinkan dosen. HackRF bekerja dalam mode terima. Pertahankan kanal, gain, posisi perangkat, arah antena, dan sumber paket selama seluruh pengujian. Gunakan kode subjek seperti `P1` dengan persetujuan subjek sesuai modul. Saat merekam kondisi kosong, operasikan alat dari luar area pengujian.

### Bangkitkan trafik yang teratur

Cara yang paling mudah dipisahkan dari paket perangkat lain adalah membuat trafik **dari laptop berkabel Ethernet ke klien Wi-Fi** melalui router. Di sisi udara, router mengirim data dan klien mengirim balasan Wi-Fi pendek. Laptop perekam boleh sekaligus menjadi klien Wi-Fi. Tempatkan operator di luar area pengukuran.

Contoh alamat klien Wi-Fi adalah `192.168.1.24`. Ganti dengan IPv4 klien di jaringan kelompok. Buka satu terminal di klien dan satu di laptop sumber, jalankan dari folder ini di masing-masing perangkat:

```bash
# Klien Wi-Fi
python case_a.py trafik terima --ip 192.168.1.24 --durasi 300

# Sumber berkabel Ethernet ke router yang sama
python case_a.py trafik kirim --ip 192.168.1.24 --durasi 270 --pps 40
```

Mulai klien lebih dulu. Cek hitungan datagram ketika kedua perintah selesai. Jalankan ulang ketika trafik berhenti sebelum sesi berikutnya. Jika memakai hotspot HP tanpa Ethernet, pakai trafik terkendali antarperangkat kelompok yang tersambung ke hotspot dan pisahkan sumber Wi-Fi saat kalibrasi. **40 datagram/s adalah setelan pengirim. Target Case A adalah minimal 20 paket CSI terpilih/s yang benar-benar terbaca di HackRF.**

## 3. Kalibrasi dan uji satu rekaman pendek

Dengan trafik sedang berjalan, rekam lima detik pada lokasi dan gain yang akan dipakai:

```bash
python case_a.py rekam --raw data/pilot --sesi pilot --subjek none --skenario kosong --freq-mhz 5180 --durasi 5 --lokasi "Ruang kelas" --sumber router-kelompok --lna 32 --vga 26
python case_a.py ekstrak data/pilot --csi data/pilot-csi
```

Periksa tiga angka dari terminal:

| Hasil | Yang dicek |
|---|---|
| L-LTF valid | Korelasi L-LTF lebih dari 0,6. Untuk checkpoint minggu 1, modul meminta minimal 20 paket valid. |
| Paket per detik | Target akhir minimal 20 paket/s **setelah** memilih pemancar. |
| Clipping | Persentase sampel yang menyentuh batas ADC sebaiknya mendekati nol. Jika signifikan, turunkan gain dan ulangi pilot. |

Untuk mengenali pemancar target, bandingkan kelompok CFO yang muncul saat trafik berjalan dan saat trafik kelompok dihentikan. Untuk pilot tanpa trafik, rekam dengan `--sesi hening`, lalu ekstrak file `data/pilot/A_hening_none_kosong.cs8` dengan `--csi data/pilot-hening-csi`. Jika hasilnya nol paket valid, terminal tetap menampilkan ringkasan. Pilih kelompok CFO yang konsisten dan bertambah saat trafik dinyalakan. Durasi burst minimum 40 µs membantu membuang ACK pendek. Gunakan kanal yang sepi karena CFO dan durasi burst hanya petunjuk sumber. Jika dua sumber bertumpuk pada CFO yang sama, pindah ke kanal kelompok yang lebih bersih, lalu ulangi pilot.

Misalnya, jika pusat kelompok CFO adalah **−8 kHz**, uji filter berikut:

```bash
python case_a.py ekstrak data/pilot/A_pilot_none_kosong.cs8 --csi data/pilot-csi --cfo-hz -8000 --cfo-tol-hz 4000
```

Angka `-8000` hanya contoh. Ganti dengan hasil dari perangkat kalian. Jika laju paket kurang, periksa dulu pilihan sumber, kanal utama, dan kualitas L-LTF. Naikkan laju UDP secara bertahap bila jaringan masih longgar, lalu ukur lagi. Jika 2,4 GHz tidak menghasilkan L-LTF valid, uji ulang pada 5 GHz. Untuk sinyal lemah tanpa clipping, kalibrasikan gain atau coba `--ambang-db 8` dan tinjau apakah paket tambahan datang dari sumber yang benar. Catat parameter ekstraksi yang akhirnya dipakai.

## 4. Rekam semua skenario

Setiap ID sesi (`s1`, `s2`, dan `s3`) memuat empat rekaman berdurasi minimal 30 detik. Ambil tiap sesi sebagai pengulangan tersendiri.

| Label | Selama perekaman |
|---|---|
| `kosong` | Ruangan kosong selama 30 detik. |
| `diam` | Satu orang duduk diam di garis LOS. |
| `jalan_los` | Satu orang berjalan berulang melintasi LOS. |
| `jalan_dinding` | Satu orang berjalan berulang di dekat dinding tanpa melintasi LOS. |

Perulangan Bash berikut meminta konfirmasi sebelum tiap pengambilan dan langsung mengekstrak CSV setelah perekaman. Isi `freq`, `cfo`, dan gain sesuai pilot. Pastikan trafik tetap berjalan selama setiap pengambilan. Di PowerShell, jalankan kedua perintah di badan perulangan satu per satu dengan nilai sesi, subjek, dan skenario yang sama seperti tabel.

```bash
freq=5180
cfo=-8000
lna=32
vga=26
for sesi in s1 s2 s3; do
  for skenario in kosong diam jalan_los jalan_dinding; do
    subjek=P1
    if [ "$skenario" = kosong ]; then subjek=none; fi
    read -r -p "$sesi/$skenario siap dan trafik aktif? Tekan Enter: " _
    python case_a.py rekam --sesi "$sesi" --subjek "$subjek" --skenario "$skenario" --freq-mhz "$freq" --lokasi "Ruang kelas" --sumber router-kelompok --lna "$lna" --vga "$vga" || break 2
    python case_a.py ekstrak "data/raw/A_${sesi}_${subjek}_${skenario}.cs8" --cfo-hz "$cfo" || break 2
  done
done
```

Jika melanjutkan setelah kendala, jalankan perintah untuk rekaman yang masih kurang. Skrip menjaga agar rekaman dengan nama yang sama tidak tertimpa. Jika rekaman sudah ada dan ekstraksinya gagal, jalankan ulang `ekstrak` saja setelah memperbaiki parameternya. Parameter yang dipakai untuk membandingkan sesi harus konsisten. Tambahkan `--catatan "pintu tertutup, lintasan ditandai"` pada `rekam` jika ada kondisi yang perlu dicatat.

Satu rekaman 30 detik memerlukan sekitar **1,2 GB**, sehingga 12 rekaman memerlukan **14,4 GB**. Pindahkan CS8 dan JSON pasangannya ke penyimpanan yang disetujui setelah CSV diperiksa. Simpan minimal satu contoh CS8 per skenario untuk luaran. Analisis berikut membaca CSV dan JSON di `data/csi/`.

## 5. Buat grafik dan hitung hasil

```bash
python case_a.py analisis --eksplorasi
```

| Keluaran di `hasil/` | Isi |
|---|---|
| `heatmap.png` | Amplitudo CSI terhadap waktu untuk keempat skenario, dengan skala warna bersama. |
| `fitur.png` | Perbandingan distribusi variansi CSI dan variansi daya terima berbasis L-LTF (RSSI dalam dBFS). |
| `fitur.csv` | Fitur per jendela 1 detik, setelah interpolasi ke 20 Hz, median filter, dan low-pass. |
| `metrik.json` | Akurasi, FPR, FNR dan hitungan TP/TN/FP/FN untuk CSI dan RSSI. Ada hasil gabungan dan per sesi uji. |
| `log_sesi.csv` | Waktu, konfigurasi, jumlah paket valid, laju paket, celah terpanjang, dan jumlah jendela yang bisa dinilai. |

Pada deteksi gerak, kelas positif menggabungkan dua skenario berjalan dan kelas negatif adalah ruangan kosong. Pada uji kehadiran diam, skor dihitung dari jarak profil amplitudo atau daya rata-rata terhadap baseline kosong. Ambang dan baseline tiap putaran dihitung dari sesi latih. Satu sesi penuh ditahan untuk uji, lalu digilir. Jendela dengan paket terlalu sedikit atau celah panjang dilewati dan jumlahnya dicatat.

Opsi `--eksplorasi` mengurangi data aktual ke paling banyak 20, 10, dan 5 paket/s. Bandingkan akurasi, FPR, FNR, laju paket yang tercapai, dan jumlah jendela valid di `metrik.json`. Laju rendah bisa membuat sebagian jendela tidak dapat dinilai, sehingga laporkan jumlah jendelanya bersama metrik.

Untuk proposal, cantumkan denah, hipotesis yang bisa diuji, skenario, pengulangan, setelan radio, target laju paket, dan pembagian sesi latih/uji. Untuk laporan, gunakan grafik dan angka dari pengukuran sendiri dan jelaskan apakah CSI lebih baik dari RSSI pada kondisi gerak serta duduk diam. Saat demo kelas, tunjukkan perekaman singkat, ekstraksi CSI, lalu grafik dan metrik dari sesi yang sudah lengkap.

## Referensi

- Modul *Case Base: Pemanfaatan SDR untuk Wi-Fi Sensing Berbasis Channel State Information (CSI)*, bagian 3 dan Case A.
- [IEEE 802.11-2012, §18.3.3, legacy OFDM training sequence](https://ptacts.uspto.gov/ptacts/public-informations/petitions/1462020/download-documents?artifactId=Vap3VA26cwdGsHDSxZ0RlL8iIl-Elq7oKPmCjgkdj19_KzDlzJfuRT4). Skrip memakai urutan standar dengan tepat 52 subcarrier aktif dan DC nol.
- [Dokumentasi HackRF One](https://hackrf.readthedocs.io/en/stable/hackrf_one.html).
