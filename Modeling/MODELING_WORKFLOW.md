# Alur Berpikir Pemodelan Cutting Force

> Dokumen ini menjelaskan **kenapa** pipeline `Modeling/main.ipynb` dibangun seperti sekarang — mulai dari temuan EDA sampai keputusan Stratified 5-Fold dan rasio split ~80:20 — bukan sekadar apa yang dikerjakan. Untuk detail hyperparameter dan riwayat eksperimen lengkap, lihat [PROGRESS_REPORT.md](../PROGRESS_REPORT.md).
>
> Catatan riwayat: versi dokumen ini pernah dibuat sebelumnya (commit `4f052ad`), tapi sempat hilang karena ter-revert (`b41097f`) sebelum sempat di-commit ulang. Isinya sekarang ditulis ulang mengikuti kondisi `main.ipynb` yang aktif saat ini (Stratified **5-Fold**, `MSELoss`, tanpa common-depth-grid interpolation).

## 1. Titik Berangkat: Apa yang Terlihat di EDA

Sebelum bicara soal split, perlu jelas dulu bentuk datanya, karena hampir semua keputusan split turun dari sini.

- **283.140 baris, tidak ada missing value, tidak ada duplikat.** Data bersih secara struktural.
- Data adalah **198 eksperimen** hasil dari **72 kombinasi** parameter mesin (`density` × `cutting_speed` × `feed_rate` = 4 × 6 × 3, full-factorial, tidak ada kombinasi yang hilang). Tiap kombinasi punya **2–3 replikasi** (54 kombinasi punya 3 replikasi, 18 kombinasi hanya punya 2).
- Satu eksperimen adalah satu lintasan `depth` dari 0 sampai maksimum, direkam sangat rapat (ribuan baris per eksperimen). `experiment_id` dideteksi dari titik `depth` kembali ke nol dalam kombinasi parameter yang sama (`separate_experiments` di `utils/experiment_separator.py`).
- Plot `depth` vs `cutting_force` pada satu eksperimen menunjukkan pola naik-turun (*squiggle*), bukan garis mulus. Artinya nilai pada satu titik tidak cukup dijelaskan oleh titik itu sendiri — perlu **konteks beberapa titik sebelumnya**. Ini alasan dasar kenapa pipeline pakai sequence model (LSTM/GRU/RNN/TCN) dengan sliding window, bukan model tabular titik-per-titik.
- Audit variance per-kombinasi menemukan sesuatu yang penting: **between-combination variance ≈ 27.622**, sedangkan **within-combination (replicate) variance rata-rata ≈ 35** dari total variance ≈ 23.608 — replikasi dalam kombinasi yang sama umumnya hanya menyumbang **~0,1%** dari variance keseluruhan. Tapi ini rata-rata; beberapa kombinasi spesifik (mis. `density=20, speed=10, feed=10`) punya `replicate_std` sampai ~23,5 — jauh di atas kombinasi lain. Artinya: **kondisi mesin (parameter) adalah sumber variasi dominan, tapi ada beberapa kondisi "sulit" dengan variasi antar-replikasi besar yang tidak dijelaskan fitur** (irreducible error lokal). Temuan ini nanti jadi alasan kenapa split *tidak boleh* dibiarkan acak murni — kalau kombinasi sulit itu kebetulan selalu jadi test atau selalu jadi train, hasil evaluasi jadi bias.
- Perbandingan `data.csv` vs `master_ml_raw.xlsx` menunjukkan korelasi row-aligned 0,9957 (axial) dan 0,9977 (cutting) — `data.csv` adalah versi yang sudah diproses/dihaluskan dari sinyal mentah, bukan sinyal mentah itu sendiri. Ini alasan kenapa `data.csv` tetap dipakai sebagai sumber utama modeling (lebih bersih), sementara raw disimpan sebagai referensi, bukan diganti.
- Ditemukan 363 baris `cutting_force` negatif (0,128%) — semuanya terjadi di `depth` kecil (< 1,4 mm), konsisten dengan noise awal pemotongan, bukan kesalahan sensor sistemik. Karena data tidak boleh dihapus/direkayasa, nilai ini dibiarkan apa adanya dan ditangani lewat pemilihan loss function saat training, bukan lewat filtering data.

**Kesimpulan dari EDA yang langsung memengaruhi desain split:**
1. Unit analisis yang benar adalah **eksperimen**, bukan baris — baris yang berdekatan dalam satu eksperimen sangat berkorelasi.
2. Ada struktur kelas alami (`density`, `cutting_speed`, `feed_rate`) dengan jumlah member per kelas yang **tidak seragam dan kadang sangat kecil** (minimum 2 replikasi per kombinasi 3-arah).
3. Beberapa kondisi jauh lebih sulit/variatif daripada kondisi lain, jadi evaluasi yang adil butuh setiap kondisi terwakili di training maupun test.

## 2. Kenapa Split di Level Eksperimen, Bukan di Level Baris

Kalau split dilakukan setelah windowing (level baris), window yang tumpang tindih dari eksperimen yang sama bisa jatuh ke train dan ke test sekaligus — modelnya secara efektif "melihat" sebagian dari sequence yang sama saat training maupun saat dievaluasi. Ini data leakage klasik untuk data sekuensial.

Solusinya: **split dilakukan di level kunci eksperimen** `(density, cutting_speed, feed_rate, experiment_id)` — jauh **sebelum** scaling dan windowing. Windowing baru dibentuk *setelah* tahu suatu eksperimen masuk ke train, val, atau test, sehingga seluruh window dari satu eksperimen selalu berada di split yang sama.

## 3. Evolusi Strategi Split (Kenapa Tidak Berhenti di Random Split Biasa)

Riwayat di `PROGRESS_REPORT.md` menunjukkan pipeline split tidak langsung sampai ke bentuk sekarang, tapi melalui beberapa iterasi yang masing-masing menjawab masalah konkret:

1. **Random split per eksperimen (awal).** Cepat dicoba, tapi audit (Update 6) menemukan sebagian test set berisi kombinasi parameter yang *tidak pernah* muncul di training pada seed tertentu, sementara di seed lain semua kombinasi sudah dikenal. Akibatnya, standard deviation antar-seed yang besar bukan murni mengukur ketidakstabilan model — sebagian besar mengukur **jenis generalisasi yang berbeda-beda** tiap kali split diacak ulang. Ini bikin hasil sulit dibandingkan secara adil.
2. **Fixed stratified split (Update 7), kira-kira 138 train / 29 val / 31 test dari 198 eksperimen** (≈ 70/15/15). Ini pendekatan single-split pertama yang mengontrol representativeness. Masalahnya: satu split hanya memberi **satu** angka test — tidak ada cara mengukur seberapa besar hasil bisa berubah kalau pembagian datanya sedikit berbeda, dan 167 dari 198 eksperimen (yang jadi train+val) tidak pernah dievaluasi sebagai test sama sekali.
3. **Stratified K-Fold Cross-Validation (Update 8 dst.).** Solusi terhadap masalah nomor 2: alih-alih satu split tetap, buat *n* fold di mana **setiap eksperimen bergiliran menjadi test tepat satu kali**. Ini menjawab dua hal sekaligus — (a) seluruh 198 eksperimen akhirnya dievaluasi sebagai test, bukan cuma 31, dan (b) ada *n* angka RMSE independen sehingga stabilitas model bisa dilihat dari mean ± std, bukan dari satu angka yang bisa kebetulan bagus/buruk.

Jadi keputusan pakai cross-validation itu sendiri adalah jawaban atas: *"satu split acak/tetap tidak cukup dipercaya untuk dataset sekecil dan seheterogen ini."*

## 4. Kenapa "Stratified", Bukan K-Fold Biasa

`density` (4 kelas), `cutting_speed` (6 kelas), dan `feed_rate` (3 kelas) menghasilkan pengaruh yang sangat tidak seragam terhadap `cutting_force` — dari EDA, mean `cutting_force` naik dari ~35 (density=10) sampai ~378 (density=25), dan dari ~78 (speed=100) sampai ~262 (speed=10). Kalau fold dibentuk dengan K-Fold polos (tanpa stratifikasi), ada risiko nyata satu fold kebetulan didominasi kombinasi "ringan" dan fold lain didominasi kombinasi "berat" — RMSE antar-fold jadi tidak sebanding, dan kita tidak tahu apakah selisih itu karena model atau karena komposisi fold yang timpang.

`StratifiedKFold` memastikan setiap fold punya proporsi kelas yang mirip, sehingga variasi RMSE antar-fold lebih mencerminkan variasi performa model, bukan variasi komposisi data.

Implementasi saat ini (`split_experiment_keys` di `main.ipynb`) menstratifikasi berdasarkan **`density` saja** (`strata = [key[0] for key in keys]`, 4 kelas) — bukan kombinasi penuh 3-arah (72 kelas) seperti versi sebelumnya. Ini bukan detail sepele — justru ini kunci kenapa jumlah fold bisa naik dari 2 ke 5 (lihat bagian 5).

## 5. Kenapa Stratified **5-Fold**, Bukan 2-Fold atau 10-Fold

Ini pertanyaan inti, dan jawabannya berubah seiring waktu — versi sebelumnya (2-fold) dan versi sekarang (5-fold) sama-sama "benar" untuk skema stratifikasi masing-masing, tapi skemanya berbeda.

**Kenapa dulu 2-fold:** Saat stratifikasi memakai kombinasi penuh `(density, cutting_speed, feed_rate)` — 72 kelas — jumlah replikasi minimum per kelas hanya **2**. Sebuah `StratifiedKFold` tidak bisa membuat lebih banyak fold daripada jumlah member kelas terkecil (kalau dipaksa, kelas dengan 2 anggota tidak bisa terwakili di 5 fold berbeda). Jadi 2-fold adalah **batas atas yang aman** untuk skema stratifikasi 72-kelas itu.

**Kenapa sekarang bisa 5-fold:** Stratifikasi diturunkan granularitasnya jadi **`density` saja** (4 kelas, masing-masing puluhan eksperimen). Dengan jumlah member per kelas yang jauh lebih besar, fold bisa dibuat lebih banyak tanpa melanggar batasan stratifikasi. 5 dipilih (bukan 10 atau lebih) karena dua pertimbangan praktis:
- **Standar umum di literatur ML** — 5-fold adalah default yang menyeimbangkan bias estimasi performa (semakin banyak fold, semakin besar train set per fold, estimasi makin representatif) dengan variance estimasi (semakin sedikit fold, makin sedikit "sudut pandang" berbeda yang diuji).
- **Biaya komputasi nyata.** Pipeline melatih 4 model (LSTM, GRU, RNN, TCN) dari nol di setiap fold, di CPU (Ryzen 7 5800U, tanpa GPU). 5-fold × 4 model = 20 proses training penuh per full run. 10-fold akan menggandakan biaya itu untuk manfaat marginal, mengingat jumlah eksperimen (198) sudah cukup besar relatif terhadap 5 fold (≈40 eksperimen test per fold — sampel test yang cukup untuk RMSE stabil).

Trade-off dari 2-fold ke 5-fold: fold sekarang **tidak lagi menjamin semua 72 kombinasi 3-arah terwakili persis merata di tiap fold** (karena stratifikasi cuma pegang `density`), tapi sebagai gantinya setiap eksperimen mendapat kesempatan jauh lebih besar untuk benar-benar **dilatih** (bukan cuma jadi test/validation) — lihat Update 18 di progress report: sebelum fold validasi diperbaiki, 5 dari 198 eksperimen (termasuk kombinasi sulit `(20,10,10,1)`) tidak pernah masuk training di fold manapun. Ini murni bug coverage split (splitter validasi memakai `random_state` yang sama di tiap outer fold), sudah diperbaiki dengan memakai **dua `StratifiedKFold` independen**: satu untuk outer test (`random_state=split_seed`), satu lagi khusus keanggotaan validasi (`random_state=split_seed + 1`), dengan validation fold dirotasi `(test_fold + 1) % n_splits` supaya val dan test tidak pernah tumpang tindih dan setiap eksperimen matematis dijamin: tepat 1× test, maksimal 1× validation, sisanya (≥3 dari 5 fold) otomatis train.

## 6. Kenapa Rasio ~80:20

Rasio 80:20 **bukan angka yang dipilih terpisah** — itu adalah konsekuensi langsung dari memilih `n_splits = 5`. Dengan 5 fold, tiap fold otomatis menyisihkan `1/5 = 20%` eksperimen sebagai outer test dan `4/5 = 80%` sisanya sebagai training pool untuk fold itu. Ini diulang 5 kali dengan test fold yang berbeda-beda, sehingga tiap eksperimen menjadi bagian dari 20% test tepat sekali dan bagian dari 80% training pool di keempat fold lainnya.

Dari sisi angka aktual (198 eksperimen, mengikuti audit di Update 18):

| Bagian | Ukuran per fold | Persentase |
|---|---:|---:|
| Outer test | ~40 eksperimen | ~20% |
| Outer training pool (train+val) | ~158 eksperimen | ~80% |
| — Inner train (dari 80% itu) | ~126 eksperimen | ~64% |
| — Inner validation (dari 80% itu) | ~32 eksperimen | ~16% |

Jadi struktur split sebenarnya dua tingkat:
1. **Outer 80:20** (training pool vs test) — ini yang biasanya dimaksud saat orang bilang "80:20 split". Test 20% ini murni untuk evaluasi akhir per fold, tidak pernah dipakai untuk fitting scaler, memilih epoch, atau tuning apa pun.
2. **Di dalam 80% itu**, dipecah lagi jadi inner train vs inner validation. Validation dipakai untuk *early stopping* dan memilih epoch terbaik (lewat `ReduceLROnPlateau` + patience) — bukan untuk mengukur performa akhir. Kalau outer test juga dipakai untuk memilih epoch/hyperparameter, angka performanya tidak lagi independen (data yang dipakai memutuskan kapan berhenti training akan "bocor" ke angka evaluasi).

Alasan proporsi ~80:20 (bukan 50:50, bukan 90:10): 20% test dari 198 eksperimen (~40) sudah cukup banyak untuk RMSE test yang stabil secara statistik, sementara 80% training pool menyisakan cukup data untuk model sequence (yang notabene butuh banyak window) benar-benar belajar polanya. Proporsi ini juga konsisten dengan konvensi umum (rule-of-thumb 80/20 di banyak pipeline ML) dan sejalan dengan percobaan fixed-split sebelumnya (Update 7, ≈70/15/15) yang juga condong ke arah training pool besar dan test/val lebih kecil.

## 7. Kenapa Bukan Hyperparameter Tuning yang Melihat Outer Test

Karena outer test cuma dipakai sekali di akhir tiap fold (setelah model selesai dilatih dan epoch terbaik sudah ditentukan dari inner validation), estimasi performanya menjaga independensi: keputusan "kapan berhenti training" tidak pernah melihat data yang dipakai untuk menilai keberhasilannya. Ini prinsip yang sama kenapa ada pemisahan outer/inner sama sekali — kalau cuma ada satu level split (train vs test), tidak ada tempat aman untuk melakukan early stopping tanpa mengintip test set.

Catatan jujur yang tetap perlu disebut: kelima outer fold *pernah* dilihat selama eksperimen tuning hyperparameter sebelumnya (Update 3–9 di progress report bereksperimen di split versi lama). Jadi secara historis, keputusan manusia (pemilihan arsitektur, learning rate, dsb.) sudah terpengaruh oleh melihat hasil test berkali-kali sepanjang project — bukan berarti pipeline saat ini membocorkan test ke training secara teknis, tapi hasil akhir sebaiknya tetap dibaca sebagai *exploratory* bukan estimasi generalisasi yang benar-benar "belum pernah dilihat".

## 8. Ringkasan Alur, dari Data Mentah sampai Evaluasi

```
data.csv (283.140 baris)
  → separate_experiments()      : deteksi 198 eksperimen dari reset depth=0
  → split_experiment_keys()     : Stratified 5-Fold (density) → per fold: 80% train-pool / 20% test
                                   dalam 80% itu → StratifiedKFold kedua (offset+1) → ~64% inner-train / ~16% val
  → Pipeline.fit_transform()    : StandardScaler, fit HANYA pada inner-train
  → experiments_to_tensor()     : windowing per eksperimen (window & stride beda per model), tanpa lintas-eksperimen
  → train()                     : MSELoss, Adam/AdamW, ReduceLROnPlateau, early stopping via inner-val
  → evaluate() / evaluate_test_experiments() : prediksi di-inverse-transform, dihitung MAE/MSE/RMSE/R² di skala asli
  → diulang untuk test_fold = 0..4, lalu diagregasi (mean ± std RMSE per model)
```

## 9. Keputusan Terkait Lain (Ringkas)

Beberapa keputusan lain yang sering muncul berdampingan dengan pembahasan split, dan sumber alasannya:

- **`experiment_id` bukan fitur model** — hanya metadata untuk split/plot. Kalau ikut jadi fitur, model bisa "menghafal" identitas eksperimen alih-alih belajar hubungan fisik antar-variabel.
- **Tidak ada penghapusan outlier/replikasi ekstrem** — dari audit variance di EDA, variasi antar-replikasi itu nyata dan valid secara fisik (bukan noise sensor), jadi menghapusnya berarti membuang informasi asli tentang seberapa reprodusibel proses pemotongan tersebut.
- **Window & stride berbeda per model** (LSTM/RNN: window 100, stride 5; GRU: window 75, stride 10; TCN: window 76, stride 10) — hasil tuning terpisah tiap arsitektur, bukan dipaksa seragam, karena tuning awal (Update 3) menunjukkan preferensi window/stride tiap arsitektur memang berbeda.
- **Scaler baru di-fit pada inner-train**, ditransform-kan ke val & test — mencegah informasi distribusi val/test bocor ke proses normalisasi.

## 10. Batasan yang Perlu Diingat Saat Membaca Hasil

- Estimasi std dari 5 fold tetap lebih baik daripada 2 fold, tapi masih bukan sampel besar — baca sebagai indikasi kestabilan, bukan interval kepercayaan yang ketat.
- Stratifikasi hanya berbasis `density` berarti proporsi `cutting_speed`/`feed_rate` antar-fold **tidak dijamin** identik, hanya cenderung mirip karena distribusinya cukup merata secara alami di tiap density.
- TCN memakai konfigurasi awal yang belum melalui tuning seluas model recurrent — perbandingan RMSE antar-model perlu mempertimbangkan ini, bukan dibaca sebagai "arsitektur A pasti lebih baik dari B".
