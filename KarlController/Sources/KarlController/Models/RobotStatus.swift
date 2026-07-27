import Foundation

struct RobotStatus: Sendable {
    var daemon = false
    var eyes = false
    var camera = false

    var isOnline: Bool {
        daemon
    }
}

enum RobotMode: String, CaseIterable, Identifiable, Sendable {
    case wakeWord
    case continuous
    case greeter
    case gpp

    var id: Self { self }

    var title: String {
        switch self {
        case .wakeWord: "Wake Word"
        case .continuous: "Conversation"
        case .greeter: "Visitor Greeter"
        case .gpp: "GPP"
        }
    }

    var subtitle: String {
        switch self {
        case .wakeWord: "Wait for “Hey Karl”"
        case .continuous: "Always listen and respond"
        case .greeter: "Greet people seen by the camera"
        case .gpp: "Genuine People Personality"
        }
    }

    var systemImage: String {
        switch self {
        case .wakeWord: "waveform.badge.mic"
        case .continuous: "bubble.left.and.bubble.right"
        case .greeter: "person.crop.rectangle"
        case .gpp: "sparkles"
        }
    }

    nonisolated var scriptArguments: [String] {
        switch self {
        case .wakeWord: ["wake"]
        case .continuous: ["listen"]
        case .greeter, .gpp: []
        }
    }
}

enum ControllerSection: String, CaseIterable, Identifiable {
    case overview
    case interact
    case diagnostics

    var id: Self { self }

    var title: String {
        switch self {
        case .overview: "Overview"
        case .interact: "Interact"
        case .diagnostics: "Diagnostics"
        }
    }

    var systemImage: String {
        switch self {
        case .overview: "gauge.with.dots.needle.67percent"
        case .interact: "gamecontroller"
        case .diagnostics: "stethoscope"
        }
    }
}
