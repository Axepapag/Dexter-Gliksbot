using System;
using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.Linq;
using System.Threading.Tasks;
using DexterCockpit.State;

namespace DexterCockpit.Services;

public sealed class ChatCoordinator : IDisposable
{
    private readonly AgentTabsControl _agentTabs;
    private bool _disposed;

    public ChatCoordinator(AgentTabsControl agentTabs)
    {
        _agentTabs = agentTabs ?? throw new ArgumentNullException(nameof(agentTabs));
        Entries = new ObservableCollection<ChatEntry>();
        Targets = new ObservableCollection<ChatTargetOption>();

        _agentTabs.ChatMessageRaised += OnChatMessageRaised;
        _agentTabs.Tabs.CollectionChanged += OnTabsCollectionChanged;
        _agentTabs.TabsMetadataChanged += OnTabsMetadataChanged;

        RefreshTargets();
    }

    public ObservableCollection<ChatEntry> Entries { get; }
    public ObservableCollection<ChatTargetOption> Targets { get; }

    public void AddSystemMessage(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return;
        }

        AppendEntry(new ChatEntry("System", string.Empty, message, DateTimeOffset.UtcNow));
    }

    public async Task SendAsync(string text, ChatTargetOption? target = null)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        var selected = EnsureTarget(target);

        if (selected.IsBroadcast)
        {
            var tabs = _agentTabs.Tabs.ToList();
            if (tabs.Count == 0)
            {
                return;
            }
            foreach (var tab in tabs)
            {
                await _agentTabs.SendNaturalLanguageAsync(tab, text, "Broadcast");
            }
        }
        else if (selected.Agent != null)
        {
            await _agentTabs.SendNaturalLanguageAsync(selected.Agent, text, "Chat");
        }
    }

    public void RefreshTargets()
    {
        Targets.Clear();
        Targets.Add(ChatTargetOption.Broadcast());
        foreach (var tab in _agentTabs.Tabs)
        {
            Targets.Add(ChatTargetOption.ForAgent(tab));
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        _agentTabs.ChatMessageRaised -= OnChatMessageRaised;
        _agentTabs.Tabs.CollectionChanged -= OnTabsCollectionChanged;
        _agentTabs.TabsMetadataChanged -= OnTabsMetadataChanged;
    }

    private ChatTargetOption EnsureTarget(ChatTargetOption? target)
    {
        if (target != null)
        {
            return target;
        }

        if (Targets.Count == 0)
        {
            RefreshTargets();
        }

        return Targets.FirstOrDefault() ?? ChatTargetOption.Broadcast();
    }

    private void OnChatMessageRaised(object? sender, ChatMessageEventArgs e)
    {
        var from = e.Direction == ChatMessageDirection.Outgoing ? "You" : e.Tab.DisplayName;
        var to = e.Direction == ChatMessageDirection.Outgoing ? e.Tab.DisplayName : "You";
        AppendEntry(new ChatEntry(from, to, e.Message, DateTimeOffset.UtcNow));
    }

    private void AppendEntry(ChatEntry entry)
    {
        Entries.Add(entry);
        const int maxEntries = 400;
        while (Entries.Count > maxEntries)
        {
            Entries.RemoveAt(0);
        }
    }

    private void OnTabsCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        RefreshTargets();
    }

    private void OnTabsMetadataChanged(object? sender, EventArgs e)
    {
        RefreshTargets();
    }
}
