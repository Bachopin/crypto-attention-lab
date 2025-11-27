import pandas as pd
from src.config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR


def process_attention_features(freq: str = 'D'):
    """
    读取原始新闻数据（优先 attention_zec_news.csv，退回 attention_zec_mock.csv），
    按天/小时聚合，计算 news_count 和 0-100 的 attention_score（min-max）。
    保存到 data/processed/attention_features_zec.csv，至少包含列：datetime, attention_score。
    """
    raw_news = RAW_DATA_DIR / "attention_zec_news.csv"
    if not raw_news.exists():
        raw_news = RAW_DATA_DIR / "attention_zec_mock.csv"

    if not raw_news.exists():
        print(f"Raw news file not found: {raw_news}")
        return None

    print("Processing attention features from:", raw_news)
    df = pd.read_csv(raw_news)
    if 'datetime' not in df.columns:
        print("Invalid news file format: missing 'datetime'")
        return None

    df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')
    df = df.dropna(subset=['datetime'])

    # 聚合：news_count
    grp = df.set_index('datetime').resample(freq).agg({
        'title': 'count'
    }).rename(columns={'title': 'news_count'})

    grp = grp.fillna(0).reset_index()

    # Min-Max 归一化到 [0,100]
    mn = grp['news_count'].min()
    mx = grp['news_count'].max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        grp['attention_score'] = 0.0
    else:
        grp['attention_score'] = (grp['news_count'] - mn) / (mx - mn) * 100.0

    # 输出仅保留核心字段 + news_count（便于调试）
    out = grp[['datetime', 'attention_score', 'news_count']]

    output_file = PROCESSED_DATA_DIR / "attention_features_zec.csv"
    out.to_csv(output_file, index=False)
    print(f"Saved attention features to {output_file}")
    return output_file


if __name__ == "__main__":
    process_attention_features()
