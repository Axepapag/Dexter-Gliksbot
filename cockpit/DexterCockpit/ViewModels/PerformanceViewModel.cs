using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using DexterCockpit.Models;
using DexterCockpit.Services;

namespace DexterCockpit.ViewModels;

/// <summary>
/// ViewModel for performance monitoring
/// </summary>
public partial class PerformanceViewModel : ObservableObject
{
    private readonly DexterWebSocketClient _wsClient;
    private readonly ILogger<PerformanceViewModel> _logger;

    [ObservableProperty]
    private double cpuUsage = 0.0;

    [ObservableProperty]
    private double memoryUsageMb = 0.0;

    [ObservableProperty]
    private int redisQueueDepth = 0;

    [ObservableProperty]
    private double brainSizeMb = 0.0;

    [ObservableProperty]
    private int messagesPerSecond = 0;

    [ObservableProperty]
    private double avgLatencyMs = 0.0;

    [ObservableProperty]
    private ObservableCollection<PerformanceDataPoint> cpuHistory = new();

    [ObservableProperty]
    private ObservableCollection<PerformanceDataPoint> memoryHistory = new();

    public PerformanceViewModel(
        DexterWebSocketClient wsClient,
        ILogger<PerformanceViewModel> logger)
    {
        _wsClient = wsClient;
        _logger = logger;

        // Subscribe to performance metrics
        _wsClient.PerformanceMetric += OnPerformanceMetricReceived;
    }

    private void OnPerformanceMetricReceived(object? sender, PerformanceMetricEventArgs e)
    {
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            CpuUsage = e.CpuUsage;
            MemoryUsageMb = e.MemoryMb;
            RedisQueueDepth = e.RedisQueueDepth;
            BrainSizeMb = e.BrainSizeMb;
            MessagesPerSecond = e.MessagesPerSecond;
            AvgLatencyMs = e.AvgLatencyMs;

            // Add to history for charts
            var timestamp = DateTime.UtcNow;
            CpuHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.CpuUsage });
            MemoryHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.MemoryMb });

            // Keep last 60 data points (1 minute at 1sec interval)
            if (CpuHistory.Count > 60) CpuHistory.RemoveAt(0);
            if (MemoryHistory.Count > 60) MemoryHistory.RemoveAt(0);
        });
    }

    public void Dispose()
    {
        _wsClient.PerformanceMetric -= OnPerformanceMetricReceived;
    }
}

public partial class PerformanceDataPoint : ObservableObject
{
    [ObservableProperty]
    private DateTime timestamp;

    [ObservableProperty]
    private double value;
}
