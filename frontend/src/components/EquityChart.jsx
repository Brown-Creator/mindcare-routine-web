import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function EquityChart({ data }) {
  const chartContainerRef = useRef();
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current || !data || data.length === 0) return;

    if (chartRef.current) {
        chartRef.current.remove();
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: '#111827' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: 'rgba(43, 43, 67, 0.5)' },
        horzLines: { color: 'rgba(43, 43, 67, 0.5)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(43, 43, 67, 0.5)',
      },
      timeScale: {
        borderColor: 'rgba(43, 43, 67, 0.5)',
      },
    });
    
    chartRef.current = chart;

    const areaSeries = chart.addAreaSeries({
      lineColor: '#3b82f6',
      topColor: 'rgba(59, 130, 246, 0.4)',
      bottomColor: 'rgba(59, 130, 246, 0.0)',
      lineWidth: 2,
    });

    // deduplicate and sort
    const timeMap = {};
    const uniqueData = [];
    data.sort((a,b) => a.time.localeCompare(b.time)).forEach(item => {
        if(!timeMap[item.time]) {
            timeMap[item.time] = true;
            uniqueData.push({ time: item.time, value: item.value });
        }
    });

    areaSeries.setData(uniqueData);
    chart.timeScale().fitContent();

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  return (
    <div 
      ref={chartContainerRef} 
      style={{ width: '100%', height: '400px' }} 
    />
  );
}
