using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using DexterCockpit.Models;

namespace DexterCockpit.Services;

/// <summary>
/// HTTP API client for Dexter backend REST endpoints
/// </summary>
public class DexterApiClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<DexterApiClient> _logger;

    public DexterApiClient(string baseUrl, ILogger<DexterApiClient> logger)
    {
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri(baseUrl),
            Timeout = TimeSpan.FromSeconds(30)
        };
        _logger = logger;
    }

    #region Health & Status

    public async Task<HealthResponse?> GetHealthAsync()
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<HealthResponse>("/healthz");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get health status");
            return null;
        }
    }

    #endregion

    #region Agents

    public async Task<List<Agent>?> GetAgentsAsync()
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<List<Agent>>("/agents");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get agents");
            return null;
        }
    }

    public async Task<bool> PauseAgentAsync(string agentId)
    {
        try
        {
            var response = await _httpClient.PostAsync($"/agents/{agentId}/pause", null);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to pause agent {AgentId}", agentId);
            return false;
        }
    }

    public async Task<bool> ResumeAgentAsync(string agentId)
    {
        try
        {
            var response = await _httpClient.PostAsync($"/agents/{agentId}/resume", null);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to resume agent {AgentId}", agentId);
            return false;
        }
    }

    public async Task<bool> StopAgentAsync(string agentId)
    {
        try
        {
            var response = await _httpClient.PostAsync($"/agents/{agentId}/stop", null);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to stop agent {AgentId}", agentId);
            return false;
        }
    }

    #endregion

    #region Missions

    public async Task<List<Mission>?> GetMissionsAsync()
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<List<Mission>>("/missions");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get missions");
            return null;
        }
    }

    public async Task<Mission?> CreateMissionAsync(string name, string yamlDefinition)
    {
        try
        {
            var response = await _httpClient.PostAsJsonAsync("/missions", new
            {
                name,
                yaml = yamlDefinition
            });
            return await response.Content.ReadFromJsonAsync<Mission>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create mission");
            return null;
        }
    }

    public async Task<bool> StartMissionAsync(string missionId)
    {
        try
        {
            var response = await _httpClient.PostAsync($"/missions/{missionId}/start", null);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to start mission {MissionId}", missionId);
            return false;
        }
    }

    public async Task<bool> PauseMissionAsync(string missionId)
    {
        try
        {
            var response = await _httpClient.PostAsync($"/missions/{missionId}/pause", null);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to pause mission {MissionId}", missionId);
            return false;
        }
    }

    public async Task<bool> CancelMissionAsync(string missionId)
    {
        try
        {
            var response = await _httpClient.DeleteAsync($"/missions/{missionId}");
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to cancel mission {MissionId}", missionId);
            return false;
        }
    }

    #endregion

    #region Logs

    public async Task<bool> ExportLogsAsync(string outputPath, LogFilter? filter = null)
    {
        try
        {
            var queryParams = filter != null ? BuildLogFilterQuery(filter) : "";
            var response = await _httpClient.GetAsync($"/logs/export{queryParams}");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                await System.IO.File.WriteAllTextAsync(outputPath, content);
                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to export logs");
            return false;
        }
    }

    private string BuildLogFilterQuery(LogFilter filter)
    {
        var parts = new List<string>();
        if (filter.Levels.Count > 0)
            parts.Add($"levels={string.Join(",", filter.Levels)}");
        if (filter.AgentIds.Count > 0)
            parts.Add($"agents={string.Join(",", filter.AgentIds)}");
        if (filter.Topics.Count > 0)
            parts.Add($"topics={string.Join(",", filter.Topics)}");
        if (!string.IsNullOrEmpty(filter.SearchText))
            parts.Add($"search={Uri.EscapeDataString(filter.SearchText)}");
        
        return parts.Count > 0 ? "?" + string.Join("&", parts) : "";
    }

    #endregion

    #region Configuration

    public async Task<ConfigResponse?> GetConfigAsync()
    {
        try
        {
            return await _httpClient.GetFromJsonAsync<ConfigResponse>("/config");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get config");
            return null;
        }
    }

    public async Task<bool> UpdateConfigAsync(string yamlContent)
    {
        try
        {
            var response = await _httpClient.PostAsJsonAsync("/config", new { yaml = yamlContent });
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to update config");
            return false;
        }
    }

    #endregion
}

// Response models
public class HealthResponse
{
    public bool Ok { get; set; }
    public string Mode { get; set; } = "";
    public Dictionary<string, object> Details { get; set; } = new();
}

public class ConfigResponse
{
    public string Yaml { get; set; } = "";
    public string Hash { get; set; } = "";
}

public class LogFilter
{
    public List<string> Levels { get; set; } = new();
    public List<string> AgentIds { get; set; } = new();
    public List<string> Topics { get; set; } = new();
    public string SearchText { get; set; } = "";
}
