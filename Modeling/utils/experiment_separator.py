import pandas as pd

PARAMS = ['density', 'cutting_speed', 'feed_rate']


def separate_experiments(df: pd.DataFrame, params: list = PARAMS) -> pd.DataFrame:
    """
    Assigns an experiment_id to each row within each parameter combination.
    A new experiment starts every time depth resets to 0.

    Args:
        df:     Raw dataframe
        params: Grouping columns (default: density, cutting_speed, feed_rate)

    Returns:
        df with an added 'experiment_id' column (1-indexed per combo)
    """
    df = df.copy()
    df['experiment_id'] = df.groupby(params)['depth'].transform(
        lambda x: (x == 0).cumsum()
    )
    return df


def get_experiment_summary(df: pd.DataFrame, params: list = PARAMS) -> pd.DataFrame:
    """
    Returns a summary table of experiment counts per parameter combination.

    Args:
        df:     Dataframe with 'experiment_id' already assigned
        params: Grouping columns

    Returns:
        Summary DataFrame with experiment_count per combination
    """
    summary = (df.groupby(params)['experiment_id']
                 .max()
                 .reset_index(name='experiment_count')
                 .sort_values('experiment_count', ascending=False))
    return summary


def print_experiment_report(df: pd.DataFrame, params: list = PARAMS) -> None:
    """
    Prints a full experiment report: summary stats + per-combination detail.
    """
    summary = get_experiment_summary(df, params)

    print(f"Total unique combinations : {len(summary)}")
    print(f"Experiment count range    : {summary['experiment_count'].min()} – {summary['experiment_count'].max()}")
    print(f"Total experiments         : {summary['experiment_count'].sum()}")
    print("\n── Experiments per combination ──")
    print(summary.to_string(index=False))


def get_experiments(df: pd.DataFrame, params: list = PARAMS) -> dict:
    """
    Splits df into individual experiment DataFrames.

    Args:
        df:     Dataframe with 'experiment_id' already assigned
        params: Grouping columns

    Returns:
        A dict keyed by (density, cutting_speed, feed_rate, experiment_id)
        Each value is the DataFrame for that experiment.

    Example:
        experiments = get_experiments(df)
        exp = experiments[(0.5, 100, 0.1, 1)]
    """
    experiments = {}
    for keys, group in df.groupby(params + ['experiment_id']):
        experiments[keys] = group.reset_index(drop=True)
    return experiments