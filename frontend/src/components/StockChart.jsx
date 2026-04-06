import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function StockChart({ data, signal }) {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current || !data || data.length === 0) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: '#111827' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: 'rgba(43, 43, 67, 0.5)' },
        horzLines: { color: 'rgba(43, 43, 67, 0.5)' },
      },
      crosshair: {
        mode: 1, // Normal mode
      },
      rightPriceScale: {
        borderColor: 'rgba(43, 43, 67, 0.5)',
      },
      timeScale: {
        borderColor: 'rgba(43, 43, 67, 0.5)',
        rightOffset: 5,
        barSpacing: 10,
        timeVisible: true,
      },
    });
    
    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#ef4444', // 한국 상승은 빨간색
      downColor: '#3b82f6', // 한국 하락은 파란색
      borderDownColor: '#3b82f6',
      borderUpColor: '#ef4444',
      wickDownColor: '#3b82f6',
      wickUpColor: '#ef4444',
    });

    // Format data for lightweight-charts
    const formattedData = data.map(item => ({
      time: item.date, // YYYY-MM-DD
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));
    
    // Sort chronologically and deduplicate times
    // Ensure uniqueness
    const timeMap = {};
    const uniqueData = [];
    formattedData.sort((a,b) => a.time.localeCompare(b.time)).forEach(item => {
        if(!timeMap[item.time]) {
            timeMap[item.time] = true;
            uniqueData.push(item);
        }
    });

    candleSeries.setData(uniqueData);

    // Add Price Lines based on signals
    if (signal) {
      if (signal.buy_price_1) {
        candleSeries.createPriceLine({
          price: signal.buy_price_1,
          color: '#10b981',
          lineWidth: 2,
          lineStyle: 1, // Dotted
          axisLabelVisible: true,
          title: '1차 매수가',
        });
      }
      if (signal.exit_price_1) {
        candleSeries.createPriceLine({
          price: signal.exit_price_1,
          color: '#f59e0b',
          lineWidth: 2,
          lineStyle: 1,
          axisLabelVisible: true,
          title: '1차 매도가',
        });
      }
      if (signal.hard_stop) {
        candleSeries.createPriceLine({
          price: signal.hard_stop,
          color: '#ef4444',
          lineWidth: 2,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: '손절가',
        });
      }
    }

    chart.timeScale().fitContent();

    // Responsive resize
    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, signal]);

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '24px' }}>
      <div className="card-header" style={{ padding: '16px' }}>
        <span className="card-title">📈 차트 및 매매 기준선</span>
      </div>
      <div 
        ref={chartContainerRef} 
        style={{ width: '100%', height: '400px' }} 
      />
    </div>
  );
}
