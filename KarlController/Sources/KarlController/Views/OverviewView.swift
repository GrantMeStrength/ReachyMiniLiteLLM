import SwiftUI

struct OverviewView: View {
    @Environment(RobotController.self) private var controller

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                statusGrid
                lifecycleControls
                modeControls
            }
            .padding(28)
        }
        .navigationTitle("Overview")
    }

    private var header: some View {
        VStack(alignment: .leading) {
            Text("Robot Karl")
                .font(.largeTitle)
                .bold()
            Text("Start services, choose an interactive mode, and monitor the robot.")
                .foregroundStyle(.secondary)
        }
    }

    private var statusGrid: some View {
        LazyVGrid(columns: [.init(.adaptive(minimum: 190))], spacing: 16) {
            StatusCard(
                title: "Robot Daemon",
                systemImage: "power",
                isAvailable: controller.status.daemon
            )
            StatusCard(
                title: "LED Eyes",
                systemImage: "eyes",
                isAvailable: controller.status.eyes
            )
            StatusCard(
                title: "Camera",
                systemImage: "camera",
                isAvailable: controller.status.camera
            )
        }
    }

    private var lifecycleControls: some View {
        GroupBox("Robot Services") {
            HStack {
                Button("Start Robot", systemImage: "play.fill") {
                    controller.startRobot()
                }
                .buttonStyle(.borderedProminent)
                .disabled(controller.isBusy || controller.status.daemon)

                Button("Stop Robot", systemImage: "stop.fill", role: .destructive) {
                    controller.stopRobot()
                }
                .disabled(controller.isBusy || !controller.status.daemon)

                Button("Wake Motion", systemImage: "sunrise") {
                    controller.wake()
                }
                .disabled(controller.isBusy || !controller.status.daemon)

                Spacer()
            }
            .padding(.top, 6)
        }
    }

    private var modeControls: some View {
        GroupBox("Interactive Modes") {
            VStack(spacing: 12) {
                ForEach(RobotMode.allCases) { mode in
                    HStack {
                        Label {
                            VStack(alignment: .leading) {
                                Text(mode.title)
                                    .bold()
                                Text(mode.subtitle)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: mode.systemImage)
                                .frame(width: 28)
                        }
                        Spacer()
                        if controller.activeMode == mode {
                            Button("Stop", systemImage: "stop.fill", role: .destructive) {
                                controller.stopMode()
                            }
                        } else {
                            Button("Start", systemImage: "play.fill") {
                                controller.startMode(mode)
                            }
                            .disabled(controller.isBusy)
                        }
                    }
                    if mode != RobotMode.allCases.last {
                        Divider()
                    }
                }
            }
            .padding(.top, 6)
        }
    }
}

private struct StatusCard: View {
    let title: String
    let systemImage: String
    let isAvailable: Bool

    var body: some View {
        HStack {
            Image(systemName: systemImage)
                .font(.title2)
                .foregroundStyle(isAvailable ? .green : .secondary)
                .frame(width: 36)
            VStack(alignment: .leading) {
                Text(title)
                    .bold()
                Text(isAvailable ? "Available" : "Unavailable")
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .padding()
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }
}
