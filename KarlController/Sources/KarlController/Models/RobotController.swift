import Foundation
import Observation
import SwiftUI

@MainActor
@Observable
final class RobotController {
    private let runner = CommandRunner()
    private let processes = ManagedProcessStore()
    private let daemon = DaemonClient()

    private(set) var status = RobotStatus()
    private(set) var activeMode: RobotMode?
    private(set) var isIdleBlinking = false
    private(set) var isFaceTracking = false
    private(set) var isBusy = false
    private(set) var activity = "Ready"
    private(set) var diagnosticOutput = "Run diagnostics to inspect Karl’s services and hardware."
    private(set) var cameraImage: NSImage?
    var errorMessage: String?

    let repositoryURL: URL

    private var karlctlURL: URL {
        repositoryURL.appending(path: "karlctl")
    }

    private var daemonURL: URL {
        URL(fileURLWithPath: "/Users/john/venv/bin/reachy-mini-daemon")
    }

    private var daemonLogURL: URL {
        URL(fileURLWithPath: "/tmp/karl-controller-daemon.log")
    }

    private var modeLogURL: URL {
        URL(fileURLWithPath: "/tmp/karl-controller-mode.log")
    }

    private var eyeLogURL: URL {
        URL(fileURLWithPath: "/tmp/karl-controller-eyes.log")
    }

    init() {
        repositoryURL = URL(
            fileURLWithPath: ProcessInfo.processInfo.environment["KARL_REPO"]
                ?? "/Users/john/Developer/ReachyMiniLiteLLM",
            isDirectory: true
        )
    }

    func refreshStatus() {
        perform("Refreshing status") {
            await self.loadStatus()
        }
    }

    func startRobot() {
        perform("Starting Karl") {
            try await self.ensureDaemonRunning()
            try? await Task.sleep(for: .seconds(5))
            try await self.daemon.settleAntennas()
            await self.loadStatus()
        }
    }

    func stopRobot() {
        perform("Stopping Karl") {
            await self.processes.stopMode()
            await self.processes.stopIdleEyes()
            try? await self.daemon.setFaceTracking(enabled: false)
            self.isFaceTracking = false
            try await self.stopRobotProcesses()
            try? await Task.sleep(for: .seconds(1))
            await self.loadStatus()
        }
    }

    func startMode(_ mode: RobotMode) {
        perform("Starting \(mode.title)") {
            try await self.ensureDaemonRunning()
            await self.processes.stopIdleEyes()
            self.isIdleBlinking = false
            try await self.processes.startMode(
                mode,
                repositoryURL: self.repositoryURL,
                logURL: self.modeLogURL
            )
            self.activeMode = mode
            self.activity = "\(mode.title) is running"
        }
    }

    func stopMode() {
        perform("Stopping interactive mode") {
            await self.processes.stopMode()
            try await self.daemon.settleAntennas()
            self.activeMode = nil
            self.activity = "Interactive mode stopped"
        }
    }

    func wake() {
        perform("Waking Karl") {
            try await self.daemon.wake()
            self.activity = "Wake motion started"
        }
    }

    func look(_ direction: String) {
        let poses: [String: HeadPose] = [
            "left": HeadPose(yaw: Self.radians(25)),
            "right": HeadPose(yaw: Self.radians(-25)),
            "up": HeadPose(pitch: Self.radians(-20)),
            "down": HeadPose(pitch: Self.radians(20)),
            "tilt-left": HeadPose(roll: Self.radians(18)),
            "tilt-right": HeadPose(roll: Self.radians(-18)),
            "center": HeadPose()
        ]
        guard let pose = poses[direction] else {
            errorMessage = "Unknown head direction: \(direction)"
            return
        }
        perform("Looking \(direction)") {
            try await self.daemon.goto(head: pose)
            self.activity = "Head moved \(direction)"
        }
    }

    func rotateBody(_ direction: String) {
        let yaws = [
            "left": Self.radians(35),
            "right": Self.radians(-35),
            "center": 0.0
        ]
        guard let yaw = yaws[direction] else {
            errorMessage = "Unknown body direction: \(direction)"
            return
        }
        perform("Turning body \(direction)") {
            try await self.daemon.goto(bodyYaw: yaw, duration: 0.7)
            self.activity = "Body moved \(direction)"
        }
    }

    func positionAntennas(_ position: String) {
        let positions = [
            "up": [0.6, -0.6],
            "down": [-0.6, 0.6],
            "neutral": DaemonClient.safeAntennaRest
        ]
        guard let antennas = positions[position] else {
            errorMessage = "Unknown antenna position: \(position)"
            return
        }
        perform("Moving antennas \(position)") {
            try await self.daemon.goto(antennas: antennas, duration: 0.4)
            self.activity = "Antennas moved \(position)"
        }
    }

    func setFaceTracking(_ enabled: Bool) {
        perform(enabled ? "Starting face tracking" : "Stopping face tracking") {
            try await self.daemon.setFaceTracking(enabled: enabled)
            self.isFaceTracking = enabled
            self.activity = enabled ? "Karl is following faces" : "Face tracking stopped"
        }
    }

    func playEmotion(_ name: String, title: String) {
        perform("Playing \(title)") {
            try await self.daemon.playEmotion(name)
            self.activity = "\(title) emotion started"
        }
    }

    func nod() {
        perform("Nodding") {
            for _ in 0..<2 {
                try await self.daemon.goto(
                    head: HeadPose(pitch: Self.radians(15)),
                    duration: 0.3
                )
                try await self.daemon.goto(
                    head: HeadPose(pitch: Self.radians(-5)),
                    duration: 0.3
                )
            }
            try await self.daemon.goto(head: HeadPose(), duration: 0.3)
            self.activity = "Nod complete"
        }
    }

    func shake() {
        perform("Shaking head") {
            for _ in 0..<2 {
                try await self.daemon.goto(
                    head: HeadPose(yaw: Self.radians(20)),
                    duration: 0.25
                )
                try await self.daemon.goto(
                    head: HeadPose(yaw: Self.radians(-20)),
                    duration: 0.25
                )
            }
            try await self.daemon.goto(head: HeadPose(), duration: 0.25)
            self.activity = "Head shake complete"
        }
    }

    func demo() {
        runKarlctl(["demo"], activity: "Running demo")
    }

    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            errorMessage = "Enter something for Karl to say."
            return
        }
        runKarlctl(["speak", trimmed], activity: "Speaking")
    }

    func setEyes(_ color: String) {
        perform(color == "off" ? "Turning eyes off" : "Changing eye color") {
            await self.processes.stopIdleEyes()
            self.isIdleBlinking = false
            let result = try await self.runner.run(
                executable: self.karlctlURL,
                arguments: ["eyes", color],
                currentDirectory: self.repositoryURL
            )
            guard result.exitCode == 0 else {
                throw ControllerError.commandFailed(result.combinedOutput)
            }
            self.activity = result.output
            await self.loadStatus()
        }
    }

    func blink() {
        runKarlctl(["blink", "random", "6"], activity: "Blinking eyes")
    }

    func startIdleBlinking(color: String) {
        perform("Starting periodic blinking") {
            try await self.processes.startIdleEyes(
                color: color,
                repositoryURL: self.repositoryURL,
                logURL: self.eyeLogURL
            )
            self.isIdleBlinking = true
            self.activity = "Periodic eye blinking is active"
        }
    }

    func stopIdleBlinking() {
        perform("Stopping periodic blinking") {
            await self.processes.stopIdleEyes()
            self.isIdleBlinking = false
            self.activity = "Periodic eye blinking stopped"
        }
    }

    func captureCamera() {
        perform("Capturing camera image") {
            let outputURL = FileManager.default.temporaryDirectory
                .appending(path: "karl-controller-camera.jpg")
            let result = try await self.runner.run(
                executable: self.karlctlURL,
                arguments: ["see", "--out", outputURL.path],
                currentDirectory: self.repositoryURL
            )
            guard result.exitCode == 0, let image = NSImage(contentsOf: outputURL) else {
                throw ControllerError.commandFailed(result.combinedOutput)
            }
            self.cameraImage = image
            self.activity = "Camera image updated"
        }
    }

    func runDiagnostics() {
        perform("Running diagnostics") {
            let statusResult = try await self.runner.run(
                executable: self.karlctlURL,
                arguments: ["status"],
                currentDirectory: self.repositoryURL
            )
            let processResult = try await self.runner.run(
                executable: URL(fileURLWithPath: "/bin/ps"),
                arguments: ["-ax", "-o", "pid=,command="]
            )
            let robotProcesses = processResult.output
                .split(separator: "\n")
                .filter {
                    $0.localizedStandardContains("reachy-mini-daemon")
                        || $0.localizedStandardContains("reachy_wake.py")
                        || $0.localizedStandardContains("reachy_listen.py")
                        || $0.localizedStandardContains("reachy_greet.py")
                        || $0.localizedStandardContains("reachy_gpp.py")
                }
                .joined(separator: "\n")
            let deviceNames = try? FileManager.default.contentsOfDirectory(atPath: "/dev")
            let serialPorts = (deviceNames ?? [])
                .filter { $0.hasPrefix("cu.usbmodem") }
                .sorted()
                .map { "/dev/\($0)" }
                .joined(separator: "\n")
            let daemonLog = try await self.tailLog(self.daemonLogURL)
            let modeLog = try await self.tailLog(self.modeLogURL)

            self.diagnosticOutput = """
            STATUS
            \(statusResult.combinedOutput)

            SERIAL PORTS
            \(serialPorts.isEmpty ? "None detected" : serialPorts)

            ROBOT PROCESSES
            \(robotProcesses.isEmpty ? "None running" : robotProcesses)

            DAEMON LOG
            \(daemonLog)

            INTERACTIVE MODE LOG
            \(modeLog)
            """
            await self.loadStatus()
            self.activity = "Diagnostics complete"
        }
    }

    private func perform(
        _ pendingActivity: String,
        operation: @escaping @MainActor () async throws -> Void
    ) {
        guard !isBusy else { return }
        isBusy = true
        activity = pendingActivity
        errorMessage = nil

        Task {
            defer { isBusy = false }
            do {
                try await operation()
            } catch {
                errorMessage = error.localizedDescription
                activity = "Action failed"
            }
        }
    }

    private func runKarlctl(_ arguments: [String], activity pendingActivity: String) {
        perform(pendingActivity) {
            let result = try await self.runner.run(
                executable: self.karlctlURL,
                arguments: arguments,
                currentDirectory: self.repositoryURL
            )
            guard result.exitCode == 0 else {
                throw ControllerError.commandFailed(result.combinedOutput)
            }
            self.activity = result.output.isEmpty ? "Command complete" : result.output
            await self.loadStatus()
        }
    }

    private func ensureDaemonRunning() async throws {
        await loadStatus()
        guard !status.daemon else { return }
        guard FileManager.default.isExecutableFile(atPath: daemonURL.path) else {
            throw ControllerError.missingExecutable(daemonURL.path)
        }
        try await processes.startDaemon(executable: daemonURL, logURL: daemonLogURL)
        try await daemon.waitUntilReady()
    }

    private func loadStatus() async {
        do {
            let result = try await runner.run(
                executable: karlctlURL,
                arguments: ["status"],
                currentDirectory: repositoryURL
            )
            if let data = result.output
                .split(separator: " ", maxSplits: 1)
                .last?
                .data(using: .utf8),
               let json = try JSONSerialization.jsonObject(with: data) as? [String: Bool] {
                status = RobotStatus(
                    daemon: json["daemon"] ?? false,
                    eyes: json["eyes"] ?? false,
                    camera: json["camera"] ?? false
                )
            }
            activeMode = await processes.activeMode()
            isIdleBlinking = await processes.idleEyesAreRunning()
            if !isBusy {
                activity = status.daemon ? "Karl is online" : "Karl is offline"
            }
        } catch {
            status = RobotStatus()
            errorMessage = error.localizedDescription
        }
    }

    private func stopRobotProcesses() async throws {
        let result = try await runner.run(
            executable: URL(fileURLWithPath: "/bin/ps"),
            arguments: ["-ax", "-o", "pid=,command="]
        )
        let processMarkers = [
            daemonURL.path,
            repositoryURL.appending(path: "reachy_wake.py").path,
            repositoryURL.appending(path: "reachy_listen.py").path,
            repositoryURL.appending(path: "reachy_greet.py").path,
            repositoryURL.appending(path: "reachy_gpp.py").path
        ]
        let pids = result.output.split(separator: "\n").compactMap { line -> String? in
            guard processMarkers.contains(where: { line.contains($0) }) else { return nil }
            return line.split(whereSeparator: \.isWhitespace).first.map(String.init)
        }
        for pid in Set(pids) {
            _ = try await runner.run(
                executable: URL(fileURLWithPath: "/bin/kill"),
                arguments: ["-TERM", pid]
            )
        }
        activeMode = nil
    }

    private func tailLog(_ url: URL) async throws -> String {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return "No log file."
        }
        let result = try await runner.run(
            executable: URL(fileURLWithPath: "/usr/bin/tail"),
            arguments: ["-n", "40", url.path]
        )
        return result.combinedOutput.isEmpty ? "Log is empty." : result.combinedOutput
    }

    nonisolated private static func radians(_ degrees: Double) -> Double {
        degrees * .pi / 180
    }
}

enum ControllerError: LocalizedError {
    case commandFailed(String)
    case missingExecutable(String)

    var errorDescription: String? {
        switch self {
        case .commandFailed(let output):
            output.isEmpty ? "The robot command failed." : output
        case .missingExecutable(let path):
            "Required executable not found: \(path)"
        }
    }
}
