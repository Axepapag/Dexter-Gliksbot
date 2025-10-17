using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Interop;
using DexterCockpit.Interop;

namespace DexterCockpit.Docking;

public sealed class DockHostControl : HwndHost
{
    private IntPtr _hostHandle;
    private DockedWindowSnapshot? _snapshot;

    public IntPtr DockedHandle => _snapshot?.Handle ?? IntPtr.Zero;

    public string? DockedTitle => _snapshot?.Title;

    public bool HasDockedWindow => DockedHandle != IntPtr.Zero;

    public event EventHandler? DockedWindowChanged;

    protected override HandleRef BuildWindowCore(HandleRef hwndParent)
    {
        _hostHandle = NativeMethods.CreateWindowEx(
            0,
            "Static",
            string.Empty,
            NativeMethods.WS_CHILD | NativeMethods.WS_VISIBLE,
            0,
            0,
            100,
            100,
            hwndParent.Handle,
            IntPtr.Zero,
            IntPtr.Zero,
            IntPtr.Zero);

        if (_hostHandle == IntPtr.Zero)
        {
            throw new InvalidOperationException("Failed to create dock host window.");
        }

        return new HandleRef(this, _hostHandle);
    }

    protected override void DestroyWindowCore(HandleRef hwnd)
    {
        if (!NativeMethods.DestroyWindow(hwnd.Handle))
        {
            Marshal.ThrowExceptionForHR(Marshal.GetHRForLastWin32Error());
        }
    }

    protected override void OnWindowPositionChanged(Rect rcBoundingBox)
    {
        base.OnWindowPositionChanged(rcBoundingBox);
        var (width, height) = GetHostDimensions();
        ResizeDocked(width, height);
    }

    public DockAttachResult Attach(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero)
        {
            return DockAttachResult.Failure("Invalid window handle.");
        }

        if (!NativeMethods.IsWindow(hwnd))
        {
            return DockAttachResult.Failure("The selected window is no longer available.");
        }

        if (hwnd == _hostHandle)
        {
            return DockAttachResult.Failure("Cannot dock the host window.");
        }

        if (DockedHandle == hwnd)
        {
            var (_, title) = EnsureSnapshotTitle(hwnd);
            return DockAttachResult.Ok(title);
        }

        Detach();

        var snapshotOpt = DockedWindowSnapshot.Capture(hwnd);
        if (snapshotOpt is null)
        {
            return DockAttachResult.Failure("Unable to capture window metadata.");
        }
        var snapshot = snapshotOpt.Value;

        // Convert to child window style to embed.
        var style = NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GWL_STYLE);
        var newStyle = (style.ToInt64()
            & ~(NativeMethods.WS_CAPTION
                | NativeMethods.WS_THICKFRAME
                | NativeMethods.WS_SYSMENU
                | NativeMethods.WS_MINIMIZE
                | NativeMethods.WS_MAXIMIZE
                | NativeMethods.WS_POPUP))
            | NativeMethods.WS_CHILD;
        NativeMethods.SetWindowLongPtr(hwnd, NativeMethods.GWL_STYLE, new IntPtr(newStyle));

        var exStyle = NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE);
        var newExStyle = exStyle.ToInt64() & ~(NativeMethods.WS_EX_APPWINDOW);
        NativeMethods.SetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE, new IntPtr(newExStyle));

        if (NativeMethods.SetParent(hwnd, _hostHandle) == IntPtr.Zero && Marshal.GetLastWin32Error() != 0)
        {
            RestoreWindowStyles(hwnd, snapshot);
            return DockAttachResult.Failure("Failed to re-parent window.");
        }

        _snapshot = snapshot;
        var (width, height) = GetHostDimensions();
        ResizeDocked(width, height);
        NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
        NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, 0, 0, width, height,
            NativeMethods.SWP_ASYNCWINDOWPOS | NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);

        DockedWindowChanged?.Invoke(this, EventArgs.Empty);
        return DockAttachResult.Ok(snapshot.Title);
    }

    public void Detach()
    {
        if (_snapshot is null)
        {
            return;
        }

        var snapshot = _snapshot.Value;
        var handle = snapshot.Handle;
        if (NativeMethods.IsWindow(handle))
        {
            NativeMethods.SetParent(handle, snapshot.OriginalParent);
            RestoreWindowStyles(handle, snapshot);

            if (snapshot.Placement.HasValue)
            {
                var placement = snapshot.Placement.Value;
                placement.Length = Marshal.SizeOf<NativeMethods.WINDOWPLACEMENT>();
                NativeMethods.SetWindowPlacement(handle, ref placement);
            }

            if (snapshot.OriginalRect is { } rect)
            {
                NativeMethods.SetWindowPos(
                    handle,
                    IntPtr.Zero,
                    rect.Left,
                    rect.Top,
                    rect.Width,
                    rect.Height,
                    NativeMethods.SWP_ASYNCWINDOWPOS | NativeMethods.SWP_NOZORDER);
            }
        }

        _snapshot = null;
        DockedWindowChanged?.Invoke(this, EventArgs.Empty);
    }

    private void RestoreWindowStyles(IntPtr hwnd, DockedWindowSnapshot snapshot)
    {
        NativeMethods.SetWindowLongPtr(hwnd, NativeMethods.GWL_STYLE, snapshot.OriginalStyle);
        NativeMethods.SetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE, snapshot.OriginalExStyle);
    }

    public (bool ok, string? actualTitle) EnsureSnapshotTitle(IntPtr hwnd)
    {
        if (!NativeMethods.IsWindow(hwnd))
        {
            return (false, null);
        }

        var sb = new StringBuilder(512);
        NativeMethods.GetWindowText(hwnd, sb, sb.Capacity);
        var title = sb.ToString();
        if (_snapshot.HasValue)
        {
            _snapshot = _snapshot.Value with { Title = title };
        }

        return (true, title);
    }

    internal bool TryGetSnapshot(out DockedWindowSnapshot snapshot)
    {
        if (_snapshot is null)
        {
            snapshot = default;
            return false;
        }

        snapshot = _snapshot.Value;
        return true;
    }

    private (int width, int height) GetHostDimensions()
    {
        var width = (int)Math.Round(ActualWidth);
        var height = (int)Math.Round(ActualHeight);
        if (width <= 0 || height <= 0)
        {
            width = (int)Math.Round(RenderSize.Width);
            height = (int)Math.Round(RenderSize.Height);
        }
        return (Math.Max(width, 0), Math.Max(height, 0));
    }

    private void ResizeDocked(int width, int height)
    {
        if (_snapshot is null)
        {
            return;
        }

        if (!NativeMethods.IsWindow(_snapshot.Value.Handle))
        {
            Detach();
            return;
        }

        NativeMethods.MoveWindow(_snapshot.Value.Handle, 0, 0, Math.Max(0, width), Math.Max(0, height), true);
    }

    internal bool TryGetDockedBounds(out NativeMethods.RECT rect)
    {
        rect = default;
        if (_snapshot is null)
        {
            return false;
        }

        var hwnd = _snapshot.Value.Handle;
        if (!NativeMethods.IsWindow(hwnd))
        {
            return false;
        }

        return NativeMethods.GetWindowRect(hwnd, out rect);
    }

    public void FocusDockedWindow()
    {
        if (_snapshot is null)
        {
            return;
        }

        var handle = _snapshot.Value.Handle;
        if (NativeMethods.IsWindow(handle))
        {
            NativeMethods.SetForegroundWindow(handle);
        }
    }

    private static string GetTitle(IntPtr hwnd)
    {
        var sb = new StringBuilder(512);
        NativeMethods.GetWindowText(hwnd, sb, sb.Capacity);
        return sb.ToString();
    }
}

internal readonly record struct DockedWindowSnapshot(
    IntPtr Handle,
    IntPtr OriginalParent,
    IntPtr OriginalStyle,
    IntPtr OriginalExStyle,
    NativeMethods.RECT? OriginalRect,
    NativeMethods.WINDOWPLACEMENT? Placement,
    string Title)
{
    public static DockedWindowSnapshot? Capture(IntPtr hwnd)
    {
        if (!NativeMethods.IsWindow(hwnd))
        {
            return null;
        }

        var parent = NativeMethods.GetParent(hwnd);
        var style = NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GWL_STYLE);
        var exStyle = NativeMethods.GetWindowLongPtr(hwnd, NativeMethods.GWL_EXSTYLE);
        NativeMethods.RECT? rect = null;
        if (NativeMethods.GetWindowRect(hwnd, out var r))
        {
            rect = r;
        }

        NativeMethods.WINDOWPLACEMENT? placement = null;
        var wp = new NativeMethods.WINDOWPLACEMENT { Length = Marshal.SizeOf<NativeMethods.WINDOWPLACEMENT>() };
        if (NativeMethods.GetWindowPlacement(hwnd, ref wp))
        {
            placement = wp;
        }

        var title = GetTitle(hwnd);
        return new DockedWindowSnapshot(hwnd, parent, style, exStyle, rect, placement, title);
    }

    private static string GetTitle(IntPtr hwnd)
    {
        var sb = new StringBuilder(512);
        NativeMethods.GetWindowText(hwnd, sb, sb.Capacity);
        return sb.ToString();
    }
}

public readonly record struct DockAttachResult(bool Success, string? Title, string? Reason)
{
    public static DockAttachResult Failure(string reason) => new(false, null, reason);

    public static DockAttachResult Ok(string? title) => new(true, title, null);
}

