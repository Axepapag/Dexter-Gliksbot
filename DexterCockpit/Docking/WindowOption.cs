using System;
using DexterCockpit.Interop;
using DexterCockpit.State;

namespace DexterCockpit.Docking;

/// <summary>
/// Represents a selectable window option backed by either a live hwnd or a history entry.
/// </summary>
public sealed class WindowOption
{
    public WindowOption(string display, IntPtr handle, bool isHistory, string? title, string? processName)
    {
        Display = display;
        Handle = handle;
        IsHistory = isHistory;
        Title = title;
        ProcessName = processName;
    }

    public string Display { get; }
    public IntPtr Handle { get; }
    public bool IsHistory { get; }
    public string? Title { get; }
    public string? ProcessName { get; }

    public string DisplayTitle => Title ?? Display;
    public string SourceLabel => IsHistory ? "History" : "Live";

    public bool Matches(WindowOption other)
    {
        if (Handle != IntPtr.Zero && other.Handle != IntPtr.Zero)
        {
            return Handle == other.Handle;
        }
        return string.Equals(DisplayTitle, other.DisplayTitle, StringComparison.OrdinalIgnoreCase);
    }

    public IntPtr ResolveHandle()
    {
        if (Handle != IntPtr.Zero && NativeMethods.IsWindow(Handle))
        {
            return Handle;
        }
        return IntPtr.Zero;
    }

    public static WindowOption FromCurrent(WindowCatalogEntry entry)
        => new(entry.Display, entry.Handle, false, entry.Title, entry.ProcessName);

    public static WindowOption FromHistory(DockedWindowMemo memo)
        => new($"[History] {memo.LastTitle}", IntPtr.Zero, true, memo.LastTitle, null);
}
