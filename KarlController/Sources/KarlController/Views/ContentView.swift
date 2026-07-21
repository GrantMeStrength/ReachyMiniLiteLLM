import SwiftUI

struct ContentView: View {
    @Environment(RobotController.self) private var controller
    @State private var selection: ControllerSection? = .overview

    var body: some View {
        NavigationSplitView {
            List(ControllerSection.allCases, selection: $selection) { section in
                Label(section.title, systemImage: section.systemImage)
                    .tag(section)
            }
            .navigationTitle("Karl Controller")
            .safeAreaInset(edge: .bottom) {
                ConnectionSummary()
                    .padding()
            }
        } detail: {
            Group {
                switch selection ?? .overview {
                case .overview:
                    OverviewView()
                case .interact:
                    InteractionView()
                case .diagnostics:
                    DiagnosticsView()
                }
            }
            .toolbar {
                ToolbarItem {
                    Button("Refresh", systemImage: "arrow.clockwise") {
                        controller.refreshStatus()
                    }
                    .disabled(controller.isBusy)
                }
            }
        }
        .alert(
            "Karl Controller",
            isPresented: Binding(
                get: { controller.errorMessage != nil },
                set: { if !$0 { controller.errorMessage = nil } }
            )
        ) {
            Button("OK") {
                controller.errorMessage = nil
            }
        } message: {
            Text(controller.errorMessage ?? "Unknown error")
        }
    }
}

private struct ConnectionSummary: View {
    @Environment(RobotController.self) private var controller

    var body: some View {
        HStack {
            Image(systemName: controller.status.isOnline ? "circle.fill" : "circle")
                .foregroundStyle(controller.status.isOnline ? .green : .secondary)
                .accessibilityHidden(true)
            VStack(alignment: .leading) {
                Text(controller.status.isOnline ? "Karl Online" : "Karl Offline")
                    .bold()
                Text(controller.activity)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            if controller.isBusy {
                ProgressView()
                    .controlSize(.small)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
