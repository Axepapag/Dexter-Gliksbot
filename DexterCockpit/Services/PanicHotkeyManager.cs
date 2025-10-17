using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;

namespace DexterCockpit.Services;

public sealed class PanicHotkeyManager : IDisposable
{
    private const int HotkeyId = 0xB0C1;
    private const int WM_HOTKEY = 0x0312;

    private HwndSource? _source;
    private IntPtr _handle;
    private Action? _callback;
    private bool _registered;

    public void Register(Window window, ModifierKeys modifiers, Key key, Action callback)
    {
        Unregister();

        _callback = callback ?? throw new ArgumentNullException(nameof(callback));
        var helper = new WindowInteropHelper(window);
        _handle = helper.EnsureHandle();
        _source = HwndSource.FromHwnd(_handle);
        _source?.AddHook(WndProc);

        var modFlags = GetModifierFlags(modifiers);
        var virtualKey = (uint)KeyInterop.VirtualKeyFromKey(key);
        if (!RegisterHotKey(_handle, HotkeyId, modFlags, virtualKey))
        {
            throw new InvalidOperationException("Unable to register panic hotkey.");
        }

        _registered = true;
    }

    public void Unregister()
    {
        if (_registered && _handle != IntPtr.Zero)
        {
            UnregisterHotKey(_handle, HotkeyId);
            _registered = false;
        }
        if (_source != null)
        {
            _source.RemoveHook(WndProc);
            _source = null;
        }
        _handle = IntPtr.Zero;
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WM_HOTKEY && wParam == (IntPtr)HotkeyId)
        {
            _callback?.Invoke();
            handled = true;
        }
        return IntPtr.Zero;
    }

    private static uint GetModifierFlags(ModifierKeys modifiers)
    {
        uint flags = 0;
        if (modifiers.HasFlag(ModifierKeys.Alt)) flags |= 0x0001;
        if (modifiers.HasFlag(ModifierKeys.Control)) flags |= 0x0002;
        if (modifiers.HasFlag(ModifierKeys.Shift)) flags |= 0x0004;
        if (modifiers.HasFlag(ModifierKeys.Windows)) flags |= 0x0008;
        return flags;
    }

    public void Dispose()
    {
        Unregister();
    }

    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);
}
