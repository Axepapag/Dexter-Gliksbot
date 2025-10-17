using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using DexterCockpit.Interop;

namespace DexterCockpit.Docking;

public sealed record WindowCatalogEntry(IntPtr Handle, string Title, uint ProcessId, string? ProcessName)
{
    public string Display => string.IsNullOrWhiteSpace(ProcessName)
        ? Title
        : $"{Title} ({ProcessName})";
}

internal static class WindowCatalog
{
    public static IReadOnlyList<WindowCatalogEntry> EnumerateTopLevelWindows(IntPtr excludeHandle)
    {
        var results = new List<WindowCatalogEntry>();

        bool Callback(IntPtr hWnd, IntPtr lParam)
        {
            if (hWnd == IntPtr.Zero || hWnd == excludeHandle)
                return true;

            if (!NativeMethods.IsWindowVisible(hWnd))
                return true;

            var length = NativeMethods.GetWindowTextLength(hWnd);
            if (length == 0)
                return true;

            var sb = new System.Text.StringBuilder(length + 1);
            NativeMethods.GetWindowText(hWnd, sb, sb.Capacity);
            var title = sb.ToString().Trim();
            if (string.IsNullOrWhiteSpace(title))
                return true;

            NativeMethods.GetWindowThreadProcessId(hWnd, out var processId);
            string? processName = null;
            try
            {
                if (processId != 0)
                {
                    using var proc = Process.GetProcessById((int)processId);
                    processName = proc.ProcessName;
                }
            }
            catch
            {
                // ignore access failures
            }

            results.Add(new WindowCatalogEntry(hWnd, title, processId, processName));
            return true;
        }

        NativeMethods.EnumWindows(Callback, IntPtr.Zero);
        results.Sort((a, b) => string.Compare(a.Title, b.Title, StringComparison.OrdinalIgnoreCase));
        return results;
    }
}
