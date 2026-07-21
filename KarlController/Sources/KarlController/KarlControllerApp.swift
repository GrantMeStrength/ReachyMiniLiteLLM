import SwiftUI

@main
struct KarlControllerApp: App {
    @State private var controller = RobotController()

    var body: some Scene {
        WindowGroup("Karl Controller") {
            ContentView()
                .environment(controller)
                .frame(minWidth: 900, minHeight: 650)
                .task {
                    controller.refreshStatus()
                }
        }
        .defaultSize(width: 1_080, height: 760)
    }
}
