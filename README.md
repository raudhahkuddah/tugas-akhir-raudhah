# Modeling and Prediction of Bone Drilling Torque

This repository contains the code and supporting files used in the research:

**Modeling and Prediction of Bone Drilling Torque: A Comparison of Sequential Deep Learning and Conventional Machine Learning**

## 1. Research Overview

This research focuses on modeling and predicting torque during bone drilling using sequential deep learning and conventional machine learning approaches.

Four sequential deep learning architectures are implemented:

- Recurrent Neural Network (RNN)
- Long Short-Term Memory (LSTM)
- Gated Recurrent Unit (GRU)
- Temporal Convolutional Network (TCN)

Conventional machine learning models are also implemented as baselines for comparison.

The models use drilling process parameters and sequential information along the drilling depth to predict `cutting_force` as the target variable for torque modeling.

## 2. Dataset

The dataset contains:

- 283,140 data points
- 198 drilling experiments
- 72 experimental condition combinations

The experimental conditions consist of:

| Parameter | Values |
|---|---|
| Density | 10, 15, 20, 25 PCF |
| Cutting Speed | 10, 16, 25, 40, 63, 100 RPM |
| Feed Rate | 10, 15, 20 mm/min |

The variables used in the modeling are:

| Variable | Description |
|---|---|
| `density` | Material density |
| `cutting_speed` | Cutting speed |
| `feed_rate` | Feed rate |
| `depth` | Drilling depth |
| `axial_force` | Axial force |
| `cutting_force` | Target variable |

The `cutting_force` variable is used as the target variable for torque modeling.

The main processed dataset is located in:

```text
data/data.csv
```

Additional raw data are provided in the `data/` directory.

## 3. Repository Structure

```text
tugas-akhir-raudhah/
│
├── data/
│   ├── data.csv
│   └── master_ml_raw.xlsx
│
├── EDA/
│
├── Modeling/
│   ├── utils/
│   ├── validation_plots/
│   ├── validation_plots_raw/
│   ├── depth_extrapolation.ipynb
│   ├── linear_baseline.ipynb
│   ├── main_raw.ipynb
│   ├── main.ipynb
│   
│
├── .gitattributes
├── .gitignore
└── README.md
```

### Directory and File Description

#### `data/`

Contains the datasets used in the research.

- `data.csv` — main processed dataset used for modeling.
- `master_ml_raw.xlsx` — raw dataset used for the raw-data modeling comparison.

#### `EDA/`

Contains files related to exploratory data analysis and examination of the dataset.

#### `Modeling/`

Contains the main modeling, evaluation, and visualization files.

- `main.ipynb` — main sequential deep learning modeling workflow.
- `main_raw.ipynb` — sequential deep learning modeling workflow using the raw dataset.
- `linear_baseline.ipynb` — conventional machine learning baseline using Linear Regression and HistGradientBoostingRegressor.
- `depth_extrapolation.ipynb` — depth extrapolation experiment comparing the implemented models.
- `utils/` — utility scripts used in the modeling workflow.
- `validation_plots/` — prediction visualization outputs for the processed dataset.
- `validation_plots_raw/` — prediction visualization outputs for the raw dataset.

## 4. Methodology

The main modeling workflow consists of the following steps:

1. Load the dataset.
2. Separate the dataset into individual experiments.
3. Split the experiments using experiment-level cross-validation.
4. Apply data scaling.
5. Construct sequential input data using sliding windows.
6. Train the sequential deep learning models.
7. Evaluate model performance on the test experiments.
8. Generate prediction visualizations.

Drilling depth is used as the sequence axis.

## 5. Sequential Deep Learning Models

Four sequential deep learning architectures are implemented.

### Recurrent Neural Network (RNN)

An RNN is used to model sequential relationships within the drilling data.

### Long Short-Term Memory (LSTM)

An LSTM is used to model sequential information using recurrent memory mechanisms.

### Gated Recurrent Unit (GRU)

A GRU is implemented as a recurrent architecture for sequential modeling.

### Temporal Convolutional Network (TCN)

A TCN is used to model sequential information using causal and dilated convolutions.

The detailed model configurations and hyperparameters are described in the research report and modeling workflow documentation.

## 6. Conventional Machine Learning

Conventional machine learning approaches are implemented as baselines for comparison with the sequential deep learning models.

The implemented conventional machine learning models are:

- Linear Regression
- HistGradientBoostingRegressor

These models are evaluated in the interpolation experiment and are also included in the depth extrapolation experiment.

## 7. Data Splitting

The main sequential deep learning models use 5-fold cross-validation at the experiment level.

Each experiment is treated as a unit during data splitting to prevent data from the same experiment from being distributed across different folds.

The main configuration is:

| Parameter | Value |
|---|---|
| Number of folds | 5 |
| Number of experiments | 198 |
| Split seed | 42 |
| Training seed | 42 |
| Unit of splitting | Experiment |

## 8. Evaluation Metrics

Model performance is evaluated using the following metrics:

- Mean Absolute Error (MAE)
- Mean Squared Error (MSE)
- Root Mean Squared Error (RMSE)
- Coefficient of Determination (R²)

Prediction visualizations are also generated to compare the actual and predicted values for the test experiments.

## 9. Modeling Experiments

The repository contains several modeling experiments.

### 9.1 Sequential Deep Learning

The main experiment compares four sequential deep learning architectures:

- RNN
- LSTM
- GRU
- TCN

The models use sequential drilling data to predict `cutting_force`.

### 9.2 Raw Data Comparison

The `main_raw.ipynb` notebook is used to evaluate the sequential deep learning models using the raw dataset.

The results are compared with those obtained from the processed dataset.

### 9.3 Conventional Machine Learning Baseline

The `linear_baseline.ipynb` notebook contains the conventional machine learning baseline experiment using:

- Linear Regression
- HistGradientBoostingRegressor

These models provide a comparison with the sequential deep learning approaches under the interpolation experiment.

### 9.4 Depth Extrapolation

The `depth_extrapolation.ipynb` notebook evaluates model performance for prediction at drilling depths beyond the training depth range.

This experiment compares the sequential deep learning models with the conventional machine learning baselines.

## 10. Results

The repository contains the code and visualization outputs used to evaluate the implemented models.

The research includes comparisons between:

- RNN, LSTM, GRU, and TCN
- Processed and raw datasets
- Sequential deep learning and conventional machine learning
- Interpolation and depth extrapolation

The detailed numerical results and analysis are presented in the accompanying research report.

Prediction visualization outputs are available in:

```text
Modeling/validation_plots/
Modeling/validation_plots_raw/
```

## 11. Requirements

The code was developed using Python 3.11.

The main dependencies used in the modeling workflow include:

- NumPy 2.4.4
- Pandas 3.0.2
- Matplotlib 3.10.8
- Seaborn 0.13.2
- Scikit-learn 1.8.0
- PyTorch 2.11.0 (CPU)

The complete dependency list is provided in:

```text
requirements.txt
```

Install the dependencies using:

```bash
pip install -r requirements.txt
```

## 12. Running the Code

To run the modeling workflow:

1. Clone this repository.
2. Install the required dependencies.
3. Ensure that the required dataset is available in the `data/` directory.
4. Open the desired notebook in the `Modeling/` directory.
5. Run the notebook cells sequentially.

The main notebooks are:

```text
Modeling/main.ipynb
Modeling/main_raw.ipynb
Modeling/linear_baseline.ipynb
Modeling/depth_extrapolation.ipynb
```


## 13. Author

**Raudhah Yahya Kuddah - 13122003**

Institut Teknologi Bandung  
Fakultas Teknik Mesin dan Dirgantara
