#!/usr/bin/env python3
"""
同步代币列表 - 从 CoinGecko 获取代币符号和全称映射
存储到数据库的 symbols 表中，用于新闻搜索时匹配
"""
import os
import sys
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import Symbol, init_database, get_session
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_coingecko_coins() -> List[Dict]:
    """从 CoinGecko 获取完整的代币列表"""
    url = "https://api.coingecko.com/api/v3/coins/list"
    
    try:
        logger.info("从 CoinGecko 获取代币列表...")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        coins = resp.json()
        logger.info(f"获取到 {len(coins)} 个代币")
        return coins
    except Exception as e:
        logger.error(f"获取 CoinGecko 代币列表失败: {e}")
        return []


def fetch_top_coins_by_market_cap(limit: int = 500) -> List[Dict]:
    """获取市值前 N 的代币（包含更多信息）"""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    
    all_coins = []
    per_page = 250
    pages = (limit + per_page - 1) // per_page
    
    for page in range(1, pages + 1):
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": False,
        }
        
        try:
            logger.info(f"获取市值排名第 {(page-1)*per_page+1}-{page*per_page} 的代币...")
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            coins = resp.json()
            all_coins.extend(coins)
            
            if len(coins) < per_page:
                break
                
            time.sleep(1)  # 避免 API 限流
            
        except Exception as e:
            logger.error(f"获取第 {page} 页失败: {e}")
            break
    
    logger.info(f"获取到 {len(all_coins)} 个市值排名代币")
    return all_coins


def sync_coins_to_db(coins: List[Dict], engine, include_all: bool = False):
    """
    同步代币列表到数据库
    
    Args:
        coins: CoinGecko 返回的代币列表
        engine: 数据库引擎
        include_all: 是否导入所有代币（约 19000 个），False 则只导入市值前 1000
    """
    # 确保 aliases 和 coingecko_id 列存在
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE symbols ADD COLUMN aliases TEXT"))
    except:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE symbols ADD COLUMN coingecko_id VARCHAR(100)"))
    except:
        pass
    
    session = get_session(engine)
    
    try:
        added = 0
        updated = 0
        
        for coin in coins:
            symbol = coin.get('symbol', '').upper()
            name = coin.get('name', '')
            coingecko_id = coin.get('id', '')
            
            if not symbol or not name:
                continue
            
            # 过滤太短或无意义的符号
            if len(symbol) < 2 or len(name) < 2:
                continue
            
            # 生成别名列表
            aliases = set()
            aliases.add(name)
            
            # 添加常见变体
            aliases.add(name.lower())
            aliases.add(name.replace(' ', ''))
            aliases.add(name.replace(' ', '-'))
            
            # 如果名称包含特殊词，添加变体
            if 'coin' in name.lower():
                aliases.add(name.lower().replace('coin', ' coin'))
            if 'token' in name.lower():
                aliases.add(name.lower().replace('token', ' token'))
            
            aliases_str = ','.join(sorted(aliases))
            
            # 查找现有记录
            existing = session.query(Symbol).filter_by(symbol=symbol).first()
            
            if existing:
                # 更新
                if not existing.name or existing.name != name:
                    existing.name = name
                if not existing.coingecko_id:
                    existing.coingecko_id = coingecko_id
                if not existing.aliases:
                    existing.aliases = aliases_str
                updated += 1
            else:
                # 新增
                new_symbol = Symbol(
                    symbol=symbol,
                    name=name,
                    coingecko_id=coingecko_id,
                    aliases=aliases_str,
                    is_active=True,
                )
                session.add(new_symbol)
                added += 1
            
            # 批量提交
            if (added + updated) % 500 == 0:
                session.commit()
                logger.info(f"进度: 新增 {added}, 更新 {updated}")
        
        session.commit()
        logger.info(f"同步完成: 新增 {added}, 更新 {updated}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"同步失败: {e}")
        raise
    finally:
        session.close()


def get_symbol_name_map(engine) -> Dict[str, List[str]]:
    """
    从数据库获取符号到名称/别名的映射
    返回格式: {'BTC': ['Bitcoin', 'bitcoin', ...], ...}
    """
    session = get_session(engine)
    
    try:
        symbols = session.query(Symbol).filter(Symbol.is_active == True).all()
        
        mapping = {}
        for sym in symbols:
            names = set()
            if sym.name:
                names.add(sym.name)
            if sym.aliases:
                names.update(sym.aliases.split(','))
            
            mapping[sym.symbol] = list(names)
        
        return mapping
    finally:
        session.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="同步代币列表到数据库")
    parser.add_argument("--top", type=int, default=1000, help="只获取市值前 N 的代币")
    parser.add_argument("--all", action="store_true", help="获取所有代币（约 19000 个）")
    args = parser.parse_args()
    
    engine = init_database()
    
    if args.all:
        # 获取所有代币（只有 symbol, name, id）
        coins = fetch_coingecko_coins()
    else:
        # 获取市值前 N 的代币（有更多信息）
        coins = fetch_top_coins_by_market_cap(args.top)
    
    if coins:
        sync_coins_to_db(coins, engine, include_all=args.all)
        
        # 显示统计
        mapping = get_symbol_name_map(engine)
        logger.info(f"\n数据库中共有 {len(mapping)} 个代币")
        logger.info("\n示例映射:")
        for sym in ['BTC', 'ETH', 'SOL', 'ZEC', 'DOGE'][:5]:
            if sym in mapping:
                logger.info(f"  {sym}: {mapping[sym][:3]}...")


if __name__ == "__main__":
    main()
