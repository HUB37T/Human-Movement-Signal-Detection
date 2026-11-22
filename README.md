# Case A — Deteksi Kehadiran dan Gerakan dengan Wi-Fi CSI

HackRF One merekam sampel I/Q dari Wi-Fi kelompok. Skrip mencari preamble OFDM, mengoreksi CFO, dan menghitung CSI pada 52 subcarrier. Dari hasilnya, kalian membandingkan CSI dengan RSSI untuk mendeteksi gerakan dan melihat apakah orang yang duduk diam bisa dibedakan dari ruangan kosong.

## 1. Pasang alat dan jalankan demo

Siapkan satu HackRF One dengan antena sesuai pita 2,4 atau 5 GHz, satu router kelompok, dan dua laptop dengan Python 3.10 atau lebih baru. Pada laptop yang merekam, gunakan kabel USB data dan penyimpanan yang bisa menulis sekitar **40 MB/s**.

Kalau belum punya proyek ini di laptop, ambil dari GitHub:

```bash
git clone https://github.com/HUB37T/Human-Movement-Signal-Detection.git
cd Human-Movement-Signal-Detection
```

Kalau foldernya sudah ada, langsung buka folder yang berisi `case_a.py`. Di Ubuntu/Debian, pasang `python3-venv` dengan `sudo apt install python3-venv` bila diperlukan. Siapkan Python di **kedua laptop**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Setiap kali membuka terminal baru, masuk ke folder proyek dan jalankan `source .venv/bin/activate` lagi.

Di **laptop yang terhubung ke HackRF**, pasang HackRF Tools dengan `sudo apt install hackrf` (Ubuntu/Debian) atau `brew install hackrf` (macOS). Sambungkan alat, lalu cek:

```bash
python case_a.py demo
python case_a.py doctor
```

Di Windows PowerShell, dari folder proyek pakai:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe case_a.py demo
```

Di langkah berikutnya, ganti `python` dengan `.\.venv\Scripts\python.exe` jika lingkungan virtual belum aktif. Untuk merekam di Windows, `hackrf_info` dan `hackrf_transfer` harus bisa dipanggil dari terminal. Demo cukup dengan Python.

Demo menguji ekstraksi dari CS8 sintetis dengan CFO yang diketahui, lalu membuat grafik dan evaluasi untuk 12 rekaman CSI simulasi. Hasilnya ada di `demo/hasil/`. Gunakan data pengukuran sendiri untuk laporan.

## 2. Siapkan ruangan dan sumber Wi-Fi

1. Tempatkan router dan HackRF sekitar **3–5 m** terpisah pada ketinggian sekitar **1 m**. Bayangkan garis lurus antara kedua antena. Itulah jalur langsung (*line of sight* atau LOS). Tempel selotip di lantai tepat di bawah garis itu agar posisi duduk dan lintasan jalan mudah diulang.
2. Kunci Wi-Fi router di satu kanal berlebar **20 MHz**. Contoh di bawah memakai **kanal 36 (5180 MHz)**. Jika memakai 2,4 GHz, kanal 1, 6, dan 11 masing-masing berada di 2412, 2437, dan 2462 MHz. Pada 2,4 GHz, pastikan trafik menghasilkan frame OFDM dengan L-LTF yang valid. Beacon 802.11b tidak menyediakan L-LTF.
3. Gunakan router kelompok dan ruangan yang diizinkan dosen. HackRF bekerja dalam mode terima. Pertahankan kanal, gain, posisi perangkat, arah antena, dan sumber paket selama seluruh pengujian. Gunakan kode subjek seperti `P1` dengan persetujuan subjek sesuai modul. Saat merekam kondisi kosong, operasikan alat dari luar area pengujian.

### Buka tiga terminal

Hubungkan laptop perekam ke **Wi-Fi router**, lalu hubungkan laptop pengirim ke **port LAN router lewat Ethernet**. Pasang HackRF lewat USB ke laptop perekam. Dengan susunan ini, router mengirim datagram lewat udara ke laptop perekam, dan HackRF merekam sinyal Wi-Fi tersebut.

| Terminal | Perangkat | Dipakai untuk |
|---|---|---|
| **A** | Laptop perekam yang tersambung Wi-Fi | Menerima datagram UDP dengan `trafik terima`. |
| **B** | Laptop pengirim yang tersambung Ethernet | Mengirim datagram UDP dengan `trafik kirim`. |
| **C** | Laptop perekam yang tersambung ke HackRF | Merekam sinyal, mengekstrak CSI, dan membuat hasil analisis. |

Cari **alamat IPv4 antarmuka Wi-Fi laptop perekam** dari detail koneksi Wi-Fi. Di Linux, bisa pakai `ip -4 -brief addr`. Contoh di bawah memakai `192.168.1.24`. Ganti alamat itu pada **kedua** perintah.

1. Di **Terminal A**, jalankan perintah ini dan tunggu tulisan `Mendengarkan UDP`.

```bash
python case_a.py trafik terima --ip 192.168.1.24 --durasi 300
```

2. Di **Terminal B**, jalankan perintah ini dan tunggu tulisan `Mengirim UDP uji`.

```bash
python case_a.py trafik kirim --ip 192.168.1.24 --durasi 270 --pps 40
```

3. Biarkan A dan B berjalan, lalu pakai **Terminal C** untuk bagian 3 dan 4. Ketika muncul `Datagram kirim: …` di B atau `Datagram terima: …` di A dan prompt shell kembali, prosesnya sudah selesai. Untuk mulai lagi, hentikan proses lama yang masih berjalan dengan **Ctrl+C di A atau B**, lalu jalankan ulang **A dulu, baru B**.

Kalau hitungan akhir di A nol, cek IPv4 klien, firewall UDP port 5005, serta apakah kedua laptop ada di jaringan router yang sama. Jika hanya punya hotspot HP, kedua laptop bisa memakai Wi-Fi hotspot selama bisa saling terhubung. Pada setup ini ada beberapa pemancar lewat udara, jadi gunakan pilot untuk memilih kelompok paket yang konsisten.

**40 datagram/s** adalah setelan Terminal B. Target Case A adalah **minimal 20 paket CSI terpilih/s** pada hasil ekstraksi di Terminal C.

## 3. Kalibrasi dan uji satu rekaman pendek

1. Dengan A dan B masih berjalan, rekam **lima detik di Terminal C**. Ganti `5180` sesuai frekuensi kanal router. Ekstrak dari nama file yang tercetak setelah `Tersimpan`:

```bash
python case_a.py rekam --raw data/pilot --sesi pilot --subjek none --skenario kosong --freq-mhz 5180 --durasi 5 --lokasi "Ruang kelas" --sumber router-kelompok --lna 32 --vga 26
python case_a.py ekstrak data/pilot/A_pilot_none_kosong.cs8 --csi data/pilot-csi
```

Periksa tiga angka dari terminal:

| Hasil | Yang dicek |
|---|---|
| L-LTF valid | Korelasi L-LTF lebih dari 0,6. Untuk checkpoint minggu 1, modul meminta minimal 20 paket valid. |
| Paket per detik | Target akhir minimal 20 paket/s **setelah** memilih pemancar. |
| Clipping | Persentase sampel yang menyentuh batas ADC sebaiknya mendekati nol. Jika signifikan, turunkan gain dan ulangi pilot. |

2. Untuk mendapat pembanding, **hentikan trafik uji di B dengan Ctrl+C** dan biarkan router tetap menyala. Di C, ulangi `rekam` dengan `--sesi hening` dan setelan lain yang sama. Ekstrak file `data/pilot/A_hening_none_kosong.cs8` dengan `--csi data/pilot-hening-csi`. Jika tidak ada paket valid pada pilot hening, terminal tetap menampilkan ringkasan.

3. Bandingkan baris `Kelompok CFO (kHz: paket)`. Pilih kelompok CFO yang konsisten dan jumlah paketnya bertambah saat trafik dinyalakan. CFO membantu memilih sumber, tapi dua perangkat bisa punya CFO mirip. Jika kelompok paket sulit dipisahkan, cari kanal kelompok yang lebih sepi dan ulangi pilot.

4. Coba filter CFO pada rekaman pilot saat trafik aktif. Misalnya jika pusatnya **−8 kHz**, masukkan **−8000 Hz**:

```bash
python case_a.py ekstrak data/pilot/A_pilot_none_kosong.cs8 --csi data/pilot-csi --cfo-hz -8000 --cfo-tol-hz 4000
```

Catat `freq`, `cfo`, `lna`, dan `vga` dari pilot yang berhasil. Lanjut ke bagian 4 setelah hasil ekstraksi dengan filter mencapai target laju dan clipping rendah. Jika laju kurang, cek pilihan sumber, kanal utama, dan kualitas L-LTF. Kalian bisa menaikkan laju UDP secara bertahap lalu mengulang pilot. Untuk sinyal lemah tanpa clipping, kalibrasikan gain atau coba `--ambang-db 8`, lalu periksa apakah paket tambahan berasal dari pemancar yang dipilih. Jika 2,4 GHz tidak menghasilkan L-LTF valid, coba 5 GHz.

## 4. Rekam semua skenario

Setiap ID sesi (`s1`, `s2`, dan `s3`) memuat empat rekaman berdurasi minimal 30 detik. Ambil tiap sesi sebagai pengulangan tersendiri.

| Label | Selama perekaman |
|---|---|
| `kosong` | Ruangan kosong selama 30 detik. |
| `diam` | Satu orang duduk diam di garis LOS. |
| `jalan_los` | Satu orang berjalan berulang melintasi LOS. |
| `jalan_dinding` | Satu orang berjalan berulang di dekat dinding tanpa melintasi LOS. |

1. Mulai ulang trafik di **A lalu B** setiap kali akan memulai sesi baru. Empat rekaman dalam satu sesi memerlukan 120 detik, ditambah waktu menyiapkan posisi dan mengekstrak data.
2. Di **Terminal C**, tempel blok Bash di bawah. Jalankan dulu dengan `sesi=s1`, lalu ulangi bloknya dengan `sesi=s2` dan `sesi=s3` setelah tiap sesi selesai. Ganti frekuensi, CFO, gain, dan filter dengan nilai yang dipakai pada pilot. Ubah nama lokasi sesuai tempat uji.

```bash
sesi=s1
freq=5180
cfo=-8000
lna=32
vga=26
cfo_tol=4000
ambang_db=10

for skenario in kosong diam jalan_los jalan_dinding; do
  subjek=P1
  if [ "$skenario" = kosong ]; then subjek=none; fi
  read -r -p "$sesi/$skenario siap dan trafik aktif? Tekan Enter: " _ || break

  python case_a.py rekam --sesi "$sesi" --subjek "$subjek" \
    --skenario "$skenario" --freq-mhz "$freq" --durasi 30 \
    --lokasi "Ruang kelas" --sumber router-kelompok \
    --lna "$lna" --vga "$vga" || break

  python case_a.py ekstrak "data/raw/A_${sesi}_${subjek}_${skenario}.cs8" \
    --cfo-hz "$cfo" --cfo-tol-hz "$cfo_tol" --ambang-db "$ambang_db" || break
done
```

3. Saat prompt pertama muncul, misalnya `s1/kosong siap dan trafik aktif? Tekan Enter:`, pastikan ruangan kosong dan A serta B masih berjalan. Tekan **Enter sekali**. C akan menampilkan `Rekam kosong selama 30 s`, berhenti merekam otomatis, lalu menampilkan `Mengekstrak …`.
4. Setelah `Mengekstrak …` muncul, kalian boleh menyiapkan skenario berikutnya. Tunggu prompt baru sebelum menekan Enter lagi. Untuk skenario berjalan, mulai saat muncul `Rekam …` dan terus berjalan sampai rekaman selesai. Jika trafik selesai ketika C masih di prompt, mulai lagi trafik di A dan B sebelum menekan Enter.
5. Setelah keempat skenario selesai, cek laju paket di hasil ekstraksi. Jalankan sesi berikutnya sebagai pengulangan terpisah dengan setelan yang sama.

### Melanjutkan sesi yang terputus

Kalau loop berhenti di tengah sesi, hapus **nama skenario yang sudah terekam** dari daftar setelah `for skenario in` sebelum menjalankan ulang blok Bash. Contohnya, jika `kosong` dan `diam` sudah selesai, pakai `for skenario in jalan_los jalan_dinding; do` dengan ID sesi yang sama.

Jika CS8 sudah tersimpan tetapi ekstraksi gagal, ulangi perintah `ekstrak` untuk file itu. Jika trafik mati di tengah perekaman dan hasilnya perlu diulang, pindahkan CS8 dan JSON pasangannya ke folder cadangan di luar `data/raw/` dan `data/csi/`, lalu ulangi skenarionya. Skrip menjaga nama rekaman yang sudah ada agar tidak tertimpa.

Kalau memakai **PowerShell** atau ingin menjalankan satu skenario saja, ini contoh untuk `s1/diam`. Sesuaikan opsi dengan hasil pilot. Ganti label skenario pada kedua perintah setiap kali berpindah. Untuk `kosong`, ganti juga subjek dari `P1` menjadi `none`.

```powershell
python case_a.py rekam --sesi s1 --subjek P1 --skenario diam --freq-mhz 5180 --durasi 30 --lokasi "Ruang kelas" --sumber router-kelompok --lna 32 --vga 26
python case_a.py ekstrak "data/raw/A_s1_P1_diam.cs8" --cfo-hz -8000 --cfo-tol-hz 4000 --ambang-db 10
```

Satu rekaman 30 detik memerlukan sekitar **1,2 GB**, sehingga 12 rekaman memerlukan **14,4 GB**. Pindahkan CS8 dan JSON pasangannya ke penyimpanan yang disetujui setelah CSV diperiksa. Simpan minimal satu contoh CS8 per skenario untuk luaran. Analisis berikut membaca CSV dan JSON di `data/csi/`.

## 5. Buat grafik dan hitung hasil

Setelah **12 CSV dan 12 JSON** dari `s1`, `s2`, dan `s3` tersedia di `data/csi/`, jalankan ini di **Terminal C**:

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
