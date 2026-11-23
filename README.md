# Case A — Deteksi Kehadiran dan Gerakan dengan Wi-Fi CSI

Kedua laptop tersambung ke access point (AP) Wi-Fi yang sama. HackRF One merekam sampel I/Q saat satu laptop mengirim trafik UDP ke laptop satunya. Skrip mencari preamble OFDM, mengoreksi CFO, dan menghitung CSI pada 52 subcarrier. Dari hasilnya, kalian membandingkan CSI dengan RSSI untuk mendeteksi gerakan dan melihat apakah orang yang duduk diam bisa dibedakan dari ruangan kosong.

## 1. Pasang alat dan jalankan demo

Siapkan akses ke satu AP Wi-Fi, dua laptop dengan Python 3.10 atau lebih baru, dan satu HackRF One dengan antena sesuai pita AP. Pada laptop yang merekam, gunakan kabel USB data dan penyimpanan yang bisa menulis sekitar **40 MB/s**.

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

## 2. Siapkan AP, posisi perangkat, dan trafik UDP

### Sambungkan perangkat

1. Sambungkan **kedua laptop lewat Wi-Fi ke AP yang sama**. Kalau satu nama Wi-Fi (SSID) dipakai banyak AP, cek **BSSID dan kanal** pada kedua laptop. Untuk setup ini, pilih tempat di mana keduanya terhubung ke radio AP yang sama.
2. Colokkan HackRF lewat USB ke **laptop penerima**. HackRF bekerja dalam mode terima. Jalankan trafik UDP selama perekaman supaya laju paket cukup untuk Case A. Beacon AP biasanya hanya sekitar 10 paket per detik per BSSID.
3. Jika bisa memilih pita pada AP kelompok, mulai dari **5 GHz** dengan antena yang sesuai. **2,4 GHz** bisa dipakai jika pilot menemukan cukup paket OFDM dengan L-LTF valid. Untuk AP kampus, gunakan ruangan yang diizinkan dosen, catat kanal yang dipakai, dan biarkan posisi serta konfigurasi AP sesuai pengaturan kampus.

### Letakkan kedua laptop dan tandai area gerak

Denah ini dilihat dari atas dan memakai AP sebagai sumber paket yang dituju. Laptop diletakkan di sisi meja agar jalur di tengah ruangan bebas untuk subjek.

```text
Dinding
      <---- lintasan jalan_dinding ---->

Laptop pengirim (B)                          Laptop penerima (A, C)
di sisi AP, di luar lintasan                         | USB
       [AP] ----------- titik duduk ----------- [HackRF]
            <----------- LOS 3–5 m ----------->
                             ^
                             | jalan_los
                             v
```

- **Laptop pengirim (Terminal B)** diletakkan di sisi AP, agak menyamping dari garis AP–HackRF. Biarkan laptop di meja selama perekaman.
- **Laptop penerima (Terminal A dan C)** diletakkan di ujung penerima, di sisi antena HackRF agar kabel USB bisa menjangkau. Sisakan ruang di depan antena untuk jalur AP–HackRF.
- **Antena AP dan HackRF** idealnya terpisah sekitar **3–5 m**, pada ketinggian sekitar **1 m** jika posisi AP bisa diatur. Jika AP sudah terpasang di dinding atau plafon, tempatkan HackRF di area dengan jalur langsung ke AP, lalu catat jarak dan tinggi yang sebenarnya.
- **Subjek** duduk kira-kira di tengah garis AP–HackRF pada skenario `diam`. Untuk `jalan_los`, ia menyeberangi garis itu dari satu sisi ke sisi lain berulang kali. Untuk `jalan_dinding`, ia berjalan dekat dinding tanpa menyeberangi garis. Tempel selotip di lantai untuk menandai garis dan lintasan.

Jaga posisi laptop, AP, antena, dan gain tetap sama selama semua sesi. Pada skenario kosong, biarkan alat tetap di tempat dan keluarkan orang dari area uji. Gunakan kode subjek seperti `P1` dengan persetujuan sesuai modul.

### Cari IPv4 penerima dan frekuensi AP

- **IPv4** diambil dari antarmuka Wi-Fi **laptop penerima**. Di Linux, jalankan `ip -4 -brief addr`. Di Windows, jalankan `ipconfig` dan lihat bagian Wi-Fi. Contoh di bawah memakai `192.168.1.24`. Ganti dengan alamat yang muncul di laptop kalian.
- **Frekuensi** diambil dari kanal utama AP. Di Linux, jalankan `iw dev` untuk melihat nama antarmuka Wi-Fi lalu jalankan `iw dev wlp2s0 link`, dengan mengganti `wlp2s0` sesuai nama antarmuka kalian. Pakai angka setelah `freq:` dalam MHz. Di Windows, `netsh wlan show interfaces` menampilkan kanal koneksi. Contoh kanal 1, 6, dan 11 pada 2,4 GHz masing-masing **2412, 2437, dan 2462 MHz**. Kanal 36 pada 5 GHz adalah **5180 MHz**.
- Cek BSSID dan kanal lagi sebelum memulai sesi baru, terutama pada jaringan dengan banyak AP. Rekaman yang dibandingkan harus memakai kanal yang sama dan sumber paket yang konsisten.

### Buka tiga terminal

| Terminal | Perangkat | Dipakai untuk |
|---|---|---|
| **A** | Laptop penerima di sisi HackRF | Menerima datagram UDP dengan `trafik terima`. |
| **B** | Laptop pengirim di sisi AP | Mengirim datagram UDP dengan `trafik kirim`. |
| **C** | Laptop perekam yang tersambung ke HackRF | Merekam sinyal, mengekstrak CSI, dan membuat hasil analisis. |

Gunakan **IPv4 laptop penerima pada kedua perintah**. A dan C dibuka di laptop yang sama.

1. Di **Terminal A**, jalankan perintah ini dan tunggu tulisan `Mendengarkan UDP`.

```bash
python case_a.py trafik terima --ip 192.168.1.24 --durasi 300
```

2. Di **Terminal B**, jalankan perintah ini dan tunggu tulisan `Mengirim UDP uji`.

```bash
python case_a.py trafik kirim --ip 192.168.1.24 --durasi 270 --pps 40
```

3. Biarkan A dan B berjalan, lalu pakai **Terminal C** untuk bagian 3 dan 4. Ketika muncul `Datagram kirim: …` di B atau `Datagram terima: …` di A dan prompt shell kembali, prosesnya sudah selesai. Untuk mulai lagi, hentikan proses lama yang masih berjalan dengan **Ctrl+C di A atau B**, lalu jalankan ulang **A dulu, baru B**.

Untuk uji koneksi cepat sebelum merekam, gunakan perintah yang sama dengan `--durasi 20` di A dan `--durasi 10` di B. Setelah selesai, pastikan hitungan `Datagram terima` di A lebih dari nol, lalu mulai ulang dengan durasi normal. Jika hasilnya nol, cek IPv4 Wi-Fi penerima dan izin firewall untuk UDP port 5005 di jaringan uji. Beberapa AP memblokir komunikasi antarklien. Jika itu terjadi, gunakan AP lain yang diizinkan dan mendukung komunikasi antarklien.

**40 datagram/s** adalah setelan Terminal B. Target Case A adalah **minimal 20 paket CSI terpilih/s** pada hasil ekstraksi di Terminal C.

## 3. Kalibrasi dan uji satu rekaman pendek

1. Dengan A dan B masih berjalan, rekam **lima detik di Terminal C**. Ganti `5180` dengan frekuensi kanal utama AP dalam MHz. Ekstrak dari nama file yang tercetak setelah `Tersimpan`:

```bash
python case_a.py rekam --raw data/pilot --sesi pilot --subjek none --skenario kosong --freq-mhz 5180 --durasi 5 --lokasi "Ruang kelas" --sumber ap-wifi --lna 32 --vga 26
python case_a.py ekstrak data/pilot/A_pilot_none_kosong.cs8 --csi data/pilot-csi
```

Periksa tiga angka dari terminal:

| Hasil | Yang dicek |
|---|---|
| L-LTF valid | Korelasi L-LTF lebih dari 0,6. Untuk checkpoint minggu 1, modul meminta minimal 20 paket valid. |
| Paket per detik | Target akhir minimal 20 paket/s **setelah** memilih pemancar. |
| Clipping | Persentase sampel yang menyentuh batas ADC sebaiknya mendekati nol. Jika signifikan, turunkan gain dan ulangi pilot. |

2. Untuk mendapat pembanding, **hentikan trafik uji di B dengan Ctrl+C** dan biarkan AP tetap menyala. Di C, ulangi `rekam` dengan `--sesi hening` dan setelan lain yang sama. Ekstrak file `data/pilot/A_hening_none_kosong.cs8` dengan `--csi data/pilot-hening-csi`. Jika tidak ada paket valid pada pilot hening, terminal tetap menampilkan ringkasan.

3. Bandingkan baris `Kelompok CFO (kHz: paket)`. HackRF bisa menangkap paket dari AP dan laptop pengirim. Pilih satu kelompok CFO yang konsisten dan bertambah saat trafik uji aktif. CFO saja belum memastikan siapa pemancarnya. Jika kelompok paket sulit dipisahkan, coba AP atau pita lain yang diizinkan dan ulangi pilot. Jika yang terpilih adalah pancaran laptop pengirim, tandai LOS dari laptop itu ke HackRF dan catat sumbernya. Jika identitas pemancar belum pasti, gunakan garis AP–HackRF sebagai acuan tata letak dan catat keterbatasan ini di laporan.

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
2. Di **Terminal C**, tempel blok Bash di bawah. Jalankan dulu dengan `sesi=s1`, lalu ulangi bloknya dengan `sesi=s2` dan `sesi=s3` setelah tiap sesi selesai. Ganti frekuensi, CFO, gain, dan filter dengan nilai yang dipakai pada pilot. Ubah lokasi sesuai tempat uji. Isi `sumber` dengan perangkat yang dipilih saat pilot, atau pakai `kelompok-cfo-pilot` jika baru kelompok CFO-nya yang diketahui. Gunakan label yang sama di setiap sesi.

```bash
sesi=s1
freq=5180
cfo=-8000
lna=32
vga=26
cfo_tol=4000
ambang_db=10
sumber=ap-wifi

for skenario in kosong diam jalan_los jalan_dinding; do
  subjek=P1
  if [ "$skenario" = kosong ]; then subjek=none; fi
  read -r -p "$sesi/$skenario siap dan trafik aktif? Tekan Enter: " _ || break

  python case_a.py rekam --sesi "$sesi" --subjek "$subjek" \
    --skenario "$skenario" --freq-mhz "$freq" --durasi 30 \
    --lokasi "Ruang kelas" --sumber "$sumber" \
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
python case_a.py rekam --sesi s1 --subjek P1 --skenario diam --freq-mhz 5180 --durasi 30 --lokasi "Ruang kelas" --sumber ap-wifi --lna 32 --vga 26
python case_a.py ekstrak "data/raw/A_s1_P1_diam.cs8" --cfo-hz -8000 --cfo-tol-hz 4000 --ambang-db 10
```

Satu rekaman 30 detik memerlukan sekitar **1,2 GB**, sehingga 12 rekaman memerlukan **14,4 GB**. Pindahkan CS8 dan JSON pasangannya ke penyimpanan yang disetujui setelah CSV diperiksa. Simpan minimal satu contoh CS8 per skenario untuk luaran. Analisis berikut membaca CSV dan JSON di `data/csi/`.

## 5. Buat grafik dan hitung hasil

**Untuk dataset yang ada di repo ini**, S1 dan S2 lengkap, sedangkan S3 hanya memiliki pengukuran asli untuk skenario kosong. Jalankan evaluasi dua sesi lengkap dari Terminal C:

```bash
python case_a.py analisis --sesi s1 s2 --eksplorasi
```

Hasil di `hasil/` menggunakan delapan rekaman HackRF dari S1 dan S2. Ambang dilatih dari S1 dan diuji di S2, lalu giliran dibalik. File sintetis S3 dari pengolahan sebelumnya disimpan bersama data awalnya di `data/csi/`. Ringkasan S3 untuk laporan ada di `hasil/ringkasan_s3.csv`. Baris kosong memakai pengukuran S3 yang asli. Baris diam, jalan melintasi LOS, dan jalan dekat dinding berisi rata-rata pengukuran S1 dan S2 per skenario. Ringkasan ini berada di luar evaluasi akurasi, FPR, dan FNR.

Log perekaman S2 mencatat trafik UDP satu arah dari terminal A ke B. Catat perbedaan arah trafik itu saat membahas hasil antar sesi.

### Jika semua tiga sesi sudah direkam

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
