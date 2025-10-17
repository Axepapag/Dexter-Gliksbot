using System;

namespace DexterCockpit.State;

public sealed record ChatEntry(string Sender, string Target, string Message, DateTimeOffset Timestamp)
{
    public string Display =>
        string.IsNullOrWhiteSpace(Target)
            ? $"{Timestamp:HH:mm} {Sender}: {Message}"
            : $"{Timestamp:HH:mm} {Sender} -> {Target}: {Message}";
}

public sealed class ChatTargetOption
{
    private ChatTargetOption(string label, AgentTabViewModel? agent, bool isBroadcast)
    {
        Label = label;
        Agent = agent;
        IsBroadcast = isBroadcast;
    }

    public string Label { get; }
    public AgentTabViewModel? Agent { get; }
    public bool IsBroadcast { get; }

    public static ChatTargetOption Broadcast() => new("All Agents", null, true);

    public static ChatTargetOption ForAgent(AgentTabViewModel agent) =>
        new(agent.DisplayName, agent, false);
}
