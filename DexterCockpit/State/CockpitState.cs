using System;
using System.Collections.Generic;

namespace DexterCockpit.State;

public sealed class CockpitState
{
    public DockedWindowMemo? DockedWindow { get; set; }

    public List<AgentTabSettings> Agents { get; set; } = new();

    public string DexterHttpUrl { get; set; } = "";

    public string DexterWsUrl { get; set; } = "";

    public List<DockedWindowMemo> DockedHistory { get; set; } = new();
}

public sealed class DockedWindowMemo
{
    public long LastHandle { get; set; }
    public string? LastTitle { get; set; }
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
    public string? DisplayHint { get; set; }
}

public sealed class AgentTabSettings
{
    public string TabId { get; set; } = Guid.NewGuid().ToString("N");
    public string DisplayName { get; set; } = "Agent";
    public string BaseUrl { get; set; } = string.Empty;
    public string ApiKeyEnv { get; set; } = string.Empty;
    public string Model { get; set; } = string.Empty;
    public double Temperature { get; set; } = 0.2;
    public string SystemPrompt { get; set; } = string.Empty;
    public string SessionId { get; set; } = "local";
    public string TargetTitleFallback { get; set; } = string.Empty;
    public bool MonitorEnabled { get; set; }
    public string? TemplateId { get; set; }
}
