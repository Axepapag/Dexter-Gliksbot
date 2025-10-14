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
        _wsClient.PerformanceDataReceived += OnPerformanceDataReceived;
    }

    private void OnPerformanceDataReceived(object? sender, PerformanceDataEventArgs e)
    {
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            CpuUsage = e.CpuPercent;
            MemoryUsageMb = e.MemoryMb;
            RedisQueueDepth = 0; // Not in event args, keep at 0 or remove if not needed
            BrainSizeMb = e.BrainSizeMb;
            MessagesPerSecond = e.EventBusMessagesPerSec;
            AvgLatencyMs = 0; // Not in event args, keep at 0 or remove if not needed

            // Add to history for charts
            var timestamp = e.Timestamp;
            CpuHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.CpuPercent });
            MemoryHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.MemoryMb });

            // Keep last 60 data points (1 minute at 1sec interval)
            if (CpuHistory.Count > 60) CpuHistory.RemoveAt(0);
            if (MemoryHistory.Count > 60) MemoryHistory.RemoveAt(0);
        });
    }

    public void Dispose()
    {
        _wsClient.PerformanceDataReceived -= OnPerformanceDataReceived;
    }
}

public partial class PerformanceDataPoint : ObservableObject
{
    [ObservableProperty]
    private DateTime timestamp;

    [ObservableProperty]
    private double value;
}
