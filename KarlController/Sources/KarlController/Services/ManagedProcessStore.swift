import Foundation

actor ManagedProcessStore {
    private var daemonProcess: Process?
    private var modeProcess: Process?
    private var eyeProcess: Process?
    private var currentMode: RobotMode?

    func startDaemon(executable: URL, logURL: URL) throws {
        guard daemonProcess?.isRunning != true else { return }
        daemonProcess = try startProcess(
            executable: executable,
            arguments: [],
            currentDirectory: nil,
            logURL: logURL
        )
    }

    func startMode(
        _ mode: RobotMode,
        repositoryURL: URL,
        logURL: URL
    ) throws {
        stopMode()

        let executable: URL
        let arguments: [String]
        if mode == .greeter {
            executable = URL(fileURLWithPath: "/Users/john/venv/bin/python")
            arguments = ["-u", repositoryURL.appending(path: "reachy_greet.py").path]
        } else {
            executable = repositoryURL.appending(path: "start_karl.sh")
            arguments = mode.scriptArguments
        }

        modeProcess = try startProcess(
            executable: executable,
            arguments: arguments,
            currentDirectory: repositoryURL,
            logURL: logURL
        )
        currentMode = mode
    }

    func stopMode() {
        if let modeProcess, modeProcess.isRunning {
            modeProcess.terminate()
            modeProcess.waitUntilExit()
        }
        modeProcess = nil
        currentMode = nil
    }

    func startIdleEyes(
        color: String,
        repositoryURL: URL,
        logURL: URL
    ) throws {
        stopIdleEyes()
        eyeProcess = try startProcess(
            executable: repositoryURL.appending(path: "karlctl"),
            arguments: ["eyes-idle", color],
            currentDirectory: repositoryURL,
            logURL: logURL
        )
    }

    func stopIdleEyes() {
        if let eyeProcess, eyeProcess.isRunning {
            eyeProcess.terminate()
            eyeProcess.waitUntilExit()
        }
        eyeProcess = nil
    }

    func idleEyesAreRunning() -> Bool {
        guard eyeProcess?.isRunning == true else {
            eyeProcess = nil
            return false
        }
        return true
    }

    func activeMode() -> RobotMode? {
        guard modeProcess?.isRunning == true else {
            modeProcess = nil
            currentMode = nil
            return nil
        }
        return currentMode
    }

    private func startProcess(
        executable: URL,
        arguments: [String],
        currentDirectory: URL?,
        logURL: URL
    ) throws -> Process {
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        let log = try FileHandle(forWritingTo: logURL)
        try log.truncate(atOffset: 0)

        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = currentDirectory
        process.standardOutput = log
        process.standardError = log
        try process.run()
        return process
    }
}
