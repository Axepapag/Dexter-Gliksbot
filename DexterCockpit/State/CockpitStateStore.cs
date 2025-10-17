using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace DexterCockpit.State;

public sealed class CockpitStateStore
{
    private static readonly Lazy<CockpitStateStore> LazyInstance = new(() => new CockpitStateStore());

    public static CockpitStateStore Instance => LazyInstance.Value;

    private readonly string _statePath;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public CockpitState State { get; private set; } = new();

    private CockpitStateStore()
    {
        var baseDir = AppContext.BaseDirectory;
        var dataDir = Path.Combine(baseDir, "data");
        Directory.CreateDirectory(dataDir);
        _statePath = Path.Combine(dataDir, "cockpit_state.json");
        Load();
    }

    public void Load()
    {
        if (!File.Exists(_statePath))
        {
            State = new CockpitState();
            return;
        }

        try
        {
            var json = File.ReadAllText(_statePath);
            var state = JsonSerializer.Deserialize<CockpitState>(json, _jsonOptions);
            State = state ?? new CockpitState();
            State.Agents ??= new List<AgentTabSettings>();
            State.DexterHttpUrl ??= "";
            State.DexterWsUrl ??= "";
            State.DockedHistory ??= new List<DockedWindowMemo>();
        }
        catch
        {
            State = new CockpitState();
        }
    }

    public void Save()
    {
        var json = JsonSerializer.Serialize(State, _jsonOptions);
        File.WriteAllText(_statePath, json);
    }

    public void UpdateDocked(IntPtr handle, string? title, string? displayHint = null)
    {
        var memo = new DockedWindowMemo
        {
            LastHandle = handle.ToInt64(),
            LastTitle = title,
            UpdatedAt = DateTimeOffset.UtcNow,
            DisplayHint = displayHint
        };
        State.DockedWindow = memo;
        RecordDockHistory(memo);
        Save();
    }

    public void ClearDocked()
    {
        State.DockedWindow = null;
        Save();
    }

    public void UpdateEndpoints(string httpUrl, string wsUrl)
    {
        State.DexterHttpUrl = httpUrl;
        State.DexterWsUrl = wsUrl;
        Save();
    }

    public void RecordDockHistory(DockedWindowMemo memo)
    {
        State.DockedHistory ??= new List<DockedWindowMemo>();
        // Remove any existing entries that match by title (case-insensitive)
        State.DockedHistory.RemoveAll(x =>
            (!string.IsNullOrWhiteSpace(x.LastTitle) && !string.IsNullOrWhiteSpace(memo.LastTitle) &&
             string.Equals(x.LastTitle, memo.LastTitle, StringComparison.OrdinalIgnoreCase)) ||
            (x.LastHandle != 0 && memo.LastHandle != 0 && x.LastHandle == memo.LastHandle));

        State.DockedHistory.Insert(0, new DockedWindowMemo
        {
            LastHandle = memo.LastHandle,
            LastTitle = memo.LastTitle,
            DisplayHint = memo.DisplayHint,
            UpdatedAt = memo.UpdatedAt
        });

        const int maxHistory = 12;
        if (State.DockedHistory.Count > maxHistory)
        {
            State.DockedHistory.RemoveRange(maxHistory, State.DockedHistory.Count - maxHistory);
        }

        Save();
    }
}

