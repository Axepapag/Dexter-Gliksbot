using System;
using CommunityToolkit.Mvvm.ComponentModel;

namespace DexterCockpit.Models;

/// <summary>
/// Log severity levels matching backend
/// </summary>
public enum LogLevel
{
    TRACE,
    INFO,
    WARN,
    ERROR,
    CRITICAL
}

/// <summary>
/// Event bus topics matching backend
/// </summary>
public enum LogTopic
{
    INTENT,
    EFFECT,
    ERROR,
    TRACE,
    COUNCIL,
    SYSTEM
}

/// <summary>
/// Model for a log entry from the backend
/// </summary>
public partial class LogEntry : ObservableObject
{
    [ObservableProperty]
    private Guid id = Guid.NewGuid();

    [ObservableProperty]
    private DateTime timestamp = DateTime.UtcNow;

    [ObservableProperty]
    private LogLevel level = LogLevel.INFO;

    [ObservableProperty]
    private LogTopic topic = LogTopic.TRACE;

    [ObservableProperty]
    private string agentId = string.Empty;

    [ObservableProperty]
    private string correlationId = string.Empty;

    [ObservableProperty]
    private string message = string.Empty;

    [ObservableProperty]
    private string dataJson = "{}";

    [ObservableProperty]
    private long sizeBytes = 0;

    /// <summary>
    /// Gets the level color for UI
    /// </summary>
    public string LevelColor => Level switch
    {
        LogLevel.TRACE => "#9E9E9E",    // Gray
        LogLevel.INFO => "#2196F3",     // Blue
        LogLevel.WARN => "#FF9800",     // Orange
        LogLevel.ERROR => "#F44336",    // Red
        LogLevel.CRITICAL => "#9C27B0", // Purple
        _ => "#FFFFFF"
    };

    /// <summary>
    /// Gets the level icon
    /// </summary>
    public string LevelIcon => Level switch
    {
        LogLevel.TRACE => "🔍",
        LogLevel.INFO => "ℹ️",
        LogLevel.WARN => "⚠️",
        LogLevel.ERROR => "❌",
        LogLevel.CRITICAL => "🔥",
        _ => "📝"
    };

    /// <summary>
    /// Background color for severity
    /// </summary>
    public string BackgroundColor => Level switch
    {
        LogLevel.ERROR => "#3D2020",      // Dark red
        LogLevel.CRITICAL => "#3D2030",   // Dark purple
        LogLevel.WARN => "#3D3020",       // Dark yellow
        _ => "Transparent"
    };

    /// <summary>
    /// Formatted timestamp for display
    /// </summary>
    public string TimestampFormatted =>
        Timestamp.ToString("HH:mm:ss.fff");

    /// <summary>
    /// Notify UI when level changes
    /// </summary>
    partial void OnLevelChanged(LogLevel value)
    {
        OnPropertyChanged(nameof(LevelColor));
        OnPropertyChanged(nameof(LevelIcon));
        OnPropertyChanged(nameof(BackgroundColor));
    }
}
