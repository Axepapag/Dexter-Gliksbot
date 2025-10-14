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
/// Main ViewModel orchestrating all mission control components
/// </summary>
public partial class MainViewModel : ObservableObject
{
    private readonly DexterApiClient _apiClient;
    private readonly DexterWebSocketClient _wsClient;
    private readonly ILogger<MainViewModel> _logger;

    // Child ViewModels
    public AgentRosterViewModel AgentRoster { get; }
    public LogsViewModel Logs { get; }
    public ChatViewModel Chat { get; }
    public PerformanceViewModel Performance { get; }

    [ObservableProperty]
    private string windowTitle = "Dexter Mission Control - Disconnected";

    [ObservableProperty]
    private bool isConnected = false;

    [ObservableProperty]
    private string connectionStatus = "Disconnected";

    [ObservableProperty]
    private ObservableCollection<Agent> activeAgents = new();

    public MainViewModel(
        DexterApiClient apiClient,
        DexterWebSocketClient wsClient,
        AgentRosterViewModel agentRoster,
        LogsViewModel logs,
        ChatViewModel chat,
        PerformanceViewModel performance,
        ILogger<MainViewModel> logger)
    {
        _apiClient = apiClient;
        _wsClient = wsClient;
        AgentRoster = agentRoster;
        Logs = logs;
        Chat = chat;
        Performance = performance;
        _logger = logger;

        // Subscribe to connection events
        _wsClient.Connected += OnWebSocketConnected;
        _wsClient.Disconnected += OnWebSocketDisconnected;
    }

    /// <summary>
    /// Initialize and connect to backend
    /// </summary>
    [RelayCommand]
    public async Task InitializeAsync()
    {
        _logger.LogInformation("Initializing Dexter Mission Control...");

        try
        {
            // Connect WebSocket channels
            await _wsClient.ConnectAsync("ws://localhost:8765");

            // Load initial data
            await AgentRoster.LoadAgentsAsync();

            _logger.LogInformation("Mission Control initialized successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to initialize Mission Control");
            ConnectionStatus = $"Error: {ex.Message}";
        }
    }

    private void OnWebSocketConnected(object? sender, EventArgs e)
    {
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            IsConnected = true;
            ConnectionStatus = "Connected";
            WindowTitle = "Dexter Mission Control - Connected";
            _logger.LogInformation("WebSocket connected");
        });
    }

    private void OnWebSocketDisconnected(object? sender, EventArgs e)
    {
        System.Windows.Application.Current?.Dispatcher.Invoke(() =>
        {
            IsConnected = false;
            ConnectionStatus = "Disconnected";
            WindowTitle = "Dexter Mission Control - Disconnected";
            _logger.LogWarning("WebSocket disconnected");
        });
    }

    /// <summary>
    /// Cleanup on shutdown
    /// </summary>
    public void Dispose()
    {
        _wsClient.Connected -= OnWebSocketConnected;
        _wsClient.Disconnected -= OnWebSocketDisconnected;
        _wsClient.DisconnectAsync().Wait();
        
        AgentRoster.Dispose();
        Logs.Dispose();
        Chat.Dispose();
    }
}
