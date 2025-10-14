using System;
using System.Collections.Generic;
using CommunityToolkit.Mvvm.ComponentModel;

namespace DexterCockpit.Models;

/// <summary>
/// Represents the status of a mission
/// </summary>
public enum MissionStatus
{
    Queued,      // Waiting to start
    Running,     // Currently executing
    Paused,      // Temporarily stopped
    Completed,   // Successfully finished
    Failed,      // Encountered error
    Cancelled    // Manually stopped
}

/// <summary>
/// Model for an agent mission/task
/// </summary>
public partial class Mission : ObservableObject
{
    [ObservableProperty]
    private string id = Guid.NewGuid().ToString();

    [ObservableProperty]
    private string name = "Untitled Mission";

    [ObservableProperty]
    private string description = string.Empty;

    [ObservableProperty]
    private MissionStatus status = MissionStatus.Queued;

    [ObservableProperty]
    private List<string> assignedAgentIds = new();

    [ObservableProperty]
    private DateTime startTime = DateTime.UtcNow;

    [ObservableProperty]
    private DateTime? endTime;

    [ObservableProperty]
    private int totalSteps = 0;

    [ObservableProperty]
    private int completedSteps = 0;

    [ObservableProperty]
    private double progressPercent = 0.0;

    [ObservableProperty]
    private string currentStep = string.Empty;

    [ObservableProperty]
    private string yamlDefinition = string.Empty;

    [ObservableProperty]
    private Dictionary<string, object> metadata = new();

    /// <summary>
    /// Gets elapsed time for running/completed missions
    /// </summary>
    public TimeSpan ElapsedTime =>
        (EndTime ?? DateTime.UtcNow) - StartTime;

    /// <summary>
    /// Gets the status color for UI
    /// </summary>
    public string StatusColor => Status switch
    {
        MissionStatus.Queued => "#9E9E9E",      // Gray
        MissionStatus.Running => "#2196F3",     // Blue
        MissionStatus.Paused => "#FF9800",      // Orange
        MissionStatus.Completed => "#4CAF50",   // Green
        MissionStatus.Failed => "#F44336",      // Red
        MissionStatus.Cancelled => "#757575",   // Dark gray
        _ => "#9E9E9E"
    };

    /// <summary>
    /// Update progress when steps change
    /// </summary>
    partial void OnCompletedStepsChanged(int value) => UpdateProgress();
    partial void OnTotalStepsChanged(int value) => UpdateProgress();

    private void UpdateProgress()
    {
        if (TotalSteps > 0)
        {
            ProgressPercent = (CompletedSteps / (double)TotalSteps) * 100.0;
        }
    }

    /// <summary>
    /// Notify UI when status changes
    /// </summary>
    partial void OnStatusChanged(MissionStatus value)
    {
        OnPropertyChanged(nameof(StatusColor));
    }
}
