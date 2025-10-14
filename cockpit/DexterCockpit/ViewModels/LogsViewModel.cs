using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Input;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using DexterCockpit.Models;
using DexterCockpit.Services;

namespace DexterCockpit.ViewModels;

/// <summary>
/// ViewModel for Real-Time Logs (bottom pane)
/// Manages 10GB RAM budget with LLM-managed eviction
/// </summary>
public partial class LogsViewModel : ObservableObject
{
    private readonly DexterApiClient _apiClient;
    private readonly DexterWebSocketClient _wsClient;
    private readonly ILogger<LogsViewModel> _logger;

    // Ring buffer for logs with 10GB RAM budget
    private const int MAX_LOG_ENTRIES = 5_000_000; // ~10GB at 2KB per entry
    private long _currentMemoryUsageBytes = 0;
    private const long MAX_MEMORY_BYTES = 10L * 1024 * 1024 * 1024; // 10GB

    [ObservableProperty]
    private ObservableCollection<LogEntry> logs = new();

    [ObservableProperty]
    private ObservableCollection<LogEntry> filteredLogs = new();

    [ObservableProperty]
    private bool isPaused = false;

    [ObservableProperty]
    private bool autoScroll = true;

    [ObservableProperty]
    private string statusMessage = "Ready";

    // Filters
    [ObservableProperty]
    private bool showTrace = true;

    [ObservableProperty]
    private bool showInfo = true;

    [ObservableProperty]
    private bool showWarn = true;

    [ObservableProperty]
    private bool showError = true;

    [ObservableProperty]
    private bool showCritical = true;

    [ObservableProperty]
    private string filterAgent = string.Empty;

    [ObservableProperty]
    private string filterTopic = string.Empty;

    [ObservableProperty]
    private string filterText = string.Empty;

    [ObservableProperty]
    private string memoryUsageDisplay = "0 MB / 10 GB";

    [ObservableProperty]
    private double memoryUsagePercent = 0.0;

    public LogsViewModel(
        DexterApiClient apiClient,
        DexterWebSocketClient wsClient,
        ILogger<LogsViewModel> logger)
    {
        _apiClient = apiClient;
        _wsClient = wsClient;
        _logger = logger;

        // Subscribe to WebSocket log stream
        _wsClient.LogReceived += OnLogReceived;

        // Watch filter properties for auto-filtering
        PropertyChanged += (s, e) =>
        {
            if (e.PropertyName is nameof(ShowTrace) or nameof(ShowInfo) or nameof(ShowWarn) 
                or nameof(ShowError) or nameof(ShowCritical) or nameof(FilterAgent) 
                or nameof(FilterTopic) or nameof(FilterText))
            {
                ApplyFilters();
            }
        };
    }

    /// <summary>
    /// Handle incoming log from WebSocket stream
    /// </summary>
    private void OnLogReceived(object? sender, LogReceivedEventArgs e)
    {
        if (IsPaused) return;

        // Run on UI thread
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            var logEntry = new LogEntry
            {
                Id = Guid.NewGuid(),
                Timestamp = e.Timestamp,
                Level = ParseLogLevel(e.Level),
                AgentId = e.AgentId,
                Topic = ParseTopic(e.Topic),
                Message = e.Message,
                CorrelationId = e.CorrelationId,
                SizeBytes = e.Message?.Length * 2 ?? 0 // Rough estimate: 2 bytes per char
            };

            // Check memory budget
            if (_currentMemoryUsageBytes + logEntry.SizeBytes > MAX_MEMORY_BYTES)
            {
                EvictLeastImportantLogs();
            }

            // Add to collection
            Logs.Add(logEntry);
            _currentMemoryUsageBytes += logEntry.SizeBytes;

            // Update memory display
            UpdateMemoryUsage();

            // Apply filters to show in UI
            if (PassesFilters(logEntry))
            {
                FilteredLogs.Add(logEntry);
            }

            _logger.LogTrace("Received log: {Level} from {Agent}", e.Level, e.AgentId);
        });
    }

    /// <summary>
    /// LLM-managed eviction of least important logs
    /// </summary>
    private void EvictLeastImportantLogs()
    {
        _logger.LogInformation("Memory threshold reached, evicting least important logs");

        // Strategy: Remove oldest TRACE and INFO logs first
        var evictionCandidates = Logs
            .Where(l => l.Level == LogLevel.TRACE || l.Level == LogLevel.INFO)
            .OrderBy(l => l.Timestamp)
            .Take(1000) // Evict in batches of 1000
            .ToList();

        if (!evictionCandidates.Any())
        {
            // If no TRACE/INFO, evict oldest WARN logs
            evictionCandidates = Logs
                .Where(l => l.Level == LogLevel.WARN)
                .OrderBy(l => l.Timestamp)
                .Take(500)
                .ToList();
        }

        foreach (var log in evictionCandidates)
        {
            Logs.Remove(log);
            FilteredLogs.Remove(log);
            _currentMemoryUsageBytes -= log.SizeBytes;
        }

        _logger.LogInformation("Evicted {Count} logs, freed {Bytes} bytes", 
            evictionCandidates.Count, 
            evictionCandidates.Sum(l => l.SizeBytes));

        // TODO: Send evicted logs to LTM (Brain) via backend API
        // await _apiClient.ArchiveLogsAsync(evictionCandidates);
    }

    /// <summary>
    /// Pause/Resume log stream
    /// </summary>
    [RelayCommand]
    public void TogglePause()
    {
        IsPaused = !IsPaused;
        StatusMessage = IsPaused ? "Paused" : "Streaming";
        _logger.LogInformation("Log stream {Status}", IsPaused ? "paused" : "resumed");
    }

    /// <summary>
    /// Clear all logs
    /// </summary>
    [RelayCommand]
    public void ClearLogs()
    {
        Logs.Clear();
        FilteredLogs.Clear();
        _currentMemoryUsageBytes = 0;
        UpdateMemoryUsage();
        StatusMessage = "Logs cleared";
        _logger.LogInformation("Logs cleared by user");
    }

    /// <summary>
    /// Export filtered logs to JSONL
    /// </summary>
    [RelayCommand]
    public async Task ExportLogsJsonlAsync()
    {
        try
        {
            StatusMessage = "Exporting logs...";
            
            // Build filter parameters
            var levels = new System.Collections.Generic.List<string>();
            if (ShowTrace) levels.Add("TRACE");
            if (ShowInfo) levels.Add("INFO");
            if (ShowWarn) levels.Add("WARN");
            if (ShowError) levels.Add("ERROR");
            if (ShowCritical) levels.Add("CRITICAL");

            var success = await _apiClient.ExportLogsAsync(
                format: "jsonl",
                levels: levels,
                agentId: string.IsNullOrEmpty(FilterAgent) ? null : FilterAgent,
                textSearch: string.IsNullOrEmpty(FilterText) ? null : FilterText
            );

            StatusMessage = success ? "Logs exported successfully" : "Export failed";
            _logger.LogInformation("Logs exported to JSONL: {Success}", success);
        }
        catch (Exception ex)
        {
            StatusMessage = $"Export error: {ex.Message}";
            _logger.LogError(ex, "Error exporting logs");
        }
    }

    /// <summary>
    /// Export filtered logs to CSV
    /// </summary>
    [RelayCommand]
    public async Task ExportLogsCsvAsync()
    {
        try
        {
            StatusMessage = "Exporting logs...";
            
            var levels = new System.Collections.Generic.List<string>();
            if (ShowTrace) levels.Add("TRACE");
            if (ShowInfo) levels.Add("INFO");
            if (ShowWarn) levels.Add("WARN");
            if (ShowError) levels.Add("ERROR");
            if (ShowCritical) levels.Add("CRITICAL");

            var success = await _apiClient.ExportLogsAsync(
                format: "csv",
                levels: levels,
                agentId: string.IsNullOrEmpty(FilterAgent) ? null : FilterAgent,
                textSearch: string.IsNullOrEmpty(FilterText) ? null : FilterText
            );

            StatusMessage = success ? "Logs exported successfully" : "Export failed";
            _logger.LogInformation("Logs exported to CSV: {Success}", success);
        }
        catch (Exception ex)
        {
            StatusMessage = $"Export error: {ex.Message}";
            _logger.LogError(ex, "Error exporting logs");
        }
    }

    /// <summary>
    /// Apply all filters to logs
    /// </summary>
    private void ApplyFilters()
    {
        FilteredLogs.Clear();
        foreach (var log in Logs.Where(PassesFilters))
        {
            FilteredLogs.Add(log);
        }
        StatusMessage = $"Showing {FilteredLogs.Count} of {Logs.Count} logs";
    }

    /// <summary>
    /// Check if log passes current filters
    /// </summary>
    private bool PassesFilters(LogEntry log)
    {
        // Level filter
        var levelPass = log.Level switch
        {
            LogLevel.TRACE => ShowTrace,
            LogLevel.INFO => ShowInfo,
            LogLevel.WARN => ShowWarn,
            LogLevel.ERROR => ShowError,
            LogLevel.CRITICAL => ShowCritical,
            _ => false
        };

        if (!levelPass) return false;

        // Agent filter
        if (!string.IsNullOrEmpty(FilterAgent) && 
            !log.AgentId?.Contains(FilterAgent, StringComparison.OrdinalIgnoreCase) == true)
        {
            return false;
        }

        // Topic filter
        if (!string.IsNullOrEmpty(FilterTopic) && 
            !log.Topic.ToString().Contains(FilterTopic, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        // Text search
        if (!string.IsNullOrEmpty(FilterText) && 
            !log.Message?.Contains(FilterText, StringComparison.OrdinalIgnoreCase) == true)
        {
            return false;
        }

        return true;
    }

    private void UpdateMemoryUsage()
    {
        var memoryMb = _currentMemoryUsageBytes / (1024.0 * 1024.0);
        MemoryUsageDisplay = $"{memoryMb:F2} MB / 10 GB";
        MemoryUsagePercent = (_currentMemoryUsageBytes / (double)MAX_MEMORY_BYTES) * 100.0;
    }

    private Models.LogLevel ParseLogLevel(string level)
    {
        return level.ToUpper() switch
        {
            "TRACE" => Models.LogLevel.TRACE,
            "INFO" => Models.LogLevel.INFO,
            "WARN" => Models.LogLevel.WARN,
            "ERROR" => Models.LogLevel.ERROR,
            "CRITICAL" => Models.LogLevel.CRITICAL,
            _ => Models.LogLevel.INFO
        };
    }

    private LogTopic ParseTopic(string topic)
    {
        return topic.ToUpper() switch
        {
            "INTENT" => LogTopic.INTENT,
            "EFFECT" => LogTopic.EFFECT,
            "ERROR" => LogTopic.ERROR,
            "TRACE" => LogTopic.TRACE,
            "COUNCIL" => LogTopic.COUNCIL,
            "SYSTEM" => LogTopic.SYSTEM,
            _ => LogTopic.SYSTEM
        };
    }

    /// <summary>
    /// Cleanup when ViewModel is disposed
    /// </summary>
    public void Dispose()
    {
        _wsClient.LogReceived -= OnLogReceived;
    }
}
