import Foundation

nonisolated struct CommandResult: Sendable {
    let exitCode: Int32
    let output: String
    let error: String

    var combinedOutput: String {
        [output, error]
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
    }
}

actor CommandRunner {
    func run(
        executable: URL,
        arguments: [String] = [],
        currentDirectory: URL? = nil,
        timeout: TimeInterval = 30
    ) throws -> CommandResult {
        let process = Process()
        let identifier = UUID().uuidString
        let outputURL = FileManager.default.temporaryDirectory
            .appending(path: "karl-command-\(identifier).out")
        let errorURL = FileManager.default.temporaryDirectory
            .appending(path: "karl-command-\(identifier).err")
        try Data().write(to: outputURL)
        try Data().write(to: errorURL)
        let outputHandle = try FileHandle(forWritingTo: outputURL)
        let errorHandle = try FileHandle(forWritingTo: errorURL)

        defer {
            try? outputHandle.close()
            try? errorHandle.close()
            try? FileManager.default.removeItem(at: outputURL)
            try? FileManager.default.removeItem(at: errorURL)
        }

        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = currentDirectory
        process.standardOutput = outputHandle
        process.standardError = errorHandle

        try process.run()
        let deadline = Date.now.addingTimeInterval(timeout)
        while process.isRunning, Date.now < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }
        if process.isRunning {
            process.terminate()
            process.waitUntilExit()
            throw CommandRunnerError.timedOut(executable.lastPathComponent, timeout)
        }

        try outputHandle.close()
        try errorHandle.close()
        let outputData = try Data(contentsOf: outputURL)
        let errorData = try Data(contentsOf: errorURL)

        return CommandResult(
            exitCode: process.terminationStatus,
            output: String(decoding: outputData, as: UTF8.self)
                .trimmingCharacters(in: .whitespacesAndNewlines),
            error: String(decoding: errorData, as: UTF8.self)
                .trimmingCharacters(in: .whitespacesAndNewlines)
        )
    }
}

nonisolated enum CommandRunnerError: LocalizedError {
    case timedOut(String, TimeInterval)

    var errorDescription: String? {
        switch self {
        case .timedOut(let command, let timeout):
            "“\(command)” did not finish within \(timeout.formatted()) seconds."
        }
    }
}
