# Alur Pemodelan Cutting Force

## 1. Tujuan Pemodelan

Pemodelan bertujuan memprediksi `cutting_force` berdasarkan lima variabel input:

1. `density`
2. `cutting_speed`
3. `feed_rate`
4. `depth`
5. `axial_force`

Data berbentuk deret berurutan. Setiap kombinasi `density`, `cutting_speed`, dan `feed_rate` mempunyai beberapa pengulangan eksperimen. Urutan nilai `depth` dan `axial_force` dalam setiap eksperimen digunakan sebagai sequence untuk memprediksi `cutting_force` pada timestep terakhir suatu window.

Kolom `experiment_id` tidak digunakan sebagai fitur model. Kolom ini hanya menjadi metadata untuk memisahkan eksperimen, membuat train-validation-test split, dan memberi identitas pada plot. Hal ini mencegah model menghafal nomor eksperimen.

## 2. Gambaran Umum Pipeline

Urutan pengerjaan pada `main.ipynb` adalah:

1. Membaca dataset dan memberikan nama kolom.
2. Mendeteksi batas setiap eksperimen dari reset nilai `depth` ke nol.
3. Membentuk kunci eksperimen `(density, cutting_speed, feed_rate, experiment_id)`.
4. Membuat Stratified 2-Fold Cross-Validation pada level eksperimen.
5. Membagi bagian training setiap outer fold menjadi inner training dan validation.
6. Melatih scaler hanya menggunakan inner training.
7. Mengubah setiap eksperimen menjadi sequence window tanpa mencampur baris antar-eksperimen.
8. Melatih LSTM, GRU, RNN, dan TCN menggunakan `SmoothL1Loss`.
9. Memilih epoch terbaik menggunakan inner validation.
10. Menyimpan checkpoint dengan validation loss terbaik.
11. Mengevaluasi checkpoint terpilih pada outer test tanpa retraining.
12. Menampilkan metrik per fold, ringkasan mean dan standard deviation, serta plot outer test per eksperimen.

Secara ringkas:

`Data mentah → Pemisahan eksperimen → Outer 2-fold → Inner validation → Scaling → Windowing → Screening → Confirmation → Checkpoint terbaik → Outer-test evaluation`

## 3. Pemisahan Eksperimen

Eksperimen baru dianggap dimulai ketika nilai `depth` kembali ke nol pada kombinasi `density`, `cutting_speed`, dan `feed_rate` yang sama. Dataset menghasilkan 198 eksperimen dari 72 kombinasi kondisi.

Pemisahan ini penting karena window hanya boleh berisi urutan dari satu eksperimen. Jika bagian akhir satu eksperimen disambungkan dengan awal eksperimen lain, model akan mempelajari sequence yang sebenarnya tidak pernah terjadi.

Jumlah baris setiap eksperimen tidak selalu sama. Namun, seluruh window dari satu eksperimen selalu ditempatkan pada split yang sama. Tidak ada sebagian window dari satu eksperimen masuk training sementara window lainnya masuk validation atau test.

## 4. Mekanisme Stratified 2-Fold

### 4.1 Outer fold

Outer split menggunakan `StratifiedKFold` dengan:

| Parameter | Nilai |
|---|---:|
| Jumlah fold | 2 |
| Shuffle | Aktif |
| Split seed | 42 |
| Label stratifikasi | Kombinasi density, cutting speed, dan feed rate |

Stratifikasi memastikan setiap kombinasi kondisi terdapat pada training dan test. Karena jumlah replikasi minimum setiap kombinasi hanya dua, jumlah fold yang aman adalah dua. Menggunakan jumlah fold lebih besar akan membuat beberapa kombinasi tidak dapat dibagikan ke seluruh fold.

Pada setiap fold terdapat:

- 99 eksperimen sebagai outer training.
- 99 eksperimen sebagai outer test.
- Tidak ada eksperimen yang muncul pada kedua bagian.
- Setelah dua fold selesai, setiap eksperimen pernah menjadi outer test tepat satu kali.

Outer test hanya digunakan untuk menghitung hasil akhir fold. Data ini tidak digunakan untuk fitting scaler, training model, scheduler, early stopping, atau pemilihan best epoch.

### 4.2 Inner training dan validation

Outer training dibagi lagi menjadi inner training dan validation dengan rasio validation sekitar 15%. Hasilnya adalah:

- 84 eksperimen inner training.
- 15 eksperimen validation.

Pemilihan validation dilakukan pada level kondisi. Hanya kondisi yang mempunyai minimal dua replikasi di outer training yang dapat dipilih. Jika satu replikasi dimasukkan ke validation, minimal satu replikasi dengan kombinasi `density`, `cutting_speed`, dan `feed_rate` yang sama tetap berada di inner training.

Kondisi kandidat kemudian diseimbangkan menggunakan lima bin berdasarkan rata-rata target. Target hanya digunakan untuk menjaga distribusi validation, bukan sebagai fitur model dan bukan untuk fitting preprocessing.

Aturan ini mencegah kasus ketika validation berisi suatu kondisi tetapi inner training tidak mempunyai kondisi pembanding. Sebelum aturan ini diterapkan, 10–11 dari 15 eksperimen validation tidak mempunyai kondisi pasangan di inner training dan menyebabkan perbedaan hasil fold yang sangat besar.

### 4.3 Mengapa ada outer dan inner split?

Inner validation digunakan untuk memilih jumlah epoch terbaik. Outer test digunakan untuk mengukur performa setelah keputusan training selesai. Jika outer test ikut menentukan epoch atau hyperparameter, nilai test tidak lagi menjadi estimasi performa yang independen.

Hyperparameter dipilih secara independen di dalam setiap outer fold. Inner-validation dari outer fold lain tidak boleh menentukan candidate karena data tersebut dapat menjadi outer test pada fold yang sedang dievaluasi.

## 5. Scaling Data

Pipeline menggunakan dua `StandardScaler` terpisah:

- Input scaler untuk lima fitur input.
- Target scaler untuk `cutting_force`.

Standard scaling mengubah data menjadi skala yang kira-kira berpusat di nol dengan standard deviation satu:

`z = (x - mean_training) / standard_deviation_training`

Scaler selalu di-fit hanya pada data training untuk tahap terkait:

- Saat memilih epoch, scaler di-fit pada inner training dan hanya melakukan transform pada validation.
- Saat evaluasi outer test, scaler yang di-fit pada inner training digunakan tanpa fitting ulang.

Nilai prediksi dan target dikembalikan ke satuan aslinya sebelum MAE, MSE, dan RMSE dihitung. Dengan demikian, angka metrik dapat dibaca dalam satuan asli `cutting_force`.

## 6. Pembentukan Sequence Window

Sebelum windowing, setiap eksperimen diinterpolasi ke common depth grid dari 0 sampai 32.967 mm dengan 990 titik. Grid ini memakai step sekitar 0.03333 mm, yaitu resolusi paling rendah pada data asli. Downsampling dilakukan agar feed rate 10, 15, dan 20 mempunyai panjang serta bobot eksperimen yang sama.

Model menerima 76 timestep berurutan yang mencakup tepat sekitar 2.500 mm:

`[timestep 1, timestep 2, ..., timestep 76]`

Target sampel adalah `cutting_force` pada timestep terakhir. Bentuk tensor input adalah:

`[jumlah_window, panjang_window, jumlah_fitur]`

Jumlah fitur selalu lima. `experiment_id` tidak masuk tensor.

Stride berukuran 10 titik atau sekitar 0.333 mm. Setiap eksperimen menghasilkan tepat 92 window sehingga setiap feed rate dan eksperimen mempunyai kontribusi yang seimbang.

Seluruh model memakai grid, window, dan stride yang sama sehingga dapat berbagi tensor cache selama pemrosesan fold. Dibanding pipeline lama, jumlah window feed rate 10 turun dari 377 menjadi 92, feed rate 15 dari 245 menjadi 92, dan feed rate 20 dari 179 menjadi 92.

## 7. Model yang Digunakan

### 7.1 Recurrent Neural Network

RNN adalah bentuk dasar neural network untuk data berurutan. Model membawa hidden state dari satu timestep ke timestep berikutnya sehingga informasi masa lalu dapat memengaruhi prediksi saat ini.

Kelebihan RNN adalah strukturnya sederhana. Kekurangannya adalah kesulitan mempertahankan informasi jangka panjang akibat vanishing gradient. RNN dalam pipeline menggunakan hidden state dari layer terakhir dan menggabungkannya dengan fitur input pada timestep terakhir sebelum menghasilkan prediksi.

### 7.2 Long Short-Term Memory

LSTM merupakan pengembangan RNN yang memiliki cell state dan beberapa gate. Gate mengatur informasi mana yang perlu disimpan, dilupakan, dan digunakan sebagai output. Struktur ini membantu model mempertahankan informasi lebih panjang dibanding RNN biasa.

LSTM sesuai untuk sequence yang mempunyai hubungan jangka panjang, tetapi komputasinya lebih berat karena jumlah operasi dan parameter di setiap timestep lebih banyak. Pipeline menggunakan hidden state terakhir LSTM dan fitur input pada timestep terakhir sebagai input layer prediksi.

### 7.3 Gated Recurrent Unit

GRU juga merupakan pengembangan RNN. GRU menggunakan reset gate dan update gate untuk mengontrol aliran informasi. Strukturnya lebih sederhana daripada LSTM karena tidak memiliki cell state yang terpisah.

GRU sering mempunyai performa yang mendekati LSTM dengan waktu training lebih singkat. Pada pipeline ini, hidden state terakhir GRU digabungkan dengan fitur timestep terakhir sebelum masuk ke fully connected layer.

### 7.4 Temporal Convolutional Network

TCN memproses sequence menggunakan convolution satu dimensi. Berbeda dari recurrent model yang membaca timestep secara berurutan, convolution dapat menghitung beberapa bagian sequence secara paralel sehingga berpotensi lebih cepat.

TCN menggunakan causal convolution. Prediksi pada suatu timestep hanya boleh menggunakan timestep saat ini dan masa lalu, bukan data masa depan. Dilated convolution memperlebar jangkauan model tanpa harus menggunakan kernel yang sangat besar.

TCN mempunyai lima residual block dengan dilation `1, 2, 4, 8, 16`. Receptive field-nya adalah 125 timestep sehingga mencakup seluruh window berukuran 100. Residual connection membantu gradient mengalir melalui network yang lebih dalam. Representasi timestep terakhir digabungkan dengan fitur input terakhir sebelum menghasilkan prediksi.

## 8. Hyperparameter Setiap Model

| Hyperparameter | LSTM | GRU | RNN | TCN |
|---|---:|---:|---:|---:|
| Epoch maksimum | 30 | 30 | 30 | 30 |
| Window size | 76 | 76 | 76 | 76 |
| Stride | 10 | 10 | 10 | 10 |
| Hidden size | 128 | 128 | 128 | - |
| Jumlah recurrent layer | 1 | 2 | 3 | - |
| TCN channels | - | - | - | 64, 64, 64, 64, 64 |
| Kernel size | - | - | - | 3 |
| Batch size | 64 | 256 | 128 | 256 |
| Learning rate | 0.001 | 0.0015 | 0.001 | 0.001 |
| Dropout | 0.0 | 0.3 | 0.0 | 0.2 |
| Weight decay | 0.0 | 0.0001 | 0.0 | 0.0001 |
| Gradient clipping | Tidak | 1.0 | Tidak | 1.0 |
| Optimizer | Adam | AdamW | Adam | AdamW |

Konfigurasi global yang digunakan seluruh model adalah:

| Parameter global | Nilai |
|---|---:|
| Outer fold | 2 |
| Validation ratio | 0.15 |
| Split seed | 42 |
| Training seed | 42 |
| Training loss | SmoothL1Loss |
| SmoothL1 beta | 1.0 |
| Common depth points | 990 |
| Physical window | 2.500 mm |
| Physical stride | 0.333 mm |
| Early-stopping patience | 5 epoch |
| Minimum improvement | 0.0 |
| Scheduler factor | 0.5 |
| Scheduler patience | 2 epoch |
| CPU thread | 8 |
| Inter-op thread | 2 |

Konfigurasi TCN merupakan konfigurasi awal dan belum melalui tuning seluas model recurrent. Karena itu, perbandingan akhir perlu menyebutkan bahwa tingkat tuning setiap arsitektur belum sepenuhnya sama.

## 9. Arti Hyperparameter

### Epoch

Satu epoch berarti model telah memproses seluruh sampel training satu kali. Epoch maksimum 30 tidak berarti semua model selalu berjalan tepat 30 epoch. Early stopping dapat menghentikan training lebih awal jika validation loss tidak membaik.

Epoch terlalu sedikit menyebabkan underfitting karena model belum sempat mempelajari pola. Epoch terlalu banyak dapat menyebabkan overfitting karena model semakin menyesuaikan diri dengan training tetapi memburuk pada data baru.

### Window size

Window size adalah jumlah timestep masa lalu yang diberikan kepada model untuk membuat satu prediksi. Window 100 memberikan konteks lebih panjang daripada window 75, tetapi memerlukan komputasi dan memori lebih besar.

### Stride

Stride adalah jarak perpindahan window. Stride 5 menghasilkan window yang lebih rapat dan lebih banyak daripada stride 10. Stride kecil dapat menangkap perubahan secara lebih detail, tetapi memperpanjang waktu training karena jumlah sampel meningkat.

### Hidden size

Hidden size adalah jumlah unit pada hidden state RNN, LSTM, atau GRU. Hidden size lebih besar meningkatkan kapasitas model untuk menyimpan informasi sequence. Namun, jumlah parameter, waktu training, penggunaan memori, dan risiko overfitting juga meningkat.

### Jumlah layer

Jumlah layer menentukan berapa recurrent layer yang ditumpuk. Layer awal mempelajari pola sequence dasar, sedangkan layer lebih tinggi dapat mempelajari representasi yang lebih kompleks. Model yang terlalu dalam tidak selalu lebih baik, terutama ketika jumlah eksperimen terbatas.

### Channels pada TCN

Channels mempunyai fungsi yang mirip dengan hidden size, tetapi digunakan pada convolution. Angka `[64, 64, 64, 64, 64]` berarti terdapat lima residual block dengan 64 output channel pada setiap block.

### Kernel size

Kernel size menentukan berapa titik berdekatan yang diperiksa convolution dalam satu operasi. Kernel 3 melihat tiga posisi lokal. Dengan dilation yang meningkat, TCN tetap dapat menjangkau sequence yang panjang.

### Dilation

Dilation menentukan jarak antar-elemen yang dibaca kernel. Dilation `1, 2, 4, 8, 16` membuat block yang lebih dalam melihat konteks semakin luas tanpa menambah ukuran kernel secara berlebihan.

### Batch size

Batch size adalah jumlah sampel yang diproses sebelum optimizer memperbarui bobot. Batch besar biasanya lebih efisien secara komputasi, tetapi memerlukan memori lebih banyak dan menghasilkan gradient yang lebih halus. Batch kecil menghasilkan pembaruan yang lebih sering dan lebih noisy.

### Learning rate

Learning rate mengontrol besar perubahan bobot pada setiap langkah optimizer. Nilai terlalu besar dapat membuat training tidak stabil atau melewati solusi yang baik. Nilai terlalu kecil membuat training sangat lambat.

### Dropout

Dropout menonaktifkan sebagian unit secara acak selama training. Contohnya, dropout 0.3 berarti sekitar 30% aktivasi terkait dinonaktifkan pada satu langkah training. Tujuannya mengurangi ketergantungan model pada unit tertentu dan menekan overfitting. Dropout tidak aktif ketika model melakukan validation atau prediction.

### Weight decay

Weight decay memberikan penalti pada bobot yang terlalu besar. Nilai `0.0001` merupakan regularisasi ringan. Dalam pipeline ini, konfigurasi dengan weight decay menggunakan AdamW, sedangkan konfigurasi tanpa weight decay menggunakan Adam.

### Gradient clipping

Gradient clipping membatasi besar gradient sebelum optimizer memperbarui bobot. Nilai 1.0 berarti norm gradient dibatasi maksimal 1.0. Teknik ini membantu mencegah exploding gradient dan membuat training lebih stabil.

### Training seed

Training seed mengontrol inisialisasi bobot dan urutan shuffle batch. Seed 42 membuat eksperimen dapat direproduksi. Seed ini dipisahkan secara konsep dari split seed agar sumber variasi pembagian data dan training dapat dibedakan.

### Patience dan minimum improvement

Patience menentukan berapa epoch tanpa perbaikan yang masih ditoleransi. Scheduler mempunyai patience dua epoch, sedangkan early stopping mempunyai patience lima epoch. Minimum improvement bernilai 0.0, sehingga validation loss yang lebih kecil dalam jumlah berapa pun dianggap sebagai hasil terbaik baru.

### SmoothL1 beta

Beta menentukan batas perpindahan SmoothL1Loss dari perilaku kuadratik menjadi linear. Dengan beta 1.0 pada target yang telah distandardisasi, error kecil diperlakukan secara halus sementara pengaruh error yang sangat besar dibatasi.

### Jumlah thread

Jumlah thread menentukan banyaknya thread CPU yang dapat digunakan PyTorch. Nilai delapan disesuaikan dengan delapan core Ryzen 7 5800U. Inter-op thread mengatur paralelisme antar-operasi PyTorch dan ditetapkan dua agar overhead tidak terlalu besar.

## 10. Loss, Optimizer, Scheduler, dan Early Stopping

### SmoothL1Loss

Semua model dilatih menggunakan `SmoothL1Loss` dengan beta 1.0. Loss ini bersifat kuadratik untuk error kecil dan lebih mendekati linear untuk error besar. Dibanding MSE, SmoothL1Loss mengurangi dominasi observasi ekstrem tanpa menghapus observasi tersebut.

Data outlier atau variasi antar-replikasi tetap berada dalam training dan evaluasi. SmoothL1Loss hanya mengubah seberapa kuat error ekstrem memengaruhi pembaruan bobot.

### Validation MSE

Walaupun training menggunakan SmoothL1Loss, scheduler dan early stopping memantau MSE validation. Hal ini menjaga pemilihan epoch tetap selaras dengan RMSE, karena RMSE merupakan akar dari MSE.

### Adam dan AdamW

Adam menyesuaikan learning rate setiap parameter berdasarkan riwayat gradient. AdamW mempunyai mekanisme serupa, tetapi menerapkan weight decay secara terpisah dan lebih tepat untuk regularisasi bobot.

### Learning-rate scheduler

`ReduceLROnPlateau` menurunkan learning rate menjadi 50% dari nilai sebelumnya jika validation loss tidak membaik selama dua epoch. Learning rate yang lebih kecil membantu model melakukan penyesuaian lebih halus ketika training mulai stagnan.

### Early stopping

Early stopping mempunyai patience lima epoch. Jika validation loss tidak menghasilkan nilai terbaik baru selama lima epoch berturut-turut, training dihentikan. Bobot dari epoch dengan validation loss terbaik dipulihkan.

Checkpoint dari epoch dengan validation loss terbaik disimpan dan langsung digunakan untuk outer test. Model tidak dilatih ulang dari nol.

## 11. Fast Successive Tuning

Preset aktif menggunakan candidate hasil screening sebelumnya agar training tidak diulang. Full screening tetap tersedia dengan mengubah `reuse_prescreened_candidates = False`.

### Screening

Jika diaktifkan, screening menguji 18 kandidat secara terpisah di dalam setiap outer fold menggunakan inner validation fold tersebut, stride 20, maksimum 10 epoch, dan early-stopping patience 2.

Preset aktif memakai dua kandidat per model: `lstm_hidden_96` dan `lstm_base`; `gru_dropout_04` dan `gru_dropout_02`; `rnn_base` dan `rnn_hidden_96`; serta `tcn_batch_128` dan `tcn_64x5_lowdrop`.

Jika full screening dijalankan, hasil setiap kandidat disimpan ke `tuning_results_depth_balanced/fast_screening.csv`. Pada preset aktif, tahap ini dilewati.

### Confirmation

Dua kandidat preset setiap model diuji pada masing-masing inner split, stride asli, maksimum 20 epoch, scheduler, dan patience 5. Totalnya 16 training runs. Candidate dengan Validation RMSE terendah dipilih secara independen untuk setiap model-fold.

Hasil disimpan bertahap dalam `confirmation_results.csv`, `confirmation_summary.csv`, dan `selected_candidates.csv`. Bobot terbaik disimpan dalam `tuning_results_depth_balanced/checkpoints/fold_n`. Outer test tetap tidak digunakan pada screening maupun confirmation.

### Tuned final evaluation

Checkpoint terbaik dari confirmation dimuat kembali tanpa retraining. Scaler di-fit hanya pada inner training yang menghasilkan checkpoint tersebut, lalu model dievaluasi satu kali pada outer test.

`run_baseline_evaluation = False` mencegah pipeline baseline lama ikut berjalan. Kodenya tetap dipertahankan dan dapat diaktifkan kembali. `run_fast_tuning = True` serta `run_tuned_evaluation = True` menjalankan screening, confirmation, dan final evaluation secara berurutan.

## 12. Proses Evaluasi

Setiap model dievaluasi satu kali pada setiap outer fold. Screening dan confirmation hanya memakai inner training serta validation dari outer fold terkait. Checkpoint confirmation terpilih kemudian memprediksi outer test tanpa retraining. Prediksi dikembalikan ke skala asli sebelum metrik dihitung.

### MAE

Mean Absolute Error adalah rata-rata nilai absolut selisih prediksi dan aktual:

`MAE = mean(|aktual - prediksi|)`

MAE mudah dipahami dan tidak memberikan penalti kuadrat pada error besar.

### MSE

Mean Squared Error adalah rata-rata kuadrat error:

`MSE = mean((aktual - prediksi)²)`

MSE sangat sensitif terhadap error besar.

### RMSE

Root Mean Squared Error adalah akar MSE:

`RMSE = sqrt(MSE)`

RMSE kembali ke satuan target asli dan tetap memberi penalti lebih besar pada kesalahan ekstrem. Model utama biasanya dipilih berdasarkan rata-rata RMSE paling rendah, kemudian standard deviation digunakan untuk menilai kestabilannya.

### Mean dan standard deviation

Mean menunjukkan rata-rata performa dua outer fold. Standard deviation menunjukkan seberapa besar hasil berubah antarfold. Nilai mean rendah dan standard deviation kecil menunjukkan model yang akurat serta relatif konsisten.

Karena hanya terdapat dua fold, estimasi standard deviation masih terbatas. Nilainya harus dibaca sebagai indikasi awal kestabilan, bukan ukuran ketidakpastian yang sangat kuat.

## 13. Output yang Dihasilkan

### Fold metrics

`fold_metrics` berisi satu baris untuk setiap kombinasi model dan fold dengan kolom:

- `Model`
- `Fold`
- `Training Seed`
- `MAE`
- `MSE`
- `RMSE`
- `Validation RMSE`
- `Best Epoch`
- `Training Loss`

Dengan empat model dan dua fold, tabel seharusnya mempunyai delapan baris.

### Evaluation summary

`evaluation_summary` menggabungkan hasil dua fold dan menampilkan:

- `MAE_Mean`
- `MAE_Std`
- `RMSE_Mean`
- `RMSE_Std`

Tabel otomatis diurutkan dari `RMSE_Mean` paling kecil. Urutan ini sudah berfungsi sebagai ranking model, sehingga tabel ranking tambahan tidak diperlukan.

### Fold assignments

`fold_assignments` menyimpan daftar eksperimen beserta fold dan perannya:

- `Inner Train`
- `Validation`
- `Test`

Tabel ini dapat digunakan untuk mengaudit bahwa tidak ada eksperimen yang tumpang tindih.

### Outer-test plot per eksperimen

Jika `save_evaluation_plots = True`, notebook membuat kurva actual-predicted menggunakan final model pada outer test. Setiap eksperimen menjadi outer test tepat satu kali, sehingga satu full run menghasilkan 198 plot per model atau 792 plot untuk empat model.

Jika diaktifkan kembali, plot disimpan di `evaluation_plots_depth_balanced/fold_<nomor>/<model>/`. Judul setiap gambar memuat fold, model, kunci eksperimen, dan RMSE eksperimen tersebut. `experiment_id` hanya digunakan sebagai identitas file dan tidak menjadi input prediksi.

Karena plot sedang dinonaktifkan, hasil per eksperimen disimpan dalam `tuning_results_depth_balanced/tuned_per_experiment_metrics.csv`. File ini berisi MAE, MSE, RMSE, jumlah window, kondisi pemesinan, fold, dan model.

Notebook menyimpan checkpoint confirmation ke `tuning_results_depth_balanced/checkpoints`. Output lainnya adalah tabel confirmation, candidate terpilih, fold metrics, summary, dan per-experiment metrics.

## 14. Interpretasi Hasil

Model tidak boleh dipilih hanya karena menghasilkan satu fold terbaik. Pemilihan dilakukan menggunakan `RMSE_Mean` seluruh fold. Jika dua model mempunyai mean yang sangat dekat, model dengan standard deviation lebih kecil, arsitektur lebih sederhana, atau waktu training lebih singkat dapat dipertimbangkan.

Perbedaan Fold 1 dan Fold 2 tidak otomatis berarti kode salah. Setiap fold berisi replikasi yang berbeda dan beberapa replikasi memiliki target berbeda walaupun inputnya sangat mirip. Namun, selisih yang sangat besar tetap perlu diperiksa melalui outer-test plots, fold assignments, distribusi target, dan error per eksperimen.

Variasi antar-replikasi yang tidak dijelaskan oleh fitur merupakan irreducible error. Model deterministik cenderung mengambil nilai tengah ketika beberapa input hampir sama mempunyai target berbeda. Kondisi tersebut tidak dapat diselesaikan sepenuhnya hanya dengan menambah kapasitas model.

## 15. Perlindungan terhadap Data Leakage

Pipeline menerapkan perlindungan berikut:

1. Split dilakukan sebelum scaling dan windowing.
2. Seluruh bagian satu eksperimen selalu berada pada split yang sama.
3. Scaler hanya di-fit pada training.
4. Validation hanya digunakan untuk scheduler, early stopping, dan best epoch.
5. Outer test hanya digunakan setelah keputusan training selesai.
6. `experiment_id` tidak menjadi fitur.
7. Tensor cache tidak dibagikan antar-fold.
8. Candidate dipilih per outer fold sehingga tidak dipengaruhi inner-validation outer fold lainnya.
9. Checkpoint hanya melihat inner training saat pembaruan bobot; validation hanya menentukan penghentian dan pemilihan checkpoint.

Penggunaan target untuk stratifikasi validation diperbolehkan karena hanya bertujuan menyeimbangkan distribusi split. Nilai target validation tidak digunakan untuk fitting scaler training atau memperbarui bobot model.

Terdapat satu catatan metodologis: hasil kedua outer fold pernah diperiksa dalam eksperimen tuning sebelumnya. Oleh karena itu, outer test tersebut tidak lagi sepenuhnya independen secara historis, walaupun implementasi pipeline saat ini tidak membocorkan test ke training. Hasil lama sebaiknya dinyatakan sebagai exploratory tuning. Evaluasi yang benar-benar independen memerlukan data baru atau prosedur nested hyperparameter tuning yang ditentukan sebelum outer-test result diperiksa.

## 16. Cara Menjalankan

1. Aktifkan virtual environment proyek.
2. Buka `Modeling/main.ipynb`.
3. Jalankan seluruh cell secara berurutan dari atas.
4. Pastikan laporan menunjukkan 198 eksperimen dan 72 kombinasi.
5. Pastikan log common depth menunjukkan 990 titik, window 76, stride 10, dan 92 window per eksperimen.
6. Tunggu hingga 16 confirmation runs selesai.
7. Periksa `tuning_results_depth_balanced/tuned_fold_metrics.csv`, `tuned_summary.csv`, dan `tuned_per_experiment_metrics.csv`.
8. Catat konfigurasi serta hasil final sebelum melakukan perubahan hyperparameter berikutnya.

Training penuh menjalankan screening dan confirmation secara terpisah pada setiap outer fold. Final evaluation hanya memuat checkpoint sehingga tidak ada retraining tambahan. Proses dapat dilanjutkan dari CSV dan checkpoint jika notebook berhenti.
