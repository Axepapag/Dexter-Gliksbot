using System;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using WebSocketSharp;
using Microsoft.Extensions.Logging;

namespace DexterCockpit.Services;

/// <summary>
/// WebSocket client for real-time communication with Dexter backend
/// </summary>
public class DexterWebSocketClient : IDisposable
{
    private readonly string _baseUrl;
    private readonly ILogger<DexterWebSocketClient> _logger;
    private WebSocket? _wsLogs;
    private WebSocket? _wsAgents;
    private WebSocket? _wsMissions;
    private WebSocket? _wsPerformance;
    private WebSocket? _wsConfig;

    public event EventHandler<LogReceivedEventArgs>? LogReceived;
    public event EventHandler<AgentStatusEventArgs>? AgentStatusChanged;
    public event EventHandler<MissionUpdateEventArgs>? MissionUpdated;
    public event EventHandler<PerformanceDataEventArgs>? PerformanceDataReceived;
    public event EventHandler<ConfigChangedEventArgs>? ConfigChanged;

    public bool IsConnected { get; private set; }

    public DexterWebSocketClient(string baseUrl, ILogger<DexterWebSocketClient> logger)
    {
        _baseUrl = baseUrl.Replace("http://", "ws://").Replace("https://", "wss://");
        _logger = logger;
    }

    /// <summary>
    /// Connect to all WebSocket channels
    /// </summary>
    public async Task ConnectAsync()
    {
        try
        {
            _logger.LogInformation("Connecting to Dexter backend at {Url}", _baseUrl);

            // Connect to logs channel
            _wsLogs = new WebSocket($"{_baseUrl}/ws/logs");
            _wsLogs.OnMessage += (sender, e) => HandleLogMessage(e.Data);
            _wsLogs.OnError += (sender, e) => _logger.LogError("WebSocket logs error: {Error}", e.Message);
            _wsLogs.Connect();

            // Connect to agents channel
            _wsAgents = new WebSocket($"{_baseUrl}/ws/agents");
            _wsAgents.OnMessage += (sender, e) => HandleAgentMessage(e.Data);
            _wsAgents.OnError += (sender, e) => _logger.LogError("WebSocket agents error: {Error}", e.Message);
            _wsAgents.Connect();

            // Connect to missions channel
            _wsMissions = new WebSocket($"{_baseUrl}/ws/missions");
            _wsMissions.OnMessage += (sender, e) => HandleMissionMessage(e.Data);
            _wsMissions.OnError += (sender, e) => _logger.LogError("WebSocket missions error: {Error}", e.Message);
            _wsMissions.Connect();

            // Connect to performance channel
            _wsPerformance = new WebSocket($"{_baseUrl}/ws/performance");
            _wsPerformance.OnMessage += (sender, e) => HandlePerformanceMessage(e.Data);
            _wsPerformance.OnError += (sender, e) => _logger.LogError("WebSocket performance error: {Error}", e.Message);
            _wsPerformance.Connect();

            // Connect to config channel
            _wsConfig = new WebSocket($"{_baseUrl}/ws/config");
            _wsConfig.OnMessage += (sender, e) => HandleConfigMessage(e.Data);
            _wsConfig.OnError += (sender, e) => _logger.LogError("WebSocket config error: {Error}", e.Message);
            _wsConfig.Connect();

            IsConnected = true;
            _logger.LogInformation("Connected to all WebSocket channels");

            await Task.CompletedTask;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect to WebSocket channels");
            IsConnected = false;
            throw;
        }
    }

    /// <summary>
    /// Disconnect from all channels
    /// </summary>
    public void Disconnect()
    {
        _wsLogs?.Close();
        _wsAgents?.Close();
        _wsMissions?.Close();
        _wsPerformance?.Close();
        _wsConfig?.Close();

        IsConnected = false;
        _logger.LogInformation("Disconnected from WebSocket channels");
    }

    private void HandleLogMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            LogReceived?.Invoke(this, new LogReceivedEventArgs
            {
                Timestamp = obj["ts"]?.ToObject<DateTime>() ?? DateTime.UtcNow,
                Level = obj["level"]?.ToString() ?? "INFO",
                Topic = obj["topic"]?.ToString() ?? "TRACE",
                AgentId = obj["agent_id"]?.ToString() ?? "",
                CorrelationId = obj["corr"]?.ToString() ?? "",
                Message = obj["msg"]?.ToString() ?? "",
                DataJson = obj["data"]?.ToString() ?? "{}"
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse log message: {Json}", json);
        }
    }

    private void HandleAgentMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            AgentStatusChanged?.Invoke(this, new AgentStatusEventArgs
            {
                AgentId = obj["agent_id"]?.ToString() ?? "",
                Status = obj["status"]?.ToString() ?? "idle",
                CurrentMission = obj["current_mission"]?.ToString() ?? "",
                Uptime = obj["uptime"]?.ToObject<double>() ?? 0.0,
                SuccessRate = obj["success_rate"]?.ToObject<double>() ?? 100.0,
                CpuUsage = obj["cpu_usage"]?.ToObject<double>() ?? 0.0,
                MemoryMb = obj["memory_mb"]?.ToObject<double>() ?? 0.0
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse agent message: {Json}", json);
        }
    }

    private void HandleMissionMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            MissionUpdated?.Invoke(this, new MissionUpdateEventArgs
            {
                MissionId = obj["mission_id"]?.ToString() ?? "",
                Status = obj["status"]?.ToString() ?? "queued",
                CompletedSteps = obj["completed_steps"]?.ToObject<int>() ?? 0,
                TotalSteps = obj["total_steps"]?.ToObject<int>() ?? 0,
                CurrentStep = obj["current_step"]?.ToString() ?? ""
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse mission message: {Json}", json);
        }
    }

    private void HandlePerformanceMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            PerformanceDataReceived?.Invoke(this, new PerformanceDataEventArgs
            {
                Timestamp = DateTime.UtcNow,
                CpuPercent = obj["cpu_percent"]?.ToObject<double>() ?? 0.0,
                MemoryMb = obj["memory_mb"]?.ToObject<double>() ?? 0.0,
                EventBusMessagesPerSec = obj["event_bus_msg_per_sec"]?.ToObject<int>() ?? 0,
                BrainSizeMb = obj["brain_size_mb"]?.ToObject<double>() ?? 0.0
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse performance message: {Json}", json);
        }
    }

    private void HandleConfigMessage(string json)
    {
        try
        {
            var obj = JObject.Parse(json);
            ConfigChanged?.Invoke(this, new ConfigChangedEventArgs
            {
                Event = obj["event"]?.ToString() ?? "",
                Hash = obj["hash"]?.ToString() ?? ""
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse config message: {Json}", json);
        }
    }

    public void Dispose()
    {
        Disconnect();
        _wsLogs?.Dispose();
        _wsAgents?.Dispose();
        _wsMissions?.Dispose();
        _wsPerformance?.Dispose();
        _wsConfig?.Dispose();
    }
}

// Event Args classes
public class LogReceivedEventArgs : EventArgs
{
    public DateTime Timestamp { get; set; }
    public string Level { get; set; } = "";
    public string Topic { get; set; } = "";
    public string AgentId { get; set; } = "";
    public string CorrelationId { get; set; } = "";
    public string Message { get; set; } = "";
    public string DataJson { get; set; } = "{}";
}

public class AgentStatusEventArgs : EventArgs
{
    public string AgentId { get; set; } = "";
    public string Status { get; set; } = "";
    public string CurrentMission { get; set; } = "";
    public double Uptime { get; set; }
    public double SuccessRate { get; set; }
    public double CpuUsage { get; set; }
    public double MemoryMb { get; set; }
}

public class MissionUpdateEventArgs : EventArgs
{
    public string MissionId { get; set; } = "";
    public string Status { get; set; } = "";
    public int CompletedSteps { get; set; }
    public int TotalSteps { get; set; }
    public string CurrentStep { get; set; } = "";
}

public class PerformanceDataEventArgs : EventArgs
{
    public DateTime Timestamp { get; set; }
    public double CpuPercent { get; set; }
    public double MemoryMb { get; set; }
    public int EventBusMessagesPerSec { get; set; }
    public double BrainSizeMb { get; set; }
}

public class ConfigChangedEventArgs : EventArgs
{
    public string Event { get; set; } = "";
    public string Hash { get; set; } = "";
}
