import Foundation
import Testing
@testable import KarlController

struct CommandRunnerTests {
    @Test("Commands producing more than a pipe buffer complete")
    func capturesLargeOutput() async throws {
        let runner = CommandRunner()

        let result = try await runner.run(
            executable: URL(fileURLWithPath: "/usr/bin/seq"),
            arguments: ["1", "20000"],
            timeout: 5
        )

        #expect(result.exitCode == 0)
        #expect(result.output.hasSuffix("20000"))
    }

    @Test("Commands exceeding their deadline are terminated")
    func terminatesTimedOutCommand() async {
        let runner = CommandRunner()

        await #expect(throws: CommandRunnerError.self) {
            try await runner.run(
                executable: URL(fileURLWithPath: "/bin/sleep"),
                arguments: ["2"],
                timeout: 0.1
            )
        }
    }
}
