"""
技术面分析器
提供均线/MACD/RSI/量价等技术指标分析
"""
import akshare as ak
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timedelta
import time

class TechnicalAnalyzer:
    """技术面分析器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300
        self.last_request_time = 0
        self.request_delay = 0.5
    
    def analyze(self, code: str) -> Optional[Dict]:
        """
        分析股票技术面
        
        Args:
            code: 股票代码 (如 "600000.SH")
            
        Returns:
            技术面分析结果字典
        """
        try:
            # 获取历史K线数据
            df = self._get_kline_data(code)
            
            if df is None or len(df) < 60:  # 至少需要60天数据
                return None
            
            # 计算各项指标
            trend = self._analyze_trend(df)
            indicators = self._calculate_indicators(df)
            volume = self._analyze_volume(df)
            key_levels = self._find_key_levels(df)
            
            return {
                'trend': trend,
                'indicators': indicators,
                'volume': volume,
                'key_levels': key_levels,
                'summary': self._generate_summary(trend, indicators, volume)
            }
            
        except Exception as e:
            print(f"⚠️ 技术面分析失败 {code}: {e}")
            return None
    
    def _get_kline_data(self, code: str) -> Optional[pd.DataFrame]:
        """获取K线数据（带缓存和重试）"""
        # 检查缓存
        cache_key = f"kline_{code}"
        if cache_key in self.cache:
            cache_time, cached_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return cached_data
        
        # 请求限流
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        
        # 重试3次
        for attempt in range(3):
            try:
                simple_code = code.split('.')[0]
                market = 'sh' if code.endswith('.SH') else 'sz'
                symbol = f"{market}{simple_code}"
                
                # 获取最近90天数据
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
                
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"  # 前复权
                )
                
                if df.empty:
                    return None
                
                # 重命名列以便使用
                df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'turnover', 'amplitude', 'change_pct', 'change_amount', 'turnover_rate']
                
                # 缓存结果
                self.cache[cache_key] = (time.time(), df)
                self.last_request_time = time.time()
                
                return df
                
            except Exception as e:
                if attempt < 2:
                    time.sleep(1)
                    continue
                else:
                    return None
        
        return None
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """分析趋势"""
        # 计算均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        latest = df.iloc[-1]
        current_price = latest['close']
        ma5 = latest['ma5']
        ma20 = latest['ma20']
        ma60 = latest['ma60']
        
        # 判断趋势
        if ma5 > ma20 > ma60:
            direction = 'up'
            strength = 'strong'
            ma_align = 'bullish'
        elif ma5 < ma20 < ma60:
            direction = 'down'
            strength = 'strong'
            ma_align = 'bearish'
        elif ma5 > ma20:
            direction = 'up'
            strength = 'weak'
            ma_align = 'neutral'
        elif ma5 < ma20:
            direction = 'down'
            strength = 'weak'
            ma_align = 'neutral'
        else:
            direction = 'sideways'
            strength = 'neutral'
            ma_align = 'neutral'
        
        return {
            'direction': direction,  # up/down/sideways
            'strength': strength,  # strong/weak/neutral
            'ma5': round(ma5, 2) if not pd.isna(ma5) else 0,
            'ma20': round(ma20, 2) if not pd.isna(ma20) else 0,
            'ma60': round(ma60, 2) if not pd.isna(ma60) else 0,
            'ma_align': ma_align,  # bullish/bearish/neutral
            'current_price': round(current_price, 2)
        }
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        # 计算MACD
        macd_data = self._calculate_macd(df)
        
        # 计算RSI
        rsi = self._calculate_rsi(df)
        
        return {
            'macd': macd_data,
            'rsi': rsi
        }
    
    def _calculate_macd(self, df: pd.DataFrame) -> Dict:
        """计算MACD指标"""
        try:
            # 计算EMA
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            
            # 计算DIF和DEA
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd = (dif - dea) * 2
            
            latest_dif = dif.iloc[-1]
            latest_dea = dea.iloc[-1]
            prev_dif = dif.iloc[-2] if len(dif) > 1 else latest_dif
            prev_dea = dea.iloc[-2] if len(dea) > 1 else latest_dea
            
            # 判断金叉/死叉
            if latest_dif > latest_dea and prev_dif <= prev_dea:
                signal = 'golden_cross'  # 金叉
            elif latest_dif < latest_dea and prev_dif >= prev_dea:
                signal = 'death_cross'  # 死叉
            elif latest_dif > latest_dea:
                signal = 'bullish'  # 多头
            else:
                signal = 'bearish'  # 空头
            
            return {
                'dif': round(latest_dif, 3) if not pd.isna(latest_dif) else 0,
                'dea': round(latest_dea, 3) if not pd.isna(latest_dea) else 0,
                'signal': signal
            }
        except:
            return {'dif': 0, 'dea': 0, 'signal': 'neutral'}
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict:
        """计算RSI指标"""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            latest_rsi = rsi.iloc[-1]
            
            if latest_rsi > 70:
                status = 'overbought'  # 超买
            elif latest_rsi < 30:
                status = 'oversold'  # 超卖
            else:
                status = 'neutral'  # 中性
            
            return {
                'value': round(latest_rsi, 1) if not pd.isna(latest_rsi) else 50,
                'status': status
            }
        except:
            return {'value': 50, 'status': 'neutral'}
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """分析成交量"""
        try:
            latest = df.iloc[-1]
            avg_volume_5d = df['volume'].tail(5).mean()
            
            volume_ratio = latest['volume'] / avg_volume_5d if avg_volume_5d > 0 else 1
            
            # 判断量价关系
            price_change = latest.get('change_pct', 0)
            
            if volume_ratio > 1.2 and price_change > 0:
                price_volume = 'rising_with_volume'  # 放量上涨 ✓
                strength = 'strong'
            elif volume_ratio < 0.8 and price_change < 0:
                price_volume = 'falling_with_low_volume'  # 缩量下跌 ✓
                strength = 'weak'
            elif volume_ratio > 1.2 and price_change < 0:
                price_volume = 'falling_with_volume'  # 放量下跌 ✗
                strength = 'very_weak'
            elif volume_ratio < 0.8 and price_change > 0:
                price_volume = 'rising_with_low_volume'  # 缩量上涨 ⚠️
                strength = 'moderate'
            else:
                price_volume = 'neutral'
                strength = 'neutral'
            
            return {
                'volume_ratio': round(volume_ratio, 2),
                'price_volume': price_volume,
                'strength': strength
            }
        except:
            return {'volume_ratio': 1.0, 'price_volume': 'neutral', 'strength': 'neutral'}
    
    def _find_key_levels(self, df: pd.DataFrame) -> Dict:
        """寻找关键支撑/压力位"""
        try:
            recent_df = df.tail(20)  # 最近20天
            
            resistance = recent_df['high'].max()
            support = recent_df['low'].min()
            current_price = df.iloc[-1]['close']
            
            # 判断位置
            price_range = resistance - support
            if price_range > 0:
                position_pct = (current_price - support) / price_range
                if position_pct > 0.7:
                    position = 'top'
                elif position_pct < 0.3:
                    position = 'bottom'
                else:
                    position = 'middle'
            else:
                position = 'middle'
            
            return {
                'resistance': round(resistance, 2),
                'support': round(support, 2),
                'position': position
            }
        except:
            return {'resistance': 0, 'support': 0, 'position': 'middle'}
    
    def _generate_summary(self, trend: Dict, indicators: Dict, volume: Dict) -> str:
        """生成技术面总结"""
        direction_map = {
            'up': '上升趋势',
            'down': '下跌趋势',
            'sideways': '横盘整理'
        }
        
        macd_map = {
            'golden_cross': 'MACD金叉✓',
            'death_cross': 'MACD死叉✗',
            'bullish': 'MACD多头',
            'bearish': 'MACD空头'
        }
        
        rsi_map = {
            'overbought': 'RSI超买',
            'oversold': 'RSI超卖',
            'neutral': 'RSI中性'
        }
        
        volume_map = {
            'rising_with_volume': '放量上涨✓',
            'falling_with_low_volume': '缩量下跌',
            'falling_with_volume': '放量下跌✗',
            'rising_with_low_volume': '缩量上涨⚠️',
            'neutral': '量价平衡'
        }
        
        parts = [
            direction_map.get(trend['direction'], '趋势不明'),
            macd_map.get(indicators['macd']['signal'], ''),
            rsi_map.get(indicators['rsi']['status'], ''),
            volume_map.get(volume['price_volume'], '')
        ]
        
        return ', '.join([p for p in parts if p])
    
    def get_analysis_summary(self, code: str) -> str:
        """
        获取技术面分析摘要（自然语言）
        
        Returns:
            分析摘要文本
        """
        analysis = self.analyze(code)
        
        if not analysis:
            return "⚠️ 技术面数据获取失败"
        
        trend = analysis['trend']
        indicators = analysis['indicators']
        volume = analysis['volume']
        key_levels = analysis['key_levels']
        
        summary = f"""
【技术面】{analysis['summary']}
趋势: {trend['ma_align']}排列, 现价{trend['current_price']:.2f}元
均线: MA5={trend['ma5']:.2f} MA20={trend['ma20']:.2f}
指标: {indicators['macd']['signal']}, RSI={indicators['rsi']['value']:.0f}
量价: {volume['price_volume']} (量比{volume['volume_ratio']:.2f})
关键位: 支撑{key_levels['support']:.2f}元, 压力{key_levels['resistance']:.2f}元
"""
        
        return summary.strip()
