## Struktur kode aktif (dirapikan 20 November 2026)

Kode dashboard dikelompokkan berdasarkan menu. Tampilan, fitur, kunci sesi, dan perhitungan tetap sama.

| File | Kegunaan |
|---|---|
| `app_v02.py` | Titik masuk: pengaturan aplikasi, navigasi, dan sesi bersama. |
| `data_engine.py` | Registrasi BO, pembacaan/pemetaan BNPB, dan kualitas udara. |
| `ui_components.py` | Komponen bersama: tabel, grafik interaktif, detail pilihan, periode data, dan format tampilan. |
| `menus/profil_bo.py` | Profil, peta lokasi, dan penambahan Business Operation. |
| `menus/import_data.py` | Unggah, pratinjau, validasi, dan aktivasi dua dataset. |
| `menus/overview.py` | KPI, grafik kejadian/komposisi bencana, dampak, dan regional. |
| `menus/analisis_risiko.py` | Perhitungan likelihood/impact, matriks risiko, batas skor, dan rincian. |
| `menus/top_risk.py` | Peringkat 10 pasangan BO-bencana dan penentuan BO Prioritas P80. |
| `menus/asisten_bcp.py` | Asisten BCP, klarifikasi pertanyaan, dan panel percakapan. |

Jalankan tetap melalui `Buka Dashboard.vbs` atau `Start-Dashboard.ps1`; titik masuk Streamlit tetap `app_v02.py`. Semua sembilan file Python di atas harus disalin bersama folder `menus`, `data`, konfigurasi `.streamlit`, `style.css`, dan `requirements.txt` ketika aplikasi dipindahkan. File pengujian ada di `tests`; file launcher membantu penggunaan lokal. Modul lama yang sudah digabung tidak diperlukan lagi.

Pembagian ini mempertahankan fungsi yang dipakai lintas menu pada dua komponen bersama agar tidak disalin berulang. File per menu tidak harus berdiri sendiri. Bagian dokumentasi lama di bawah tetap disimpan sebagai riwayat pengembangan.

## Aturan template aktif — v2.1

Sesuai konfirmasi pengguna, sel kosong pada enam kolom impact BNPB yang tersedia berarti nol. Nilai invalid dan kolom yang hilang tetap ditandai. Jumlah konversi ditampilkan saat import; metode terbaru ada di METODE_RISIKO.md. Ketentuan lama yang menyebut semua sel kosong tidak tersedia sudah digantikan aturan ini.

## Metode aktif: Persentil berbobot v2

Likelihood menggunakan jumlah kejadian per BO × bencana dan batas P20/P40/P60/P80. Impact menggunakan rata-rata per kejadian dari enam indikator BNPB dan indeks kategori AQI dan durasi pada H+0–H+7 yang cocok wilayah, normalisasi peringkat positif 0–100, dan bobot manusia meninggal 30%, hilang 10%, terluka 10%; aset/lingkungan Karhutla: rumah rusak 10%, fasum rusak 10%, udara 30%; selain Karhutla: rumah rusak 15%, rumah terendam 15%, fasum rusak 20%. Indeks nol mendapat impact 1; indeks positif menggunakan P25/P50/P75 untuk skor 2–5. Risiko = L × I.

Penjelasan resmi versi dashboard ini ada pada [METODE_RISIKO.md](METODE_RISIKO.md). Pilihan indikator impact tunggal sudah dihapus. Aturan skor tengah untuk nilai seragam pada v1 tidak dipakai lagi; aturan persentil ketat dijelaskan dalam dokumen. Skor antar-upload tidak otomatis sebanding. Bagian lama di bawah adalah riwayat pengembangan.

Pengujian: tests/test_percentiles.py dan tests/test_simple_workspace.py.
# BCP Atlas v0.3 — Workspace analisis BCP

## Menjalankan di laptop ini

Klik dua kali **Buka Dashboard.vbs** di folder aplikasi. Browser akan terbuka otomatis. Petunjuk singkat tersedia di `CARA-BUKA.txt`.

Folder aplikasi aktif:
`G:\Shared drives\ERM\SANFantastic & AIF\05. PICA - BCP Map - Faiq\bcp-dashboard`

Alternatif: jalankan `Start-Dashboard.ps1` dari folder ini. Launcher menggunakan lokasi foldernya sendiri.

## Komputer lain

Pasang Python 3.12, lalu klik `Siapkan Dashboard.cmd` sekali pada setiap komputer. Library dipasang di `%LOCALAPPDATA%\BCP-Atlas\python312`, bukan di Shared Drive. Setelah selesai, klik `Buka Dashboard.vbs` untuk penggunaan sehari-hari. Panduan singkat tersedia di `CARA-BUKA.txt`.

## Upload file BNPB

1. Buka **Import BNPB** lalu pilih `Data bencana tingkat kabupaten kota.xlsx`.
2. Parser otomatis memilih **Sheet1** dengan header di **baris 2**. Sheet2 adalah pivot Count dan diabaikan.
3. Periksa periode yang otomatis mengikuti tanggal valid pada file. File 2022–2026 dapat digunakan dengan struktur kolom yang sama.
4. Tinjau 12 pemetaan dan kualitas dampak. Pilih apakah baris identik tambahan dikeluarkan. Default mempertahankan baris sumber agar tidak menghapus kejadian secara diam-diam.
5. Centang sudah meninjau, lalu klik **Gunakan data ini pada dashboard**.
6. Buka Overview, Profil BO, Analisis Bencana, atau Perbandingan BO. Grafik dan ekspor mengikuti filter.

Dataset berikutnya mengganti dataset aktif, bukan menambahkan data. Ini menghindari penggandaan ketika file snapshot diunggah ulang. **Kosongkan data sesi** menghapus dataset sementara aplikasi dan mengembalikan kondisi sebelum upload.

## Hasil pemeriksaan file yang diberikan

- Sheet1: 8.993 baris detail, 16 kolom; tanggal 01/01/2024–09/09/2026.
- Tahun 2024: 3.720 baris; 2025: 3.444; 2026: 1.829 (tahun parsial).
- Sembilan kategori bencana; kolom dampak: Meninggal, Hilang, Terluka, Rumah Rusak, Rumah Terendam, Fasum Rusak.
- 26 baris identik tambahan jika dibandingkan seluruh isi selain No. Nomor identitas bencana kosong pada 3.580 baris, sehingga tidak dapat dijadikan satu-satunya kunci kejadian.
- Semua 12 wilayah BO ditemukan. Ada 269 catatan dalam cakupan wilayah BO sebelum mengeluarkan duplikasi identik, atau 267 setelahnya.
- Sheet2 menggunakan Count of Hilang/Meninggal/Terluka: itu menghitung sel terisi, bukan total korban. Dashboard menjumlahkan nilai numerik pada data detail.
- Nilai kosong tidak dianggap nol. Agregat dampak ditampilkan bersama kelengkapan datanya; nilai kosong total ditampilkan sebagai tidak tersedia.

Angka pemeriksaan di atas adalah deskripsi snapshot file yang diberikan pengguna. Aplikasi menghitung dari upload baru dan tidak memuat angka-angka ini sebagai data operasional bawaan.

## Pemetaan wilayah

| BO | Kabupaten/kota untuk analisis | ID Kabupaten pada file |
|---|---|---|
| Jakarta | Kota Administrasi Jakarta Selatan | 3174 |
| Surabaya | Kota Surabaya | 3578 |
| Semarang | Kota Semarang | 3374 |
| Medan | Kota Medan | 1271 |
| Pekanbaru | Kota Pekanbaru | 1471 |
| Palembang | Kota Palembang | 1671 |
| Jambi | Kota Jambi | 1571 |
| Pontianak | Kota Pontianak | 6171 |
| Banjarmasin | Kabupaten Banjar | 6303 |
| Balikpapan | Kota Balikpapan | 6471 |
| Samarinda | Kota Samarinda | 6472 |
| Makassar | Kota Makassar | 7371 |

Alamat asli pengguna disimpan pada `data/branches.json`, beserta sumber verifikasi dan catatan. Sumber lengkap juga dapat dibuka pada Master BO & Metode di dashboard. ID diambil dengan mencocokkan nama/provinsi pada workbook, bukan diasumsikan dapat dipakai untuk semua sistem kode administratif.

Catatan khusus:

- Jakarta menggunakan wilayah administratif Jakarta Selatan, bukan seluruh DKI.
- Banjarmasin menggunakan Kabupaten Banjar. Sumber Desa Mekar Raya menyebut Kecamatan Kertak Hanyar, sementara alamat awal menulis Kertak Manyar.
- Semarang menggunakan Kota Semarang. Detail kelurahan/kecamatan perlu ditinjau: Pendrikan Kidul berada di Semarang Tengah, sementara listing jalan Menteri Supeno 28–30 menyebut Mugassari, Semarang Selatan. Perbedaan ini tidak mengubah kota yang dipakai.
- Koordinat gedung belum diverifikasi. Pin simulasi v0.1 telah diganti daftar lokasi/alamat dan tautan pencarian Google Maps. Tidak ada posisi kantor yang ditebak.

## Perhitungan dan batas interpretasi

- Catatan kejadian adalah jumlah baris diterima, setelah pilihan deduplikasi dan periode import.
- Join memakai ID Kabupaten 4 digit, dengan pengecekan nama/provinsi pada wilayah master. Kota/kabupaten dengan nama mirip tidak digabungkan.
- Meninggal/Hilang/Terluka dalam jiwa; kolom kerusakan ditampilkan terpisah dalam unit. Tidak digabung menjadi satu total korban/kerugian karena kategorinya dapat tumpang tindih.
- Dampak numerik negatif, pecahan, atau teks yang tidak valid ditandai tidak tersedia. Baris kejadiannya tetap dapat digunakan; masalahnya ditampilkan pada import.
- Angka nol pada matriks berarti tidak ada catatan dalam data/filter, bukan wilayah bebas bencana. Sel dampak kosong tetap kosong, bukan nol.
- Perbandingan BO dapat diurutkan berdasarkan frekuensi atau dampak, tetapi belum menjadi risk score atau prioritas BCP final. Perlu metode penilaian, BIA, dan kesiapan operasional untuk tahap tersebut.
- Riwayat bencana tingkat kota/kabupaten tidak otomatis membuktikan kantor terdampak. Tahun 2026 hanya parsial; gunakan periode setara untuk membandingkan tahun.

## Penyimpanan

Tidak ada database atau penyimpanan upload ke disk. Raw data, preview, dan dataset aktif hanya ada di `st.session_state`. Tidak menggunakan cache global untuk data bencana. Sesi baru/refresh/restart dapat kehilangan data. Ekspor CSV hanya diunduh ketika pengguna menekan tombol. File sumber asli tidak disertakan pada ZIP.

## Kode dan pengujian

- `app_v02.py`: kode utama dashboard dan UI.
- `data_engine.py`: parser, validasi, join wilayah dan agregasi.
- `data/branches.json`: master 12 lokasi dan referensi.
- `style.css`: tampilan.
- `tests/test_data_engine.py`: unit test pemetaan, tanggal, nilai kosong, duplikasi dan agregasi.
- `tests/verify_real_source.py`: tes read-only untuk snapshot asli dan semua halaman UI.
- `tests/test_simple_workspace.py`: tes alur import dan pengosongan sesi.

```powershell
python tests/test_data_engine.py
python tests/test_simple_workspace.py
python tests/verify_real_source.py "path-ke-file-asli.xlsx"
```

File prototipe v0.1, data demo, tangkapan layar, dan dokumentasi duplikat telah dibersihkan. Kode aktif dan pengujian alur BNPB tetap tersedia.


## Fitur workspace v0.3

- Overview: indikator BO, ringkasan temuan, komposisi bencana, matriks frekuensi, tren bulanan, dan diagram kelompok wilayah yang dapat diperbesar.
- Profil BO, Analisis Bencana, dan Perbandingan BO: filter tahun, wilayah, BO, jenis bencana, dan rentang tanggal; grafik mendukung hover, zoom, dan unduh PNG.
- Eksplorasi Data: pencarian teks, filter catatan dengan dampak positif, pagination, dan ekspor seluruh hasil pencarian.
- Kualitas Data: kelengkapan enam kolom dampak, baris ditolak, duplikasi, cakupan master BO, serta identitas file dan SHA-256.
- Pusat Laporan: ekspor Excel lima sheet mengikuti filter, termasuk detail kejadian, ringkasan BO, master, kualitas dampak, dan sumber. Nilai kosong tetap kosong; teks sumber ditulis sebagai teks Excel.
- Import BNPB: periode terdeteksi dari file, preview dan aktivasi dataset tetap terpisah.

Kode tampilan utama tetap `app_v02.py` agar entrypoint dan launcher kompatibel. Komponen analisis dan laporan baru berada di `ui_components.py`; tema berada di `style.css`. Jalankan `python tests/test_simple_workspace.py` untuk memeriksa fitur baru.

Klik ulang **Buka Dashboard.vbs** untuk membuka server v0.3. Sesi versi lama tidak dihentikan otomatis. Unggah file pada sesi versi baru untuk memulai.

Aplikasi ini masih workspace lokal tanpa login, hak akses pengguna, database Oracle, atau audit log permanen. Kesiapan multi-user perusahaan memerlukan tahap integrasi dan pengamanan berikutnya. Penetapan prioritas risiko BCP tetap memerlukan metode assessment yang disepakati.

## Auto-reload saat mengedit Python

Launcher dan konfigurasi Streamlit memakai `server.fileWatcherType = "poll"` dan `server.runOnSave = true`. Folder `.packages`, `.venv`, cache, dan tests dikecualikan dari pemantauan. Buka ulang launcher untuk masuk ke server dengan konfigurasi ini, kemudian simpan perubahan Python menggunakan Ctrl+S. Perubahan file Python yang digunakan aplikasi memicu rerun halaman. Perubahan CSS/JSON dapat dimuat melalui menu Streamlit > Rerun; perubahan launcher, dependensi, atau pengaturan server memerlukan restart. Dataset sesi biasanya bertahan pada rerun biasa, tetapi bukan penyimpanan permanen.

## Revisi navigasi dan periode analisis

Import BNPB berada di atas Overview. Diagram alur proses hanya tampil pada Import BNPB. Panel Tahun, Wilayah, Business Operation, Jenis bencana, dan Rentang tanggal telah dihapus dari halaman analisis. Periode analisis dan laporan mengikuti dataset yang diaktifkan saat import. Profil BO tetap memiliki pilihan BO; pencarian detail dan pengurutan perbandingan tetap tersedia.

## Instalasi per pengguna Shared Drive

BCP DASHBOARD - PENGGUNA SHARED DRIVE

PERTAMA KALI DI SETIAP KOMPUTER WINDOWS
1. Pastikan Python 3.12 terpasang (python.org atau bantuan IT).
2. Pastikan folder dashboard tersedia melalui Google Drive dan tersinkron.
3. Klik dua kali Siapkan Dashboard.cmd, tunggu pesan Siap.
   Instalasi membutuhkan internet/akses repository Python yang diizinkan IT.
   Library disimpan di %LOCALAPPDATA%\BCP-Atlas\python312 pada komputer masing-masing.
4. Klik dua kali Buka Dashboard.vbs.

PEMAKAIAN BERIKUTNYA
Klik Buka Dashboard.vbs. Browser default terbuka otomatis.
Untuk menggunakan Chrome, jadikan Chrome browser default atau salin URL ke Chrome.
Jika VBS dibatasi IT, gunakan Start-Dashboard.ps1 sesuai kebijakan komputer.
Tidak perlu menjalankan instalasi setiap kali. Jalankan ulang jika requirements.txt berubah.

DATA MASING-MASING PENGGUNA
Pilih Import BNPB, unggah file sendiri, tinjau, lalu aktifkan.
Server hanya menerima koneksi pada 127.0.0.1 (komputer sendiri).
Upload berada di memori sesi dan tidak disimpan di Shared Drive.
Data pengguna lain tidak otomatis muncul. Sesi baru/restart mungkin perlu upload ulang.
File hasil ekspor disimpan sesuai lokasi unduhan yang dipilih pengguna.

EDIT KODE
Kode aplikasi tetap digunakan bersama dari Shared Drive; edit akan berlaku bagi pengguna lainnya.
Simpan file Python untuk auto-reload. CSS/JSON: menu Streamlit > Rerun.
Dependensi, launcher, dan konfigurasi memerlukan restart server.
Menutup browser tidak menghentikan server; server berhenti saat komputer dimatikan.
Folder .packages masih mendukung instalasi lama pada komputer pembuat; jangan dihapus dahulu.

## Fungsi file dan folder

| File/folder | Fungsi |
|---|---|
| Buka Dashboard.vbs | Membuka dashboard tanpa jendela terminal. |
| Siapkan Dashboard.cmd | Memulai instalasi awal pada setiap komputer. |
| setup_dashboard.py | Membuat environment lokal pengguna dan memasang library dari requirements.txt. |
| click_launcher.pyw | Memulai/memakai ulang server lokal, memilih port, memeriksa kesiapan, dan membuka browser. |
| run_local.py | Menjalankan Streamlit dan app_v02.py dengan dependensi yang sesuai. |
| Start-Dashboard.ps1 | Launcher alternatif melalui PowerShell. |
| app_v02.py | Halaman, navigasi, import, visualisasi, dan interaksi utama dashboard. |
| ui_components.py | Komponen tampilan, ringkasan, pencarian, kualitas data, dan laporan Excel. |
| data_engine.py | Membaca dan memvalidasi data, mencocokkan wilayah BO, dan menghitung agregat. |
| style.css | Warna, font, jarak, dan tata letak. |
| requirements.txt | Daftar versi library untuk instalasi. |
| data/branches.json | Master alamat dan pemetaan wilayah 12 BO. |
| .streamlit/config.toml | Konfigurasi tema, server lokal, batas upload, dan auto-reload. |
| .packages/ | Library cadangan yang masih digunakan instalasi lama di komputer pembuat serta pengujian. |
| tests/test_data_engine.py | Pengujian parser, validasi, dan perhitungan. |
| tests/test_simple_workspace.py | Pengujian alur navigasi, aktivasi dataset, dan reset sesi. |
| tests/verify_real_source.py | Pengujian hasil mapping dengan snapshot Excel BNPB asli. |
| CARA-BUKA.txt | Panduan singkat pengguna. |
| README.md | Dokumentasi aplikasi dan metode analisis. |
| .gitignore | Aturan mengecualikan dependensi, cache, dan konfigurasi rahasia dari Git. |

Pembersihan: app.py (entrypoint alternatif), environment .venv lama di Shared Drive, dan cache __pycache__ telah dihapus. Cache dapat muncul kembali saat Python berjalan. File kode dan library di atas tetap diperlukan untuk pemakaian, instalasi, atau pemeliharaan aplikasi.




## Halaman import ringkas

Import menampilkan upload, preview sumber, periode, pilihan duplikasi, pemeriksaan kesalahan, dan aktivasi/reset sesi. Pilihan Sheet detail, keterangan header/sheet, empat kartu ringkasan import, serta tabel Pemetaan 12 BO dan kualitas dampak telah dihapus. Aplikasi memilih sheet pertama dalam urutan workbook yang memiliki kolom detail BNPB yang dibutuhkan. Jika workbook memuat beberapa sheet detail, hanya sheet pertama tersebut digunakan; preview sumber dapat diperiksa sebelum aktivasi. Validasi dan perhitungan tetap dijalankan.


## Asisten BCP — tanya jawab data lokal

Buka menu Asisten BCP setelah mengaktifkan dataset BNPB. Pilih cakupan **Wilayah 12 BO** (default, mengikuti wilayah dashboard) atau **Seluruh dataset unggahan**, lalu tuliskan pertanyaan lengkap. Setiap pertanyaan berdiri sendiri.

Contoh:
- Berapa kejadian banjir di Semarang tahun 2026?
- Berapa jumlah korban meninggal akibat gempa bumi selama 2026?
- Berapa rumah rusak akibat banjir di Regional 2 tahun 2024 sampai 2026?

Versi ini menggunakan pengenal pertanyaan berbasis aturan dan agregasi Python, bukan model AI generatif. Tidak memerlukan API key dan tidak mengirim data ke layanan AI. Mendukung jumlah kejadian serta total enam indikator impact, satu BO/regional, satu bencana, dan satu tahun/rentang tahun. Pertanyaan di luar kemampuan tersebut ditolak dengan penjelasan; tidak menyusun skenario BCP.

Jawaban mencantumkan cakupan, periode efektif, catatan tahun parsial, dan data dasar yang dapat diunduh. Jika nilai impact tidak lengkap, hanya subtotal yang dilaporkan. Cakupan nasional tidak otomatis dianggap lengkap. Pergantian aktivasi dataset menghapus jawaban sebelumnya. Jawaban disimpan hanya pada sesi browser; kode berada pada `menus/asisten_bcp.py`. Tes perilaku: `tests/test_menus/asisten_bcp.py`.


### Klarifikasi pertanyaan Asisten BCP

Istilah korban jiwa/korban, rumah terdampak, kerusakan, dan dampak memunculkan pilihan sebelum dihitung. Pilihan tidak dipilih otomatis; tekan Gunakan pilihan setelah menentukan maksud. Batalkan klarifikasi atau kirim pertanyaan baru untuk menggantinya. Pergantian dataset/cakupan membatalkan klarifikasi sebelumnya.

Meninggal, hilang, dan terluka ditampilkan masing-masing, tidak digabung menjadi jumlah orang unik. Jumlah warga terdampak/pengungsi belum tersedia; pengguna dapat memilih indikator lain dengan penjelasan keterbatasan tersebut. Negasi seperti tidak/bukan/kecuali/selain ditolak agar tidak menghasilkan filter yang salah. Sinonim tambahan: kematian, cedera, rumah yang rusak/terendam, fasilitas umum yang rusak. Pertanyaan singkat seperti Berapa banjir di Semarang dikenali sebagai jumlah kejadian. Filter bulan, perbandingan, dan skor masih menggunakan menu analisis.


### Widget asisten dan status ChatGPT (28 Oktober 2026)

Tombol Asisten BCP di pojok kanan bawah membuka panel tanya jawab lokal. Panel meminta aktivasi data jika dataset belum tersedia. Pada halaman Asisten BCP, gunakan tampilan penuh agar formulir tidak digandakan.

Model ChatGPT BELUM terhubung. Pengguna memilih tetap mengutamakan ChatGPT Plus dan memverifikasi kelayakan akses dahulu, bukan API berbayar. Tidak ada kredensial yang diambil atau dataset yang dikirim ke OpenAI oleh widget ini.

Dokumentasi Sign in with ChatGPT menyebut akses paket untuk aplikasi open-source dan klien privat terpilih; kepemilikan Plus tidak membuktikan aplikasi internal ini telah mendapat akses. Kelayakan aplikasi ini belum terverifikasi. Langkah berikutnya adalah konfirmasi akses untuk aplikasi privat melalui jalur resmi, kemudian implementasi OAuth dan pengujian akun pengguna.

Referensi: https://developers.openai.com/siwc/quickstart dan https://developers.openai.com/siwc/request-client-id


Cakupan BCP diperbarui: 8 kategori (Banjir, Cuaca ekstrem, Karhutla, Tanah longsor, Gempa bumi, Gelombang pasang dan abrasi, Erupsi gunung api, Tsunami). Kekeringan dikeluarkan dari kejadian yang dianalisis, dampak, kalibrasi persentil, KPI, regional, matriks, Top Risk, dan jawaban asisten. Sumber asli tetap dipertahankan; baris Kekeringan tercatat sebagai dikeluarkan saat import. Dataset aktif lama diproses ulang otomatis. Maksimal 12 BO × 8 kategori = 96 kombinasi pada heatmap. Batas persentil dihitung ulang dari cakupan tersebut.


## Interaksi rincian data

Klik batang BO/bencana, titik tren bulanan, gelembung regional, penanda peta BO, atau batang Top Risk untuk membuka Detail Pilihan. Matriks mempunyai penanda pilihan di tengah sel; klik penanda untuk rincian pasangan BO–bencana. Tabel Rincian Kejadian, Dampak, dan Skor mendukung pemilihan satu baris. Hapus pilihan menutup rincian. Setiap grafik mempunyai pilihan sendiri dan pilihan baru digunakan setelah aktivasi dataset yang baru.

Panel detail menyaring tampilan data sumber, menyediakan subtotal dampak, pratinjau 200 baris, dan unduhan seluruh hasil. Pilihan tidak mengubah populasi persentil atau perhitungan likelihood/impact/risiko. Rumus calculate() tetap sama. Komposisi bencana menggunakan batang agar mendukung klik pilihan secara native. Implementasi berada pada ui_components.py.


## Tabel berkolom tetap

Seluruh halaman memakai `ui_components.py` untuk menampilkan tabel tanpa menu titik tiga, autosize, pin, atau hide column. Lebar ditetapkan berdasarkan jenis kolom; teks panjang dibungkus dan tabel lebar tetap dapat digulir. Tabel rincian tetap mendukung pemilihan baris melalui klik atau Enter/Spasi. Format tanggal, jumlah, persentase impact, dan indikator nilai tidak tersedia dipertahankan. Komponen ini memakai Streamlit Components v2 dari versi dependensi yang sudah ditetapkan.


Komposisi Bencana memakai pie interaktif pada `ui_components.py`: klik irisan atau legenda membuka Jumlah kejadian per wilayah dan ringkasan dampak. Penanda legenda memungkinkan pemilihan kategori yang irisannya sangat kecil. Ekspor gambar PNG tetap tersedia. Modul ini perlu disertakan saat menyalin aplikasi ke server.


## Perubahan aktif: impact v3.0 dua file

Metode aktif v5.0 memakai tujuh indikator. Upload BNPB serta kualitas udara harian (Kabupaten/Kota, Tanggal, Kualitas Udara), tinjau preview dan kecocokan, lalu aktifkan keduanya. `data_engine.py` memvalidasi indeks dan meringkas delapan hari H+0–H+7 pada wilayah yang sama tanpa menambah baris kejadian. `menus/analisis_risiko.py` memakai bobot berbeda menurut bencana: manusia 30/10/10%; Karhutla rumah rusak/fasum/udara 10/10/30%; selain Karhutla rumah rusak/terendam/fasum 15/15/20%. Likelihood tidak berubah. Udara yang tidak cocok tidak dianggap nol; impact/risiko yang belum lengkap tampil N/D. Untuk Excel udara, hanya sheet pertama yang digunakan; sheet lain tidak dibaca. Kesesuaian lokasi sumber/proxy ditinjau pada file sumber. Aturan lengkap: METODE_RISIKO.md.


## Udara v5.0 — kategori dan durasi
Good (AQI 0–50) memberi dampak 0. Kategori berikutnya bernilai 25,50,75,100 untuk batas >50–100, >100–150, >150–200, >200. Dampak udara per kejadian = rata-rata nilai harian H+0–H+7 (hari kejadian termasuk), lalu rata-rata per BO × Karhutla dan bobot 30% tanpa normalisasi peringkat ulang. Kedelapan hari wajib tersedia; jika tidak, impact/risiko N/D. Likelihood tidak berubah. Unggah udara sampai H+7 kejadian terakhir. Kategori dan skala dampak dapat ditinjau pada analisis; skala 0–100 merupakan kebijakan dashboard. Lihat METODE_RISIKO.md untuk aturan lengkap.


## Bobot per jenis bencana v5.0
Udara hanya berlaku untuk Karhutla, dengan bobot 30%. Rumah Terendam tidak berbobot dan tidak diwajibkan untuk Karhutla. Selain Karhutla, udara tidak dihitung dan tidak diwajibkan; rumah rusak/rumah terendam/fasum berbobot 15/15/20%. Kedua kelompok mempertahankan manusia 50% dan aset/lingkungan 50%. File BNPB dapat diaktifkan tanpa udara; Karhutla yang belum memiliki udara lengkap H+0–H+7 tetap N/D, bencana lain tidak terhalang. Tabel Komposisi Impact menampilkan kedua kelompok bobot. Indikator yang tidak berlaku tidak ikut pembanding normalisasi. Rumus likelihood dan batas skor akhir impact tetap sama.


## BO Prioritas pada Top Risk

`menus/top_risk.py` menghitung T, K dan S dari seluruh hasil pemetaan, tanpa menghitung ulang likelihood atau impact. Prioritas jika R individu 25 ATAU minimal K kategori memiliki R >T ATAU kumulatif >S. T dan S memakai P80; K memakai P80 jumlah kategori tinggi, dibulatkan ke atas, minimum 2. K dan S mengacu pada BO lengkap; N/D tidak diisi nol. Bagian BO Prioritas di bawah grafik Top Risk menampilkan ambang aktif, seluruh BO, alasan dan penjelasan metode. Sertakan `menus/top_risk.py` bersama modul aplikasi saat dipindahkan ke server. Verifikasi metode: `tests/test_bo_priorities.py`.


## Tambah Business Operation

Di Profil BO, buka Tambah Business Operation, isi BO, Alamat, Kecamatan, Kabupaten/Kota, dan Provinsi, lalu Simpan Business Operation. Kelima isian wajib; nama BO tidak boleh sama dengan yang sudah terdaftar (tanpa membedakan huruf besar/kecil). Profil tambahan disimpan secara atomik di `data/custom_branches.json`, terpisah dari `data/branches.json` yang tetap menjadi master awal. File tambahan baru dibuat pada penyimpanan pertama. Reset dataset tidak menghapus profil BO. Folder data perlu dapat ditulis oleh akun yang menjalankan aplikasi.

ID Kabupaten ditentukan dari pasangan nama kabupaten/kota dan provinsi pada file BNPB, dengan mempertahankan perbedaan kota dan kabupaten. Nama kabupaten BNPB yang tanpa awalan Kabupaten tetap dikenali. Jika belum ada file, wilayah yang sudah terdapat pada master awal bisa dikenali; wilayah lain menunggu BNPB. Nama ambigu atau tidak ditemukan tidak ditebak. Status terlihat pada Profil BO. BO yang belum terpetakan tampil N/D pada risiko/prioritas, bukan nol kejadian yang diartikan risiko rendah.

Penambahan BO memperbarui master, pemrosesan dataset aktif, pencocokan ulang udara dan cache analisis. Upload baru memakai master yang sama untuk BNPB dan udara. Semua KPI, matriks, Top Risk, BO Prioritas P80 dan asisten memakai daftar BO dinamis. Dua BO boleh berada di kabupaten/kota yang sama; masing-masing memperoleh catatan wilayah yang sama, sementara jumlah baris sumber tidak bertambah. Kecamatan hanya informasi profil, bukan filter risiko.

Regional BO tambahan ditandai Belum ditetapkan. Tanpa koordinat, profil tetap dihitung dan tampil di tabel, namun tidak diberi titik peta yang diperkirakan sembarang. Sertakan `data_engine.py`, `menus/profil_bo.py` dan `data/custom_branches.json` (jika sudah dibuat) ketika memindahkan project ke server. Data BNPB/udara tetap di memori sesi, terpisah dari profil persisten. Pengujian menggunakan lokasi registry sementara melalui variabel BCP_CUSTOM_BO_PATH agar tidak menambahkan profil uji ke master pengguna.


## Periode analisis bersama

Overview, Analisis Risiko dan Top Risk memiliki kartu Periode data di kanan atas. Pilih tanggal awal/akhir, kemudian Terapkan periode. Satu periode disimpan per sesi browser dan dipakai oleh ketiga menu, seluruh rincian interaktif, BO Prioritas P80, serta jawaban Asisten BCP. Perpindahan menu atau kunjungan Profil BO tidak mereset periode.

Batas tanggal mengikuti tanggal valid paling awal dan terakhir dalam file BNPB yang diunggah, bukan batas hari ini dan bukan hanya cutoff awal import. Periode awal mengikuti pilihan saat aktivasi import. Pengguna dapat mempersempit atau memperluas kembali di dalam cakupan file tanpa upload ulang karena sumber asli tetap ada di memori. Tanggal awal tidak boleh melewati tanggal akhir; tanggal kosong atau di luar cakupan ditolak. Rentang valid tanpa kejadian boleh dipilih dan tampil sebagai tidak ada catatan.

`ui_components.py` menyimpan periode dan cache kejadian seluruh file yang telah divalidasi. Pergantian periode memfilter cache dan menghitung ulang ringkasan, likelihood, normalisasi impact, risiko dan ambang P80 sesuai subset terpilih; bobot dan rumus tidak berubah. Air Karhutla tetap memakai H+0–H+7 dari file udara penuh sehingga akhir periode kejadian tidak memotong jendela udara. Import baru mereset periode analisis ke periode aktivasi yang baru; penambahan BO mempertahankan pilihan periode dan memperbarui cache master. Pilihan grafik dan jawaban asisten lama dihapus saat periode berubah. Periode import asli tetap dicatat terpisah. Sertakan `ui_components.py` saat memindahkan project.
