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
/// ViewModel for the Agent Roster (left sidebar)
/// Manages list of active agents and their controls
/// </summary>
public partial class AgentRosterViewModel : ObservableObject
{
    private readonly DexterApiClient _apiClient;
    private readonly DexterWebSocketClient _wsClient;
    private readonly ILogger<AgentRosterViewModel> _logger;

    [ObservableProperty]
    private ObservableCollection<Agent> agents = new();

    [ObservableProperty]
    private Agent? selectedAgent;

    [ObservableProperty]
    private bool isLoading = false;

    [ObservableProperty]
    private string statusMessage = "Ready";

    public AgentRosterViewModel(
        DexterApiClient apiClient,
        DexterWebSocketClient wsClient,
        ILogger<AgentRosterViewModel> logger)
    {
        _apiClient = apiClient;
        _wsClient = wsClient;
        _logger = logger;

        // Subscribe to WebSocket agent status updates
        _wsClient.AgentStatusChanged += OnAgentStatusChanged;
    }

    /// <summary>
    /// Load all agents from backend
    /// </summary>
    [RelayCommand]
    public async Task LoadAgentsAsync()
    {
        IsLoading = true;
        StatusMessage = "Loading agents...";

        try
        {
            var agentList = await _apiClient.GetAgentsAsync();
            if (agentList != null)
            {
                Agents.Clear();
                foreach (var agent in agentList)
                {
                    Agents.Add(agent);
                }
                StatusMessage = $"Loaded {Agents.Count} agents";
                _logger.LogInformation("Loaded {Count} agents", Agents.Count);
            }
            else
            {
                StatusMessage = "Failed to load agents";
                _logger.LogWarning("Failed to load agents from API");
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            _logger.LogError(ex, "Error loading agents");
        }
        finally
        {
            IsLoading = false;
        }
    }

    /// <summary>
    /// Pause selected agent
    /// </summary>
    [RelayCommand(CanExecute = nameof(CanExecuteAgentCommand))]
    public async Task PauseAgentAsync()
    {
        if (SelectedAgent == null) return;

        try
        {
            var success = await _apiClient.PauseAgentAsync(SelectedAgent.Id);
            if (success)
            {
                SelectedAgent.Status = AgentStatus.Paused;
                StatusMessage = $"Paused agent {SelectedAgent.Name}";
                _logger.LogInformation("Paused agent {AgentId}", SelectedAgent.Id);
            }
            else
            {
                StatusMessage = $"Failed to pause {SelectedAgent.Name}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            _logger.LogError(ex, "Error pausing agent");
        }
    }

    /// <summary>
    /// Resume selected agent
    /// </summary>
    [RelayCommand(CanExecute = nameof(CanExecuteAgentCommand))]
    public async Task ResumeAgentAsync()
    {
        if (SelectedAgent == null) return;

        try
        {
            var success = await _apiClient.ResumeAgentAsync(SelectedAgent.Id);
            if (success)
            {
                SelectedAgent.Status = AgentStatus.Active;
                StatusMessage = $"Resumed agent {SelectedAgent.Name}";
                _logger.LogInformation("Resumed agent {AgentId}", SelectedAgent.Id);
            }
            else
            {
                StatusMessage = $"Failed to resume {SelectedAgent.Name}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            _logger.LogError(ex, "Error resuming agent");
        }
    }

    /// <summary>
    /// Stop selected agent
    /// </summary>
    [RelayCommand(CanExecute = nameof(CanExecuteAgentCommand))]
    public async Task StopAgentAsync()
    {
        if (SelectedAgent == null) return;

        try
        {
            var success = await _apiClient.StopAgentAsync(SelectedAgent.Id);
            if (success)
            {
                SelectedAgent.Status = AgentStatus.Stopped;
                StatusMessage = $"Stopped agent {SelectedAgent.Name}";
                _logger.LogInformation("Stopped agent {AgentId}", SelectedAgent.Id);
            }
            else
            {
                StatusMessage = $"Failed to stop {SelectedAgent.Name}";
            }
        }
        catch (Exception ex)
        {
            StatusMessage = $"Error: {ex.Message}";
            _logger.LogError(ex, "Error stopping agent");
        }
    }

    /// <summary>
    /// View logs for selected agent (opens log filter)
    /// </summary>
    [RelayCommand(CanExecute = nameof(CanExecuteAgentCommand))]
    public void ViewAgentLogs()
    {
        if (SelectedAgent == null) return;

        // This will be handled by the MainViewModel to filter logs
        // For now, just log the action
        _logger.LogInformation("Viewing logs for agent {AgentId}", SelectedAgent.Id);
        StatusMessage = $"Showing logs for {SelectedAgent.Name}";
    }

    private bool CanExecuteAgentCommand()
    {
        return SelectedAgent != null;
    }

    /// <summary>
    /// Handle real-time agent status updates from WebSocket
    /// </summary>
    private void OnAgentStatusChanged(object? sender, AgentStatusEventArgs e)
    {
        // Run on UI thread
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            var agent = Agents.FirstOrDefault(a => a.Id == e.AgentId);
            if (agent != null)
            {
                // Update agent properties
                agent.Status = ParseStatus(e.Status);
                agent.CurrentMission = e.CurrentMission;
                agent.Uptime = TimeSpan.FromSeconds(e.Uptime);
                agent.SuccessRate = e.SuccessRate;
                agent.CpuUsage = e.CpuUsage;
                agent.MemoryUsageMb = e.MemoryMb;
                agent.LastActionTime = DateTime.UtcNow;

                _logger.LogTrace("Updated agent {AgentId} status to {Status}", e.AgentId, e.Status);
            }
            else
            {
                // New agent detected, reload list
                _logger.LogInformation("New agent detected: {AgentId}", e.AgentId);
                _ = LoadAgentsAsync();
            }
        });
    }

    private AgentStatus ParseStatus(string status)
    {
        return status.ToLower() switch
        {
            "idle" => AgentStatus.Idle,
            "active" => AgentStatus.Active,
            "busy" => AgentStatus.Busy,
            "error" => AgentStatus.Error,
            "paused" => AgentStatus.Paused,
            "stopped" => AgentStatus.Stopped,
            _ => AgentStatus.Idle
        };
    }

    /// <summary>
    /// Cleanup when ViewModel is disposed
    /// </summary>
    public void Dispose()
    {
        _wsClient.AgentStatusChanged -= OnAgentStatusChanged;
    }
}
