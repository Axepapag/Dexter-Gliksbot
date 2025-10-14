using System;
using CommunityToolkit.Mvvm.ComponentModel;

namespace DexterCockpit.Models;

/// <summary>
/// Represents the status of an agent
/// </summary>
public enum AgentStatus
{
    Idle,       // Gray - Not doing anything
    Active,     // Green - Healthy and available
    Busy,       // Yellow - Executing task
    Error,      // Red - Failed or crashed
    Paused,     // Orange - Manually paused
    Stopped     // Black - Stopped/removed
}

/// <summary>
/// Model for an autonomous agent running in the system
/// </summary>
public partial class Agent : ObservableObject
{
    [ObservableProperty]
    private string id = string.Empty;

    [ObservableProperty]
    private string name = string.Empty;

    [ObservableProperty]
    private AgentStatus status = AgentStatus.Idle;

    [ObservableProperty]
    private string currentMission = "Idle";

    [ObservableProperty]
    private TimeSpan uptime = TimeSpan.Zero;

    [ObservableProperty]
    private double successRate = 100.0;

    [ObservableProperty]
    private int totalActions = 0;

    [ObservableProperty]
    private int successfulActions = 0;

    [ObservableProperty]
    private int failedActions = 0;

    [ObservableProperty]
    private DateTime lastActionTime = DateTime.UtcNow;

    [ObservableProperty]
    private double cpuUsage = 0.0;

    [ObservableProperty]
    private double memoryUsageMb = 0.0;

    [ObservableProperty]
    private int apiCallsPerMinute = 0;

    [ObservableProperty]
    private string provider = "ollama";

    [ObservableProperty]
    private string model = string.Empty;

    [ObservableProperty]
    private string endpoint = string.Empty;

    /// <summary>
    /// Gets the status color for UI binding
    /// </summary>
    public string StatusColor => Status switch
    {
        AgentStatus.Idle => "#9E9E9E",      // Gray
        AgentStatus.Active => "#4CAF50",    // Green
        AgentStatus.Busy => "#FFC107",      // Yellow
        AgentStatus.Error => "#F44336",     // Red
        AgentStatus.Paused => "#FF9800",    // Orange
        AgentStatus.Stopped => "#424242",   // Dark gray
        _ => "#9E9E9E"
    };

    /// <summary>
    /// Gets the status icon for UI
    /// </summary>
    public string StatusIcon => Status switch
    {
        AgentStatus.Idle => "⚪",
        AgentStatus.Active => "🟢",
        AgentStatus.Busy => "🟡",
        AgentStatus.Error => "🔴",
        AgentStatus.Paused => "🟠",
        AgentStatus.Stopped => "⚫",
        _ => "⚪"
    };

    /// <summary>
    /// Update success rate when actions change
    /// </summary>
    partial void OnSuccessfulActionsChanged(int value) => UpdateSuccessRate();
    partial void OnFailedActionsChanged(int value) => UpdateSuccessRate();

    private void UpdateSuccessRate()
    {
        if (TotalActions > 0)
        {
            SuccessRate = (SuccessfulActions / (double)TotalActions) * 100.0;
        }
    }

    /// <summary>
    /// Notify UI when status changes (to update color)
    /// </summary>
    partial void OnStatusChanged(AgentStatus value)
    {
        OnPropertyChanged(nameof(StatusColor));
        OnPropertyChanged(nameof(StatusIcon));
    }
}
