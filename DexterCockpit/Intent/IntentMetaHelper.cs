using System.Globalization;
using System.Text.Json.Nodes;
using DexterCockpit.State;

namespace DexterCockpit.Intent;

internal static class IntentMetaHelper
{
    public static void ApplyDefaultCockpitMeta(JsonObject intent)
    {
        if (!intent.TryGetPropertyValue("meta", out var metaNode) || metaNode is not JsonObject metaObj)
        {
            metaObj = new JsonObject();
            intent["meta"] = metaObj;
        }

        string? explicitTarget = null;
        if (metaObj.TryGetPropertyValue("target", out var targetNode)
            && targetNode is JsonValue targetValue
            && targetValue.TryGetValue(out string? targetText)
            && !string.IsNullOrWhiteSpace(targetText))
        {
            explicitTarget = targetText;
        }

        long? handle = ExtractHandle(metaObj);
        var state = CockpitStateStore.Instance.State;
        var memo = state.DockedWindow;
        if (handle is null && memo != null)
        {
            handle = memo.LastHandle;
            metaObj["docked_hwnd"] = memo.LastHandle;
            metaObj["target_hwnd"] = memo.LastHandle;
        }

        if (handle is not null)
        {
            metaObj["hwnd"] = $"HWND:{handle.Value}";
        }

        if (!metaObj.ContainsKey("target_title"))
        {
            if (!string.IsNullOrWhiteSpace(explicitTarget))
            {
                metaObj["target_title"] = explicitTarget;
            }
            else if (!string.IsNullOrWhiteSpace(memo?.LastTitle))
            {
                metaObj["target_title"] = memo!.LastTitle;
            }
        }
    }

    private static long? ExtractHandle(JsonObject metaObj)
    {
        if (metaObj.TryGetPropertyValue("hwnd", out var hwndNode)
            && hwndNode is JsonValue hwndValue
            && hwndValue.TryGetValue(out string? hwndText)
            && !string.IsNullOrWhiteSpace(hwndText))
        {
            if (hwndText.StartsWith("HWND:", StringComparison.OrdinalIgnoreCase)
                && long.TryParse(hwndText.Substring(5), NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
            {
                return parsed;
            }
        }

        if (metaObj.TryGetPropertyValue("target_hwnd", out var targetNode)
            && targetNode is JsonValue targetValue
            && targetValue.TryGetValue<long>(out var numericHandle))
        {
            return numericHandle;
        }

        if (metaObj.TryGetPropertyValue("docked_hwnd", out var dockNode)
            && dockNode is JsonValue dockValue
            && dockValue.TryGetValue<long>(out var dockHandle))
        {
            return dockHandle;
        }

        return null;
    }
}

