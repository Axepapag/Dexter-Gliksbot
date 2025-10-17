using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using DexterCockpit.Docking;
using DexterCockpit.Interop;
using DexterCockpit.Services;
using DexterCockpit.State;

namespace DexterCockpit;

public partial class MainWindow : Window
{
    private readonly CockpitStateStore stateStore = CockpitStateStore.Instance;
    private readonly WindowInteropHelper interopHelper;
    private readonly AgentTabsControl agentTabs = new();
    private readonly PanicHotkeyManager panicHotkey = new();
    private bool panicTriggered;
    private readonly AppConfiguration appConfig = AppConfiguration.Instance;
    private string lastConnectionStatus = string.Empty;
    private readonly ObservableCollection<WindowOption> windowOptions = new();
    private readonly ChatCoordinator chatCoordinator;
    private ChatConsoleWindow? chatWindow;

    public MainWindow()
    {
        InitializeComponent();
        interopHelper = new WindowInteropHelper(this);

        AgentPanelHost.Content = agentTabs;
        chatCoordinator = new ChatCoordinator(agentTabs);
        WindowCombo.ItemsSource = windowOptions;
        WindowCombo.KeyDown += WindowCombo_KeyDown;

        BtnRefreshWindows.Click += (_, __) => RefreshWindowList();
        BtnDockSelected.Click += (_, __) => DockSelectedWindow();
        BtnWindowBrowser.Click += (_, __) => OpenWindowBrowser();
        BtnDetach.Click += (_, __) => DetachDockedWindow();
        BtnEndpoints.Click += (_, __) => ShowEndpointsDialog();
        BtnPanic.Click += (_, __) => TriggerPanic();
        BtnChatConsole.Click += (_, __) => ShowChatConsole();
        BtnAddAgentTab.Click += (_, __) =>
        {
            agentTabs.AddTab();
        };

        agentTabs.AttachDockHost(DockHost);
        agentTabs.ConnectionStatusChanged += OnConnectionStatusChanged;

        DockHost.DockedWindowChanged += (_, __) => OnDockedWindowChanged();

        Loaded += OnLoaded;
        Closed += OnClosed;
    }

    private void OnLoaded(object? sender, RoutedEventArgs e)
    {
        PolicyStatus.Text = "Policy: (loading...)";
        UpdateDockUi();
        RefreshWindowList();
        lastConnectionStatus = "WS: waiting for connection...";
        UpdateEndpointStatus();
        try
        {
            panicHotkey.Register(this, ModifierKeys.Control | ModifierKeys.Alt, Key.P, TriggerPanic);
        }
        catch (Exception ex)
        {
            lastConnectionStatus = $"Panic hotkey unavailable: {ex.Message}";
            UpdateEndpointStatus();
        }
    }

    private void OnClosed(object? sender, EventArgs e)
    {
        chatCoordinator.Dispose();
        panicHotkey.Dispose();
        if (chatWindow != null)
        {
            chatWindow.Closed -= ChatWindow_Closed;
            chatWindow.Close();
            chatWindow = null;
        }
        DockHost.Detach();
    }

    private void OnDockedWindowChanged()
    {
        UpdateDockUi();
        RefreshWindowList();
    }

    private IReadOnlyList<WindowOption> GetWindowOptionsSnapshot()
    {
        var list = new List<WindowOption>();
        var currentWindows = WindowCatalog.EnumerateTopLevelWindows(interopHelper.Handle);
        foreach (var entry in currentWindows)
        {
            list.Add(WindowOption.FromCurrent(entry));
        }

        var history = stateStore.State.DockedHistory ?? new List<DockedWindowMemo>();
        foreach (var memo in history)
        {
            if (!string.IsNullOrWhiteSpace(memo.LastTitle))
            {
                list.Add(WindowOption.FromHistory(memo));
            }
        }

        return list;
    }

    private void RefreshWindowList()
    {
        var selected = WindowCombo.SelectedItem as WindowOption;
        var typedText = WindowCombo.Text;

        var snapshot = GetWindowOptionsSnapshot();
        windowOptions.Clear();
        foreach (var option in snapshot)
        {
            windowOptions.Add(option);
        }

        if (selected != null)
        {
            var match = windowOptions.FirstOrDefault(o => o.Matches(selected));
            if (match != null)
            {
                WindowCombo.SelectedItem = match;
            }
        }

        if (!string.IsNullOrWhiteSpace(typedText) && WindowCombo.SelectedItem == null)
        {
            WindowCombo.Text = typedText;
        }
    }

    private void DockSelectedWindow()
    {
        IntPtr handle = IntPtr.Zero;
        string? title = null;
        if (WindowCombo.SelectedItem is WindowOption option)
        {
            handle = option.ResolveHandle();
            title = option.DisplayTitle;
            if (handle == IntPtr.Zero && option.IsHistory && !string.IsNullOrWhiteSpace(option.Title))
            {
                handle = FindWindowByTitle(option.Title);
            }
        }
        else if (!string.IsNullOrWhiteSpace(WindowCombo.Text))
        {
            title = WindowCombo.Text.Trim();
            handle = FindWindowByTitle(title);
        }

        if (handle == IntPtr.Zero)
        {
            MessageBox.Show(this, "Window not found. Refresh the list and try again.", "Dexter", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        AttachWindowHandle(handle, title);
    }

    private IntPtr FindWindowByTitle(string? title)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            return IntPtr.Zero;
        }
        var windows = WindowCatalog.EnumerateTopLevelWindows(interopHelper.Handle);
        var match = windows.FirstOrDefault(w => string.Equals(w.Title, title, StringComparison.OrdinalIgnoreCase));
        if (match != null)
        {
            return match.Handle;
        }
        match = windows.FirstOrDefault(w => w.Title.IndexOf(title, StringComparison.OrdinalIgnoreCase) >= 0);
        return match?.Handle ?? IntPtr.Zero;
    }

    private void OpenWindowBrowser()
    {
        var dialog = new WindowPickerDialog(GetWindowOptionsSnapshot)
        {
            Owner = this
        };

        if (dialog.ShowDialog() == true && dialog.SelectedOption is not null)
        {
            var option = dialog.SelectedOption;
            var handle = option.ResolveHandle();
            var title = option.DisplayTitle;

            if (handle == IntPtr.Zero && !string.IsNullOrWhiteSpace(option.Title))
            {
                handle = FindWindowByTitle(option.Title);
                title = option.Title;
            }

            if (handle == IntPtr.Zero)
            {
                MessageBox.Show(this,
                    "Window is no longer available. Refresh the list and try again.",
                    "Dexter",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                RefreshWindowList();
                return;
            }

            AttachWindowHandle(handle, title);
        }
    }

    private void ShowChatConsole()
    {
        if (chatWindow != null)
        {
            if (chatWindow.IsVisible)
            {
                chatWindow.Activate();
                return;
            }

            chatWindow.Closed -= ChatWindow_Closed;
            chatWindow = null;
        }

        chatWindow = new ChatConsoleWindow(chatCoordinator)
        {
            Owner = this
        };
        chatWindow.Closed += ChatWindow_Closed;
        chatWindow.Show();
    }

    private void ChatWindow_Closed(object? sender, EventArgs e)
    {
        if (chatWindow != null)
        {
            chatWindow.Closed -= ChatWindow_Closed;
            chatWindow = null;
        }
    }

    private void AttachWindowHandle(IntPtr hwnd, string? titleOverride = null)
    {
        var result = DockHost.Attach(hwnd);
        if (!result.Success)
        {
            DockStatus.Text = $"Dock failed: {result.Reason}";
            MessageBox.Show(this, result.Reason ?? "Could not dock window.", "Docking failed", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        var title = titleOverride ?? result.Title ?? "(untitled)";
        stateStore.UpdateDocked(hwnd, title, title);
        DockPlaceholder.Visibility = Visibility.Collapsed;
        DockStatus.Text = $"Docked: {title}";
        DockInfoBadge.Visibility = Visibility.Visible;
        DockInfoTitle.Text = $"{title} (HWND 0x{hwnd.ToInt64():X})";
        chatCoordinator.AddSystemMessage($"Docked window: {title}");
        FlashDockHighlight();
        RefreshWindowList();
    }

    private void DetachDockedWindow()
    {
        if (!DockHost.HasDockedWindow)
        {
            DockStatus.Text = "No docked window.";
            return;
        }

        DockHost.Detach();
        stateStore.ClearDocked();
        DockStatus.Text = "Window detached.";
        DockInfoBadge.Visibility = Visibility.Collapsed;
        DockGlow.Visibility = Visibility.Collapsed;
        chatCoordinator.AddSystemMessage("Docked window detached.");
    }

    private void FlashDockHighlight()
    {
        DockGlow.Visibility = Visibility.Visible;
        _ = Task.Delay(800).ContinueWith(_ => Dispatcher.Invoke(() => DockGlow.Visibility = Visibility.Collapsed));
    }

    private void TriggerPanic()
    {
        if (panicTriggered)
        {
            return;
        }
        panicTriggered = true;
        panicHotkey.Unregister();
        Application.Current.Shutdown();
    }

    private void UpdateEndpointStatus()
    {
        var message = $"HTTP: {appConfig.DexterHttpUrl} | WS: {appConfig.DexterWsUrl}";
        if (!string.IsNullOrWhiteSpace(lastConnectionStatus))
        {
            message += $" | {lastConnectionStatus}";
        }
        EndpointStatus.Text = message;
    }

    private void ShowEndpointsDialog()
    {
        var dialog = new EndpointsDialog { Owner = this };
        dialog.ShowDialog();
    }

    private void OnConnectionStatusChanged(object? sender, string status)
    {
        lastConnectionStatus = status;
        Dispatcher.Invoke(UpdateEndpointStatus);
    }

    private void UpdateDockUi()
    {
        if (DockHost.HasDockedWindow && DockHost.TryGetSnapshot(out var snapshot))
        {
            var title = snapshot.Title ?? "(untitled)";
            DockStatus.Text = $"Docked: {title}";
            DockInfoBadge.Visibility = Visibility.Visible;
            DockInfoTitle.Text = $"{title} (HWND 0x{snapshot.Handle.ToInt64():X})";
        }
        else
        {
            DockStatus.Text = "No window docked.";
            DockInfoBadge.Visibility = Visibility.Collapsed;
            DockGlow.Visibility = Visibility.Collapsed;
        }
    }

    private void WindowCombo_KeyDown(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            DockSelectedWindow();
        }
    }

}
