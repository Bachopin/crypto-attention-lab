import pandas as pd
from src.config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.features.news_features import (
    source_weight,
    sentiment_score,
    relevance_flag,
    extract_tags,
)


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

    # 计算新闻级特征
    df['source_weight'] = df['source'].apply(lambda s: source_weight(str(s))) if 'source' in df.columns else 0.5
    df['sentiment_score'] = df['title'].apply(lambda t: sentiment_score(str(t))) if 'title' in df.columns else 0.0
    df['relevance'] = df['title'].apply(lambda t: relevance_flag(str(t), symbol="ZEC")) if 'title' in df.columns else 'related'
    df['tags'] = df['title'].apply(lambda t: ','.join(extract_tags(str(t)))) if 'title' in df.columns else ''

    # relevance 权重: direct=1.0, related=0.5
    rel_w = df['relevance'].map({'direct': 1.0, 'related': 0.5}).fillna(0.5)
    weighted = df['source_weight'] * rel_w
    # bullish/bearish attention（情绪分解）
    df['bullish_component'] = (df['sentiment_score'].clip(lower=0)) * weighted
    df['bearish_component'] = (-df['sentiment_score'].clip(upper=0)) * weighted

    # 聚合：news_count 与扩展特征
    grp = df.set_index('datetime').resample(freq).agg({
        'title': 'count',
        'source_weight': 'sum',
        'bullish_component': 'sum',
        'bearish_component': 'sum',
    }).rename(columns={'title': 'news_count', 'source_weight': 'weighted_attention',
                       'bullish_component': 'bullish_attention', 'bearish_component': 'bearish_attention'})

    grp = grp.fillna(0).reset_index()

    # Min-Max 归一化到 [0,100]
    mn = grp['news_count'].min()
    mx = grp['news_count'].max()
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        grp['attention_score'] = 0.0
    else:
        grp['attention_score'] = (grp['news_count'] - mn) / (mx - mn) * 100.0

    # 事件强度：当日是否出现高权重来源 + 强情绪 + 明确主题
    # 为 intensity 需要按日评估，借助原 df 逐日判断
    df_day = df.copy()
    df_day['date'] = df_day['datetime'].dt.floor(freq)
    def compute_intensity(day_df: pd.DataFrame) -> int:
        has_high_source = (day_df['source_weight'] >= 0.9).any()
        strong_sent = (day_df['sentiment_score'].abs() >= 0.6).any()
        has_tag = day_df['tags'].astype(str).str.len().gt(0).any()
        return int(has_high_source and strong_sent and has_tag)
    intensity = df_day.groupby('date').apply(compute_intensity).rename('event_intensity').reset_index()
    grp = grp.reset_index()
    grp = grp.merge(intensity, left_on='datetime', right_on='date', how='left').drop(columns=['date'])
    grp['event_intensity'] = grp['event_intensity'].fillna(0).astype(int)

    # 输出新增字段
    out = grp[['datetime', 'attention_score', 'news_count', 'weighted_attention', 'bullish_attention', 'bearish_attention', 'event_intensity']]

    output_file = PROCESSED_DATA_DIR / "attention_features_zec.csv"
    out.to_csv(output_file, index=False)
    print(f"Saved attention features to {output_file}")
    return output_file


if __name__ == "__main__":
    process_attention_features()
