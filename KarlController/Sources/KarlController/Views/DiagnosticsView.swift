import SwiftUI

struct DiagnosticsView: View {
    @Environment(RobotController.self) private var controller

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading) {
                    Text("Diagnostics")
                        .font(.largeTitle)
                        .bold()
                    Text("Inspect services, serial devices, and recent process logs.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Run Diagnostics", systemImage: "stethoscope") {
                    controller.runDiagnostics()
                }
                .buttonStyle(.borderedProminent)
                .disabled(controller.isBusy)
            }

            TextEditor(text: .constant(controller.diagnosticOutput))
                .fontDesign(.monospaced)
                .textSelection(.enabled)
                .scrollContentBackground(.hidden)
                .padding()
                .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))

            LabeledContent("Repository") {
                Text(controller.repositoryURL.path)
                    .textSelection(.enabled)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(28)
        .navigationTitle("Diagnostics")
    }
}
