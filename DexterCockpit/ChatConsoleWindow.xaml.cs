using System;
using System.Collections.Specialized;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using DexterCockpit.Services;
using DexterCockpit.State;

namespace DexterCockpit;

public partial class ChatConsoleWindow : Window
{
    private readonly ChatCoordinator _coordinator;
    private ChatTargetOption? _selectedTarget;

    public ChatConsoleWindow(ChatCoordinator coordinator)
    {
        InitializeComponent();
        _coordinator = coordinator ?? throw new ArgumentNullException(nameof(coordinator));

        ChatList.ItemsSource = _coordinator.Entries;
        TargetCombo.ItemsSource = _coordinator.Targets;

        _coordinator.Entries.CollectionChanged += Entries_CollectionChanged;
        _coordinator.Targets.CollectionChanged += Targets_CollectionChanged;

        if (_coordinator.Targets.Count == 0)
        {
            _coordinator.RefreshTargets();
        }

        EnsureValidSelection();
    }

    private void Entries_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        if (ChatList.Items.Count == 0)
        {
            return;
        }

        Dispatcher.BeginInvoke(new Action(() =>
        {
            var last = ChatList.Items[^1];
            ChatList.ScrollIntoView(last);
        }));
    }

    private async void BtnSend_Click(object sender, RoutedEventArgs e)
    {
        await SendAsync();
    }

    private async Task SendAsync()
    {
        var text = MessageInput.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        MessageInput.Clear();
        await _coordinator.SendAsync(text, _selectedTarget);
    }

    private void TargetCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        _selectedTarget = TargetCombo.SelectedItem as ChatTargetOption;
    }

    private void BtnRefreshTargets_Click(object sender, RoutedEventArgs e)
    {
        _coordinator.RefreshTargets();
        EnsureValidSelection();
    }

    private void Targets_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(new Action(EnsureValidSelection));
    }

    private void EnsureValidSelection()
    {
        var match = FindMatchingTarget(_selectedTarget);
        if (match != null)
        {
            TargetCombo.SelectedItem = match;
            _selectedTarget = match;
        }
        else if (_coordinator.Targets.Count > 0)
        {
            TargetCombo.SelectedIndex = 0;
            _selectedTarget = _coordinator.Targets[0];
        }
        else
        {
            TargetCombo.SelectedIndex = -1;
            _selectedTarget = null;
        }
    }

    private ChatTargetOption? FindMatchingTarget(ChatTargetOption? target)
    {
        if (target == null)
        {
            return null;
        }

        if (target.IsBroadcast)
        {
            return _coordinator.Targets.FirstOrDefault(t => t.IsBroadcast);
        }

        var agent = target.Agent;
        if (agent == null)
        {
            return null;
        }

        return _coordinator.Targets.FirstOrDefault(t => !t.IsBroadcast && t.Agent != null && string.Equals(t.Agent.TabId, agent.TabId, StringComparison.OrdinalIgnoreCase));
    }

    private async void MessageInput_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && !Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
        {
            e.Handled = true;
            await SendAsync();
        }
    }

    protected override void OnClosed(EventArgs e)
    {
        _coordinator.Entries.CollectionChanged -= Entries_CollectionChanged;
        _coordinator.Targets.CollectionChanged -= Targets_CollectionChanged;
        base.OnClosed(e);
    }
}
