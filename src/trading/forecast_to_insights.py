"""
Trading Insights Generator
Translates MCP forecasts into actionable trading signals.
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path


class TradingInsightsGenerator:
    """Generates trading insights from MCP forecasts."""
    
    def __init__(self, config_path="config/trading_config.yaml"):
        """Initialize with trading configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.bidding_config = self.config['bidding']
        self.signals_config = self.config['signals']
        
    def generate_trading_signals(self, forecasts, actual_prices=None, confidence=None):
        """
        Generate trading signals from price forecasts.
        
        Args:
            forecasts: Series or DataFrame with MCP forecasts
            actual_prices: Current/actual MCP (for comparison)
            confidence: Forecast confidence scores (optional)
            
        Returns:
            DataFrame with trading signals and recommendations
        """
        signals = pd.DataFrame(index=forecasts.index)
        signals['forecast_mcp'] = forecasts
        
        if actual_prices is not None:
            signals['actual_mcp'] = actual_prices
            signals['price_diff'] = forecasts - actual_prices
            signals['price_diff_pct'] = (signals['price_diff'] / actual_prices) * 100
        else:
            # Use lag for comparison
            signals['price_diff'] = forecasts.diff()
            signals['price_diff_pct'] = forecasts.pct_change() * 100
        
        # Generate buy/sell signals based on price thresholds
        buy_threshold = self.signals_config['price_threshold']['buy']
        sell_threshold = self.signals_config['price_threshold']['sell']
        
        signals['signal'] = np.where(
            signals['price_diff_pct'] < buy_threshold, 'BUY',
            np.where(
                signals['price_diff_pct'] > sell_threshold, 'SELL',
                'HOLD'
            )
        )
        
        # Signal strength based on magnitude
        signals['signal_strength'] = np.abs(signals['price_diff_pct'])
        signals['strength_category'] = pd.cut(
            signals['signal_strength'],
            bins=[0, 2, 5, 100],
            labels=['weak', 'medium', 'strong']
        )
        
        # Volume allocation
        signals['volume_allocation'] = signals['strength_category'].map({
            'weak': self.signals_config['volume_allocation']['weak_signal'],
            'medium': self.signals_config['volume_allocation']['medium_signal'],
            'strong': self.signals_config['volume_allocation']['strong_signal']
        })
        
        # Confidence-based adjustments
        if confidence is not None:
            signals['confidence'] = confidence
            # Reduce volume for low confidence
            low_conf_mask = signals['confidence'] < 0.7
            signals.loc[low_conf_mask, 'volume_allocation'] *= 0.5
        
        return signals
    
    def calculate_bid_price(self, forecast_mcp, strategy='risk_adjusted'):
        """
        Calculate optimal bid price based on forecast.
        
        Args:
            forecast_mcp: Forecasted MCP
            strategy: Bidding strategy ('aggressive', 'conservative', 'risk_adjusted')
            
        Returns:
            Recommended bid price
        """
        strategy_config = self.bidding_config[strategy]
        multiplier = strategy_config['bid_multiplier']
        
        bid_price = forecast_mcp * multiplier
        
        return bid_price
    
    def generate_bidding_recommendations(self, forecasts, strategy='risk_adjusted'):
        """
        Generate bidding recommendations for each forecast period.
        
        Args:
            forecasts: DataFrame with MCP forecasts
            strategy: Bidding strategy
            
        Returns:
            DataFrame with bidding recommendations
        """
        recommendations = pd.DataFrame(index=forecasts.index)
        
        if isinstance(forecasts, pd.Series):
            forecast_values = forecasts.values
        else:
            forecast_values = forecasts['forecast_mcp'].values if 'forecast_mcp' in forecasts.columns else forecasts.values
        
        recommendations['forecast_mcp'] = forecast_values
        recommendations['bid_price'] = self.calculate_bid_price(forecast_values, strategy)
        
        # Volume recommendation
        strategy_config = self.bidding_config[strategy]
        max_volume = strategy_config['max_position_size']
        
        # Higher volume for lower prices (better opportunity)
        price_percentile = pd.Series(forecast_values).rank(pct=True)
        recommendations['recommended_volume_mw'] = max_volume * (1 - price_percentile)
        
        # Risk metrics
        recommendations['expected_cost'] = (
            recommendations['bid_price'] * recommendations['recommended_volume_mw']
        )
        
        return recommendations
    
    def calculate_portfolio_metrics(self, trades_df):
        """
        Calculate portfolio performance metrics.
        
        Args:
            trades_df: DataFrame with executed trades (timestamp, entry_price, exit_price, volume)
            
        Returns:
            Dict with performance metrics
        """
        if 'pnl' not in trades_df.columns:
            trades_df['pnl'] = (trades_df['exit_price'] - trades_df['entry_price']) * trades_df['volume']
        
        total_pnl = trades_df['pnl'].sum()
        num_trades = len(trades_df)
        winning_trades = (trades_df['pnl'] > 0).sum()
        losing_trades = (trades_df['pnl'] < 0).sum()
        
        win_rate = winning_trades / num_trades if num_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Sharpe ratio (assuming daily returns)
        returns = trades_df['pnl'] / trades_df['entry_price'] / trades_df['volume']
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Max drawdown
        cumulative = trades_df['pnl'].cumsum()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        metrics = {
            'total_pnl': total_pnl,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }
        
        return metrics
    
    def create_trading_report(self, signals, recommendations, metrics=None):
        """
        Create a comprehensive trading report.
        
        Args:
            signals: Trading signals DataFrame
            recommendations: Bidding recommendations DataFrame
            metrics: Portfolio metrics dict (optional)
            
        Returns:
            Report string
        """
        report = []
        report.append("=" * 60)
        report.append("TRADING INSIGHTS REPORT")
        report.append("=" * 60)
        
        # Summary statistics
        report.append("\n--- Signal Summary ---")
        signal_counts = signals['signal'].value_counts()
        for signal, count in signal_counts.items():
            pct = (count / len(signals)) * 100
            report.append(f"{signal}: {count} ({pct:.1f}%)")
        
        # Top opportunities
        report.append("\n--- Top Trading Opportunities ---")
        top_buys = signals[signals['signal'] == 'BUY'].nlargest(5, 'signal_strength')
        report.append("\nTop 5 BUY Signals:")
        for idx, row in top_buys.iterrows():
            report.append(f"  {idx}: Forecast={row['forecast_mcp']:.2f}, Strength={row['signal_strength']:.2f}%")
        
        top_sells = signals[signals['signal'] == 'SELL'].nlargest(5, 'signal_strength')
        report.append("\nTop 5 SELL Signals:")
        for idx, row in top_sells.iterrows():
            report.append(f"  {idx}: Forecast={row['forecast_mcp']:.2f}, Strength={row['signal_strength']:.2f}%")
        
        # Bidding recommendations
        report.append("\n--- Bidding Recommendations ---")
        report.append(f"Average Bid Price: {recommendations['bid_price'].mean():.2f} INR/MWh")
        report.append(f"Total Recommended Volume: {recommendations['recommended_volume_mw'].sum():.0f} MW")
        report.append(f"Expected Total Cost: {recommendations['expected_cost'].sum():.0f} INR")
        
        # Portfolio metrics
        if metrics:
            report.append("\n--- Portfolio Performance ---")
            report.append(f"Total P&L: {metrics['total_pnl']:.2f} INR")
            report.append(f"Number of Trades: {metrics['num_trades']}")
            report.append(f"Win Rate: {metrics['win_rate']:.2%}")
            report.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
            report.append(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            report.append(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)


if __name__ == "__main__":
    # Example usage
    insights_generator = TradingInsightsGenerator()
    
    # Load sample forecast data
    print("Loading forecast data...")
    data = pd.read_csv('data/processed/market_weather_energy_data.csv',
                      parse_dates=['timestamp'], index_col='timestamp')
    
    # Simulate forecasts (in real use, these come from trained model)
    forecasts = data['mcp_inr_per_mwh'].iloc[-100:]  # Last 100 hours
    actual_prices = forecasts + np.random.normal(0, 5, len(forecasts))  # Simulate actual vs forecast
    
    # Generate signals
    print("\nGenerating trading signals...")
    signals = insights_generator.generate_trading_signals(forecasts, actual_prices)
    
    # Generate bidding recommendations
    print("Generating bidding recommendations...")
    recommendations = insights_generator.generate_bidding_recommendations(forecasts)
    
    # Simulate some trades for metrics
    sample_trades = pd.DataFrame({
        'entry_price': np.random.uniform(40, 60, 50),
        'exit_price': np.random.uniform(40, 60, 50),
        'volume': np.random.uniform(100, 500, 50)
    })
    
    # Calculate portfolio metrics
    metrics = insights_generator.calculate_portfolio_metrics(sample_trades)
    
    # Create report
    report = insights_generator.create_trading_report(signals, recommendations, metrics)
    print("\n" + report)
    
    # Save outputs
    signals.to_csv('outputs/trading_signals.csv')
    recommendations.to_csv('outputs/bidding_recommendations.csv')
    
    with open('outputs/trading_report.txt', 'w') as f:
        f.write(report)
    
    print("\nTrading insights saved to outputs/")
